"""Turns a plain-English query into structured intent plus alternative phrasings.

STUB — filled in during M2. Covers TC-019.

This is Deviation 1 from SRS v1.0 (see docs/PROJECT_SPEC.md § Deviations): the SDD §5.1
specified keyword matching with if-statements. That does not meet the SRS's own definition
of an Agent as something that "autonomously decides what steps to take", so the primary
path is a Groq call returning structured JSON, and keyword matching survives as the
fallback. Needs a line in the final report.

This is the FIRST of the two Groq calls per search. FR-018 applies here too: if Groq is
unavailable, parse_intent must fall back to keywords, not raise.
"""

# The closed set of categories. Shared with the scoring loop in adapters/db_manager.py —
# a job's category must come from this list or the save/reject scores fragment.
# TODO(M3): this is also the answer to the open question in docs/PROJECT_STATUS.md about
# how a job's category is derived. Decide before M3.
CATEGORIES = ()


def parse_intent(query):
    """Ask Groq for work type, experience, category and 2-3 query variants; keywords on failure."""
    raise NotImplementedError("M2")


def _parse_intent_keywords(query):
    """Keyword-matching fallback used when the Groq call fails (FR-018)."""
    raise NotImplementedError("M2")


def enrich_query(query, context):
    """Fold the user's profile into the query text before it is embedded."""
    raise NotImplementedError("M2")
