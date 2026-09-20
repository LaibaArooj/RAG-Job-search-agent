"""Turns a plain-English query into structured intent plus alternative phrasings.

Covers TC-019 (LLM intent parsing) and TC-020 (fallback when Groq is unavailable).

This is Deviation 1 from SRS v1.0 (see docs/PROJECT_SPEC.md § Deviations): the SDD §5.1
specified keyword matching with if-statements. That does not meet the SRS's own definition
of an Agent as something that "autonomously decides what steps to take", so the primary
path is a Groq call returning structured JSON, and keyword matching survives as the
fallback. Needs a line in the final report.

This is the FIRST of the two Groq calls per search. FR-018 applies here too: if Groq is
unavailable, parse_intent must fall back to keywords, not raise.

Two rules shape the whole module:

1. **Parsing and validation are separate steps.** Groq's reply is untrusted input, exactly
   like a form POST. Every field is checked for membership in a closed set before it leaves
   this module. In M3 `category` reaches a MongoDB field path (`category_scores.<category>`),
   which is the injection hole config.py documents; trusting the model's string there would
   reopen it.

2. **Both paths return the identical dict shape.** JobSearchAgent must never branch on
   whether the LLM or the keyword fallback ran. Only the `source` field records which did,
   and that exists for the demo and the report, not for control flow.
"""

import json
import os

from groq import Groq

# The closed sets, defined once in config.py. Intent parsing and the save/reject scoring loop
# in adapters/db_manager.py must name a category identically or the loop silently fragments
# across spellings.
#
# TODO(M3): mapping Adzuna's and Remotive's differing taxonomies onto CATEGORIES is still the
# open question in docs/PROJECT_STATUS.md. Decide before M3.
from config import CATEGORIES, EXPERIENCE_LEVELS, WORK_TYPE_HINTS, WORK_TYPES
from core.rag_pipeline import GROQ_MODEL

# At most three variants including the original query, per docs/PROJECT_SPEC.md § M2.
# The cap is enforced here rather than trusted to the prompt: each extra variant is another
# Adzuna call, and Adzuna allows 250 a day.
MAX_VARIANTS = 3

# A query that matches no category still has to name one, because category_scores is keyed by
# these values. "other" is in CATEGORIES precisely so there is a safe landing value.
DEFAULT_CATEGORY = "other"

# Intent parsing is extraction, not generation. Near-zero temperature keeps the same query
# returning the same intent, which matters for a live viva demo and for the M4 evaluation
# run being reproducible.
TEMPERATURE = 0.1

# A hung request must not hang the search. Groq is one step of several and the user is waiting
# on all of them; better to fall back to keywords than to stall the page.
TIMEOUT_SECONDS = 10

_client = None


def _groq_client():
    """Return a lazily constructed Groq client, so a missing key cannot break module import."""
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def _blank_intent(query, source):
    """Return the canonical intent dict with nothing detected, used as every path's base."""
    return {
        "work_type": None,
        "experience": None,
        "category": DEFAULT_CATEGORY,
        "variants": [query] if query else [],
        "source": source,
    }


def _build_prompt(query):
    """Format the intent-extraction prompt, enumerating the allowed values inline."""
    # The allowed values are listed in the prompt AND checked again on the way out. The prompt
    # steers the model; the check is what actually guarantees the closed set, because a prompt
    # is a request and a membership test is not.
    return (
        f'A job seeker typed this search: "{query}"\n\n'
        f"Extract their intent as JSON with exactly these four keys:\n"
        f'  "work_type": the single closest match from {list(WORK_TYPES)}, or null\n'
        f'  "experience": the single closest match from {list(EXPERIENCE_LEVELS)}, or null\n'
        f'  "category": the single closest match from {list(CATEGORIES)}\n'
        f'  "variants": 2 or 3 short alternative keyword phrasings of this search,\n'
        f"      the kind of terms a job board would index, as a list of strings\n\n"
        f"Pick the single closest member of each list even when the search does not use "
        f"that exact word. Never invent a value outside a list; use null instead. "
        f'For "category" there is no null -- if nothing fits, use "other".\n'
        f"Reply with the JSON object only. No markdown, no commentary."
    )


def _extract_json(text):
    """Pull the first JSON object out of a model reply, tolerating markdown fences."""
    # Models wrap JSON in ```json fences often enough that failing on it would send working
    # replies down the fallback path. Slicing between the outermost braces handles fences,
    # preambles and trailing prose in one step.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start : end + 1])


def _validate_variants(raw, query):
    """Clean the model's variant list, guaranteeing the original query comes first."""
    # The original query leads the list so that query expansion can only ever widen the
    # candidate pool. If a bad variant displaced it, expansion could return fewer jobs than
    # no expansion at all, which would invert what TC-021 is meant to demonstrate.
    variants = [query]
    seen = {query.lower()}

    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if not item or item.lower() in seen:
                continue
            variants.append(item)
            seen.add(item.lower())
            if len(variants) >= MAX_VARIANTS:
                break

    return variants


def _validate_intent(raw, query, source):
    """Coerce a parsed reply into the canonical shape, dropping anything outside the closed sets."""
    intent = _blank_intent(query, source)

    if not isinstance(raw, dict):
        return intent

    # Membership, not sanitising. An unrecognised value is discarded rather than repaired,
    # because there is no safe way to repair a string the model invented.
    work_type = raw.get("work_type")
    if isinstance(work_type, str) and work_type.strip().lower() in WORK_TYPES:
        intent["work_type"] = work_type.strip().lower()

    experience = raw.get("experience")
    if isinstance(experience, str) and experience.strip().lower() in EXPERIENCE_LEVELS:
        intent["experience"] = experience.strip().lower()

    # This is the one that matters most: in M3 the category becomes part of a MongoDB field
    # path. A value like "technology.$ne" must not survive this line.
    category = raw.get("category")
    if isinstance(category, str) and category.strip().lower() in CATEGORIES:
        intent["category"] = category.strip().lower()

    intent["variants"] = _validate_variants(raw.get("variants"), query)
    return intent


def parse_intent(query):
    """Ask Groq for work type, experience, category and 2-3 query variants; keywords on failure."""
    query = (query or "").strip()

    # TC-017: an empty query makes no external call at all. Returning early here means the rule
    # holds even if a caller forgets to check, and it saves a Groq call per stray submit.
    if not query:
        return _blank_intent("", "keywords")

    try:
        response = _groq_client().chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": _build_prompt(query)}],
            temperature=TEMPERATURE,
            max_tokens=300,
            timeout=TIMEOUT_SECONDS,
        )
        raw = _extract_json((response.choices[0].message.content or "").strip())
        return _validate_intent(raw, query, "llm")
    except Exception as e:
        # FR-018. A network error, a decommissioned model, a rate limit and a reply that is not
        # JSON are all the same event to the caller: the LLM did not answer, so use keywords.
        # Caught broadly on purpose -- the search must complete regardless.
        print(f"Groq intent parsing failed, falling back to keywords: {e}")
        return _parse_intent_keywords(query)


def _parse_intent_keywords(query):
    """Keyword-matching fallback used when the Groq call fails (FR-018)."""
    query = (query or "").strip()
    intent = _blank_intent(query, "keywords")
    if not query:
        return intent

    text = query.lower()

    # Substring matching over the same closed sets the LLM path validates against, so the two
    # paths cannot disagree about what a category is called. Synonyms are listed explicitly
    # because "from home" is how people actually write "remote" and a bare membership test
    # would miss it. This is the crude path, and the code should look crude.
    # WORK_TYPE_HINTS moved to config.py on 2026-09-20: adapters/api_client.py strips the
    # same terms out of the keyword string it sends to Adzuna, and the two must not drift.
    # Same reasoning that moved WORK_TYPES and EXPERIENCE_LEVELS there, and config.py imports
    # nothing from the project so an adapter reading it cannot cycle.
    for work_type, hints in WORK_TYPE_HINTS.items():
        if any(h in text for h in hints):
            intent["work_type"] = work_type
            break

    experience_hints = {
        "entry level": (
            "no experience", "entry", "junior", "graduate", "starting out",
            "beginner", "trainee", "intern",
        ),
        "senior": ("senior", "lead", "principal", "head of", "experienced", "expert"),
        "mid level": ("mid level", "mid-level", "intermediate"),
    }
    for experience, hints in experience_hints.items():
        if any(h in text for h in hints):
            intent["experience"] = experience
            break

    category_hints = {
        "writing": ("writing", "writer", "content", "copywrit", "editor", "journalis"),
        "design": ("design", "ux", "ui", "graphic", "illustrat", "creative"),
        "technology": (
            "developer", "software", "programm", "python", "data",
            "web dev", "devops", "coding",
        ),
        "marketing": ("marketing", "seo", "social media", "brand", "advertis"),
        "sales": ("sales", "account executive", "business development"),
        "finance": ("finance", "account", "audit", "bookkeep", "financial"),
        "healthcare": ("health", "nurse", "medical", "clinical", "care assistant"),
        "education": ("teach", "tutor", "lectur", "education", "school"),
        "customer_support": (
            "customer support", "customer service", "help desk", "call centre",
        ),
        "hr": ("human resources", "recruit", "talent acquisition"),
        "legal": ("legal", "lawyer", "solicitor", "paralegal", "compliance"),
        "engineering": ("mechanical", "electrical", "civil engineer", "manufacturing"),
    }
    for category, hints in category_hints.items():
        if any(h in text for h in hints):
            intent["category"] = category
            break

    # No expansion without the LLM. Inventing variants by string manipulation would widen the
    # pool with phrasings nobody chose, and TC-021 measures expansion against the LLM path.
    intent["variants"] = [query]
    return intent


def enrich_query(query, context, experience=None):
    """Fold the user's profile into the query text before it is embedded."""
    # The profile moves the QUERY vector, not the job vectors. TC-016 expects Python roles to
    # rank higher for a user whose profile lists Python; that works by pulling the query point
    # towards Python in embedding space. Editing the job text instead would change what every
    # user sees, not what this user sees.
    #
    # The wording is carried over unchanged from the search route in app.py, which is the one
    # code path already demonstrated to satisfy TC-016. Moving it here is a relocation, not a
    # rewrite -- changing the phrasing would invalidate that evidence.
    #
    # `experience` overrides the profile's level when parse_intent found one stated in the
    # query itself. A user whose profile says "mid level" searching for a "beginner" role
    # means the query, not the profile: embedding both put two conflicting levels into one
    # vector, and measurement on 2026-09-20 showed it narrowing the similarity gap between a
    # junior and a senior job by roughly a third.
    #
    # The FORMAT is untouched, and the two-argument call still produces the byte-identical
    # string TC-016 was proven against. Only which value fills "Level:" can change.
    context = context or {}
    skills = ", ".join(context.get("skills") or [])
    level = experience or context.get("experience", "") or ""
    return f"job search: {query}. Skills: {skills}. Level: {level}."
