import json
import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# Single point of change for the LLM.
#
# SECOND forced substitution on this line. The SRS names Llama 3 8B-instant; Groq
# decommissioned its Llama 3 chat models (2026-09-13), so this became
# `groq/compound-mini`. On 2026-09-23 that model started returning 404 as well --
# "does not exist or you do not have access to it" -- and no groq/compound-* or
# Llama chat model remains on the account's model list. Both substitutions were
# forced by the provider, neither was a preference. Provider, cost and the
# free-tier constraint are unchanged throughout. Needs supervisor sign-off and a
# line in docs/PROJECT_SPEC.md § Deviations.
#
# The replacement is a REASONING model, and that is not a detail -- it changed
# max_tokens at both call sites. gpt-oss models spend hidden reasoning tokens
# before emitting any content, and max_tokens covers both. Measured 2026-09-23:
#
#   gpt-oss-20b, max_tokens=300 (the old intent budget): 99 reasoning tokens, the
#     JSON truncated, no parseable object, so parse_intent fell back to keywords
#     and query expansion silently stopped happening. TC-019 and TC-021 both
#     broken WITH THE APP STILL APPEARING TO WORK. That is the failure mode to
#     watch for whenever this constant changes.
#   gpt-oss-120b, max_tokens=700 (the old RAG budget): 475 reasoning tokens and
#     finish_reason="length" -- recommendations cut off mid-sentence.
#
# Both budgets below were raised to fit. Candidates measured on four test queries:
#
#   qwen/qwen3.8-27b     0 reasoning tokens, existing budgets fine, but reads
#                        "something creative I can do from home" as "other",
#                        which fails TC-019's category assertion.
#   openai/gpt-oss-20b   reads "junior software engineer" as "engineering".
#   openai/gpt-oss-120b  all four queries correct, TC-019 included. Chosen.
#
# The cost of the choice is latency: ~250-475 reasoning tokens per call, twice per
# search. If the demo feels slow, qwen is the fast fallback and the only thing it
# loses is that one category judgement.
# A CHAIN, not a single model, as of 2026-09-26. Groq has now retired this project's LLM
# twice in two weeks -- Llama 3, then groq/compound-mini -- and a free-tier catalogue will
# keep rotating. Pinning one model means that each retirement silently removes the AI
# Recommendations panel until somebody notices, which took two days last time.
#
# The order is the measured one (see the comment above and the two-week history below): the
# first model got all four intent test queries right, qwen missed one, gpt-oss-20b missed one.
# So a retirement now costs slightly different explanations instead of no panel at all, and
# buys time to choose a replacement properly rather than mid-demo.
#
# Both max_tokens budgets below are already sized for the reasoning models in this list, so
# any member of the chain is safe to fall through to. verify_agent.py asserts that.
GROQ_MODELS = (
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
)

# The primary. Kept as a name because core/intent_parser.py imports it and the docs name it.
GROQ_MODEL = GROQ_MODELS[0]

# How Groq words a model that no longer exists. Matched so that a RETIREMENT can be told
# apart from a network failure -- the distinction that cost two days on 2026-09-23, when
# verify_intent.py reported a dead model as "Groq unreachable" and it was read as a network
# blip. A retirement advances the chain; anything else fails fast to the FR-018 fallback
# rather than burning three timeouts.
_MODEL_GONE_MARKERS = (
    "model_not_found", "does not exist", "decommissioned", "deprecated",
)


def model_is_gone(error):
    """Return True if this error means the model itself is no longer offered."""
    return any(marker in str(error).lower() for marker in _MODEL_GONE_MARKERS)


def complete(client, messages, models=GROQ_MODELS, **params):
    """Call the first model in the chain that still exists; raise if none answer."""
    # Returns the reply text. The caller keeps its own try/except, because FR-018 requires a
    # working fallback whatever the reason -- this only decides whether trying the NEXT model
    # is worth a round trip.
    last_error = None
    for model in models:
        try:
            response = client.chat.completions.create(model=model, messages=messages, **params)
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            last_error = e
            if not model_is_gone(e):
                raise
            # Loud on purpose. A retired model is a thing the developer must act on, and the
            # old generic message hid it. verify_live.py also checks the chain against the
            # live catalogue so this surfaces before a demo rather than during one.
            print(f"GROQ MODEL RETIRED: {model!r} is no longer offered -- trying the next.")
    raise last_error

# FR-016 asks for three explained picks. Enforced on the way OUT as well as in the prompt --
# a prompt is a request, a slice is a guarantee.
MAX_PICKS = 3

# The reason is the one string on the rendered card that came from the model. Truncated so a
# runaway generation cannot push the ranked results off the page.
REASON_LIMIT = 400


def _extract_json(text):
    """Pull the first JSON object out of a model reply, tolerating markdown fences."""
    # Models wrap JSON in ```json fences often enough that failing on it would send working
    # replies down the fallback path. Slicing between the outermost braces handles fences,
    # preambles and trailing prose in one step.
    #
    # Lives here rather than in intent_parser, where it was written, because BOTH Groq call
    # sites need it and intent_parser already imports GROQ_MODEL from this module -- so this
    # is the direction that does not create a cycle. One parser, so the two call sites cannot
    # drift apart in how forgiving they are.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start : end + 1])


def _hiring_line(job):
    """Render one job's candidate-eligibility as a phrase the prompt can reason about."""
    # Plain English rather than the raw bucket name, because the model reads this as text.
    # "unknown" is stated as unknown and never smoothed into something reassuring: the whole
    # point of the field is that guessing costs the seeker a wasted application.
    eligibility = job.get("eligibility") or "unknown"
    candidate_location = (job.get("candidate_location") or "").strip()

    if eligibility == "open":
        return "anywhere in the world, no geographic restriction"
    if eligibility == "regional":
        return f"ONLY candidates in: {candidate_location or 'unspecified regions'}"
    if eligibility == "local":
        where = candidate_location or job.get("location") or "one location"
        return f"ONLY candidates already able to work in {where} (on-site or local role)"
    return "not stated by the employer"


class RAGPipeline:
    """Builds a prompt from the top ranked jobs and asks Groq to explain three picks."""

    def __init__(self, model=None, top_k=5):
        """Create a Groq client; the API key comes from the environment, never hardcoded."""
        # `model` pins a single model, which the evaluation scripts use to compare candidates.
        # Left unset, the whole GROQ_MODELS chain is tried in order, so a retirement degrades
        # the explanations rather than removing the panel.
        self.models = (model,) if model else GROQ_MODELS
        self.model = self.models[0]
        self.top_k = top_k
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))

    def build_prompt(self, query, jobs):
        """Format the top k already-ranked jobs into a single prompt string."""
        lines = []
        for i, job in enumerate(jobs[:self.top_k], 1):
            lines.append(
                f"Job {i}:\n"
                f"- Title: {job.get('title', 'Unknown')}\n"
                f"- Company: {job.get('company', 'Unknown')}\n"
                f"- Location: {job.get('location', 'Unknown')}\n"
                # Added 2026-09-23. Without this the model could not see eligibility at all
                # and routinely spent one of its three picks on a UK-only Adzuna role -- a
                # recommendation the user cannot act on, in the most prominent panel on the
                # page. The two lines are separate because they answer different questions:
                # Location is where the job IS, Hiring is where the candidate MAY LIVE.
                f"- Hiring from: {_hiring_line(job)}\n"
                f"- Source: {job.get('source', 'Unknown')}\n"
                f"- Description: {str(job.get('description', ''))[:400]}\n"
            )
        job_context = "\n".join(lines)

        return (
            f'A job seeker searched for: "{query}"\n\n'
            f"These are the highest ranked results already retrieved and re-ranked "
            f"for that search:\n\n{job_context}\n"
            # Changed 2026-10-11 from "Recommend the three best matches". Forcing three made
            # the model fill the slots when nothing fitted, with reasons like "This is a
            # recruitment-focused role, which does not meet the requirement" -- an
            # anti-recommendation under an AI Recommendations header. Reproduced on Q14 and
            # Q18 of the evaluation. Declining is now a stated, valid answer.
            f"Recommend up to three jobs from the list above that genuinely fit the "
            f"search. Do not recommend a job if your reason would say it does not fit. "
            f'If none of them fits, reply {{"picks": []}}.\n'
            f'Reply with JSON only, in exactly this shape:\n'
            f'{{"picks": [{{"index": <the Job number above>, '
            f'"reason": "<two sentences on why it fits>"}}]}}\n'
            f"At most three picks. Use each Job number at most once, and only numbers that "
            f"appear above.\n"
            # The model is asked for an INDEX, never for a title, company or URL. Everything
            # rendered on the resulting card comes from our own job dict, so a hallucinated
            # listing is impossible by construction rather than by trusting the model.
            f"Do not include the job title, the company or any URL in your reply -- the "
            f"index identifies the job. Do not invent jobs.\n"
            # Each reason is rendered on its own card, away from the others. Without this the
            # model writes them as one flowing list -- observed 2026-09-25: "Again, the
            # position is open worldwide..." reads as a non-sequitur once split apart.
            f"Each reason must stand on its own, because it is shown beside that one job "
            f"and nothing else. Do not refer to the other picks, and do not number them.\n"
            # Prefer, not exclude. A hard "only recommend open roles" rule would leave the
            # panel empty whenever all five top-ranked jobs are location-restricted, which
            # for a UK-heavy result set is common -- and an empty panel teaches the user
            # nothing. Ranking them lower and stating the restriction keeps the panel
            # useful and honest at the same time.
            f"Prefer jobs whose 'Hiring from' line shows no geographic restriction, "
            f"because the seeker can actually apply for those. If you recommend a job "
            f"that is restricted to a place or region, say so plainly in its first "
            f"sentence so the seeker is not misled.\n"
            f"Write plain text, no markdown."
        )

    def fallback(self):
        """Return None so the caller hides the AI section and still shows ranked results (FR-018)."""
        return None

    @staticmethod
    def validate_picks(raw, job_count):
        """Coerce the model's reply into a clean list of {index, reason}, or raise ValueError."""
        # Same discipline as core.intent_parser._validate_intent: the reply is untrusted
        # input, exactly like a form POST, and every field is checked before it leaves this
        # module. Here the index selects which of OUR job dicts gets rendered as a card with
        # a live Save button, so an out-of-range value would either crash the join or
        # silently attach the model's reasoning to the wrong listing.
        picks = raw.get("picks") if isinstance(raw, dict) else None
        if not isinstance(picks, list):
            raise ValueError("no picks list in reply")
        if not picks:
            # The model DECLINED: nothing fitted. A valid answer since 2026-10-11, returned as
            # [] so the caller can tell it apart from None, which means Groq failed.
            return []

        cleaned = []
        seen = set()
        for item in picks:
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            # bool is a subclass of int; True would otherwise pass as index 1.
            if isinstance(index, bool) or not isinstance(index, int):
                continue
            if not 1 <= index <= job_count or index in seen:
                continue
            reason = item.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                continue
            seen.add(index)
            cleaned.append({"index": index, "reason": reason.strip()[:REASON_LIMIT]})
            if len(cleaned) >= MAX_PICKS:
                break

        if not cleaned:
            # The model offered picks and every one was unusable. That is garbage, not a
            # decline, so it takes the FR-018 fallback and the band is hidden.
            raise ValueError("no usable picks in reply")
        return cleaned

    def run(self, query, jobs):
        """Return validated picks, [] if the model declined, or None if Groq fails."""
        # STRUCTURED, not prose, as of 2026-09-25. The panel renders real job cards with
        # working Save/Reject buttons, so it needs to know WHICH jobs were picked -- prose
        # could only be printed. Strict by choice: a reply that will not parse yields None
        # and the band is hidden, rather than falling back to printing the raw text. One
        # contract is easier to defend than two, and a prose path exercised only when the
        # model misbehaves is exactly the kind of branch that rots untested.
        if not jobs:
            return self.fallback()

        # Held outside the try so a failure can log what the model actually said. Added
        # 2026-10-11: the 10-01 evaluation recorded 9 failures and no replies, so finding out
        # that every one was a deliberate decline took a second round of calls.
        text = ""
        try:
            text = complete(
                self.client,
                [{"role": "user", "content": self.build_prompt(query, jobs)}],
                models=self.models,
                temperature=0.3,
                # Covers the model's hidden reasoning tokens as well as the prose. At 700
                # gpt-oss-120b returned finish_reason="length" and cut off mid-sentence.
                max_tokens=1200,
            )
            if not text:
                return self.fallback()
            return self.validate_picks(_extract_json(text), len(jobs[:self.top_k]))
        except Exception as e:
            # Deliberately one catch for the API call, the JSON parse and the validation.
            # All three mean the same thing to the user -- no explanation available -- and
            # FR-018 says the app must never crash when the LLM is unavailable. TC-009
            # covers this path.
            # The raw reply goes to the server log only, never to the page.
            print(f"Groq RAG error: {e}" + (f" -- reply began: {text[:200]!r}" if text else ""))
            return self.fallback()
