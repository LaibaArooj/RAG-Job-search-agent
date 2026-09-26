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

import os
import re

from groq import Groq

# The closed sets, defined once in config.py. Intent parsing and the save/reject scoring loop
# in adapters/db_manager.py must name a category identically or the loop silently fragments
# across spellings.
#
# Settled 2026-09-21: the two API taxonomies are not mapped at all. classify_category below
# applies CATEGORY_HINTS to a fetched job's own text, so a query and a job are categorised by
# one table and one rule. See config.py above CATEGORIES for the full reasoning.
from config import (
    CATEGORIES,
    CATEGORY_HINTS,
    EXPERIENCE_LEVELS,
    WORK_TYPE_HINTS,
    WORK_TYPES,
)
from core.rag_pipeline import GROQ_MODEL, _extract_json, complete

# At most three variants including the original query, per docs/PROJECT_SPEC.md § M2.
# The cap is enforced here rather than trusted to the prompt: each extra variant is another
# Adzuna call, and Adzuna allows 250 a day.
MAX_VARIANTS = 3

# A query that matches no category still has to name one, because category_scores is keyed by
# these values. "other" is in CATEGORIES precisely so there is a safe landing value.
DEFAULT_CATEGORY = "other"

# Hints of this length or shorter must match a WHOLE word; longer ones match at a word start.
#
# The short ones are real terms -- "ui", "ux", "seo" -- but as bare substrings they are inside
# ordinary English: s-ui-ted, b-ui-lt, req-ui-rements, s-eo-ul. Measured 2026-09-22 against
# the jobs three real users had saved, "ui" alone put four of five software jobs into design.
#
# The longer hints anchor only at the START of a word because several entries in
# CATEGORY_HINTS are deliberate stems -- copywrit, illustrat, programm, journalis -- which
# exist to catch their own longer forms and would match nothing if both ends were anchored.
# The cost of the looser end is that a stem can still match a longer unrelated word; the
# benefit is that the table keeps working as written. Anchoring the start is what stops
# "developer" matching inside "nondeveloper".
WHOLE_WORD_MAX_LENGTH = 3

# Compiled once at import rather than per call. classify_category runs on every job of every
# search and every feed build -- eighty-odd jobs times thirteen categories times six hints is
# a lot of regex compilation to repeat for a result that never changes.
_HINT_PATTERNS = {
    category: tuple(
        re.compile(
            r"\b"
            + re.escape(hint)
            + (r"\b" if len(hint) <= WHOLE_WORD_MAX_LENGTH else "")
        )
        for hint in hints
    )
    for category, hints in CATEGORY_HINTS.items()
}

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
        text = complete(
            _groq_client(),
            [{"role": "user", "content": _build_prompt(query)}],
            temperature=TEMPERATURE,
            # Must cover the model's hidden reasoning tokens as well as the JSON. At 300 a
            # reasoning model truncated the object, _extract_json raised, and parse_intent
            # fell back to keywords with query expansion silently gone. See GROQ_MODEL.
            max_tokens=600,
            timeout=TIMEOUT_SECONDS,
        )
        raw = _extract_json(text)
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

    # The same table and the same matcher that classify a fetched JOB (classify_category
    # below). Sharing them is the point: if the query path and the job path used separate
    # tables, a query parsed as "writing" and a job classified as "content" would increment
    # different keys in category_scores and the preference loop would fragment in silence.
    intent["category"] = classify_category(text)

    # No expansion without the LLM. Inventing variants by string manipulation would widen the
    # pool with phrasings nobody chose, and TC-021 measures expansion against the LLM path.
    intent["variants"] = [query]
    return intent


def _best_category(text):
    """Return the category matching the most hints in text, or None if none match at all."""
    # Rule 3 of the 2026-09-22 rewrite: the category with the MOST hint matches wins, and
    # CATEGORY_HINTS order is only the tie-break. The comparison is strict `>`, and dict
    # iteration is insertion order, so on a tie the category listed first still takes it --
    # "Marketing Content Writer" is still writing. Order remains a real, stated rule; it is
    # just no longer the whole decision.
    #
    # Distinct hints are counted, not occurrences. A category that matches four different
    # hints (developer, software, python, data) has four independent pieces of evidence; a
    # description that happens to say "design" five times has one, repeated. Counting
    # occurrences would let a long advert win on repetition alone.
    best = None
    best_count = 0
    for category, patterns in _HINT_PATTERNS.items():
        count = sum(1 for pattern in patterns if pattern.search(text))
        if count > best_count:
            best = category
            best_count = count
    return best


def classify_category(title, fallback=DEFAULT_CATEGORY, description=None):
    """Return the config.CATEGORIES value whose hints best match the title, else the text."""
    # Used for two different things on purpose. _parse_intent_keywords passes a user's QUERY
    # as the title and no description; JobSearchAgent.classify passes a fetched JOB's title
    # and description separately. Both must land on the same vocabulary, because one writes
    # the category the other later scores.
    #
    # Rewritten 2026-09-22 after reading the live user documents: four of the five jobs real
    # users had saved were filed as "design" when every one of them was a software job, so
    # two accounts carried a design preference nobody had expressed. Three rules replaced
    # "first substring hit in table order", and each fixed part of that:
    #
    #   1. The TITLE decides. The description is consulted only when the title names no
    #      category at all. All five misfiled jobs said "Software" or "Developer" in the
    #      title; the description is where the noise was.
    #   2. Hints are matched with word boundaries (see _HINT_PATTERNS). "ui" was matching
    #      inside "suited", "built" and "requirements", which is close to every advert.
    #   3. Most hint matches wins, with table order as the tie-break only (_best_category).
    #
    # Honest description, unchanged and still required in the report: this is keyword
    # matching over job text. It is NOT classification by meaning. It still misfiles a job
    # whose title and description name no category word -- those land on the fallback -- and
    # it still cannot tell a job that mentions design from a job that is about design.
    category = _best_category((title or "").lower())

    if category is None and description:
        category = _best_category(description.lower())

    if category is not None:
        return category

    # The fallback is validated too. classify_category's return value reaches a MongoDB field
    # path via DatabaseManager._score_path, and the caller supplying the fallback is the agent
    # passing an intent category, so it is not a constant this module controls.
    return fallback if fallback in CATEGORIES else DEFAULT_CATEGORY


def enrich_query(query, context, experience=None):
    """Fold the user's profile into the query text before it is embedded."""
    # The profile moves the QUERY vector, not the job vectors. TC-016 expects Python roles to
    # rank higher for a user whose profile lists Python; that works by pulling the query point
    # towards Python in embedding space. Editing the job text instead would change what every
    # user sees, not what this user sees.
    #
    # `experience` overrides the profile's level when parse_intent found one stated in the
    # query itself. A user whose profile says "mid level" searching for a "beginner" role
    # means the query, not the profile: embedding both put two conflicting levels into one
    # vector, and measurement on 2026-09-20 showed it narrowing the similarity gap between a
    # junior and a senior job by roughly a third.
    #
    # REWRITTEN 2026-09-26. The old format was
    #     f"job search: {query}. Skills: {skills}. Level: {level}."
    # and it was destroying the search. For a two-word query the labels -- "job search:",
    # "Skills:", "Level:" -- were most of the embedded text, so the vector described the
    # SCAFFOLDING rather than what the user asked for. Measured on "customer support" against
    # a support job and a QA job:
    #
    #     "customer support"                                      gap +0.240
    #     "job search: customer support. Skills: . Level: ..."    gap +0.051
    #     ...with Skills: python                                  gap +0.023
    #
    # A 90% collapse, and +0.023 is BELOW the +0.10 that a category scored 5 contributes via
    # CATEGORY_BOOST -- so a learned preference could overturn meaning outright. That is the
    # direct cause of the complaint that results were "related to the field but completely
    # unrelated to what I would apply for".
    #
    # Two changes, both measured over the ten cases in evaluation/model_comparison.py plus
    # two targeted probes (see evaluation/enrichment_comparison.py to reproduce):
    #
    #   - Drop the labels. They carry no meaning a job advert can match.
    #   - Repeat the query once. It restores the query's share of the text without removing
    #     the profile. Repeating it a THIRD time was measured and adds nothing, which is why
    #     the number is two rather than an arbitrary choice.
    #
    # The result beats the old format on every measure taken -- accuracy and margin, with and
    # without a profile, plus the discrimination probe AND TC-016's skill lift. There was no
    # trade to make.
    #
    # Empty parts are omitted rather than left as separators. A naive join produced
    # "nursing job in a hospital. . ." for a user with no skills or level, and that measurably
    # cost accuracy on the neutral case.
    context = context or {}
    skills = ", ".join(context.get("skills") or [])
    level = experience or context.get("experience", "") or ""
    parts = [part for part in (query, query, skills, level) if part]
    return ". ".join(parts) + "." if parts else ""
