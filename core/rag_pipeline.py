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
GROQ_MODEL = "openai/gpt-oss-120b"


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

    def __init__(self, model=GROQ_MODEL, top_k=5):
        """Create a Groq client; the API key comes from the environment, never hardcoded."""
        self.model = model
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
            f"Recommend the three best matches from the list above. For each one give "
            f"the job title, the company, and two sentences explaining why it fits the "
            f"search. Only use jobs from the list. Do not invent jobs.\n"
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

    def run(self, query, jobs):
        """Generate recommendations for the top ranked jobs, or fall back if Groq is unavailable."""
        if not jobs:
            return self.fallback()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": self.build_prompt(query, jobs)}],
                temperature=0.3,
                # Covers the model's hidden reasoning tokens as well as the prose. At 700
                # gpt-oss-120b returned finish_reason="length" and cut off mid-sentence.
                max_tokens=1200,
            )
            text = (response.choices[0].message.content or "").strip()
            return text or self.fallback()
        except Exception as e:
            print(f"Groq API error: {e}")
            return self.fallback()
