"""Central configuration — every secret is read from .env, never hardcoded (SRS §3.5)."""

import os

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised at startup when a required environment variable is missing."""


# --- Flask ---
SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
FLASK_ENV = os.getenv("FLASK_ENV", "development")

# --- MongoDB Atlas ---
# Name settled as MONGODB_URI to match .env.example, docs/ARCHITECTURE.md and the SDD.
# Only adapters/db_manager.py may consume these.
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "job_search_agent")

# --- Adzuna (250 requests/day free) ---
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "gb")

# --- Groq ---
# The API key lives here; the *model id* deliberately does not. It has a single
# home in the GROQ_MODEL constant in core/rag_pipeline.py, so there is exactly one
# place to change it and no way for two sources of truth to disagree mid-demo.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- Remotive: no key required ---

# --- Job cache ---
# Spec value. Kept here rather than hardcoded in the TTL index so it can be changed
# without touching code. Note the direction: a LONGER ttl means fewer Adzuna calls,
# because a cached query stays reusable for longer. Shortening it to save quota would
# do the opposite.
JOB_CACHE_TTL_MINUTES = 60

# --- Profile vocabularies ---
# The work types and experience levels offered at registration and on the profile form.
# Closed sets, so a crafted POST cannot store arbitrary values in the user document.
#
# These live here rather than in controllers/ui_controller.py, where they started, because
# core/intent_parser.py must validate Groq's output against the same sets. An AI-layer module
# importing from a controller inverts the SDD layering, and it also deadlocks: ui_controller
# imports core.agent, which imports core.intent_parser, which would import ui_controller --
# a cycle that fails with "partially initialized module". config.py imports nothing from the
# project, so nothing can cycle through it.
WORK_TYPES = ("remote", "full-time", "part-time", "freelance")

EXPERIENCE_LEVELS = ("entry level", "mid level", "senior")

# How people actually write each work type. Used in two places that must not disagree:
# core/intent_parser.py's keyword fallback matches against these, and
# adapters/api_client.py strips them out of the keyword string it sends to Adzuna.
#
# They live here for the same reason WORK_TYPES and EXPERIENCE_LEVELS do (2026-09-19): two
# layers need the same vocabulary, and an adapter importing from core/ would invert the SDD
# layering. config.py imports nothing from the project, so nothing can cycle through it.
#
# Why api_client strips them at all: Adzuna's `what=` is an AND keyword match against the job
# text. Measured 2026-09-20 -- "junior software engineer" returns 77 results, "remote junior
# software engineer" returns 0. A work-type word in the keyword field silently empties the
# search, and Adzuna reports that as HTTP 200 with no results, not as a failure.
WORK_TYPE_HINTS = {
    "remote": ("work from home", "from home", "remote", "wfh", "anywhere"),
    "freelance": ("self employed", "freelance", "contract", "gig"),
    "part-time": ("part time", "part-time", "casual"),
    "full-time": ("full time", "full-time", "permanent"),
}

# Words carrying no signal when deciding whether a Remotive job matches the query. Remotive
# ignores its own search parameter (see adapters/api_client.py), so the filtering is done
# locally against the job title, and without this list every query would match on "job".
QUERY_STOPWORDS = frozenset(
    {
        "level", "job", "jobs", "work", "working", "position", "positions", "role", "roles",
        "vacancy", "vacancies", "career", "careers", "experience", "experienced", "need",
        "needed", "want", "wanted", "looking", "seeking", "hiring", "please", "some",
        "something", "anything", "with", "without", "that", "this", "from", "into", "about",
        "and", "the", "for", "any", "can", "you", "your", "our",
    }
)

# --- Category vocabulary ---
# A closed set, shared by intent parsing and by the save/reject scoring loop, which
# only works if both name a category identically.
#
# It is also the injection defence. The deleted models.py built a MongoDB field path
# by interpolation — f"category_scores.{category}" — so a category containing a "." or
# a "$" wrote to an arbitrary field, or ran an operator. Membership of this tuple is
# checked before any category reaches a field path. A closed set, not escaping.
#
# TODO(M3): Adzuna and Remotive use different taxonomies and neither matches this list.
# Mapping their categories onto these values is still an open question in
# docs/PROJECT_STATUS.md and must be settled before the scoring loop is trusted.
CATEGORIES = (
    "technology",
    "writing",
    "design",
    "marketing",
    "sales",
    "finance",
    "healthcare",
    "education",
    "engineering",
    "customer_support",
    "hr",
    "legal",
    "other",
)

# Variables without which the app cannot do its job. Checked at startup rather than
# left to surface later as an opaque 401 from a provider, which is far harder to
# diagnose than a named missing key.
REQUIRED = ("MONGODB_URI", "ADZUNA_APP_ID", "ADZUNA_APP_KEY", "GROQ_API_KEY")


def validate():
    """Raise ConfigError naming every required variable that is missing from .env."""
    missing = [name for name in REQUIRED if not globals().get(name)]
    if missing:
        raise ConfigError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Copy .env.example to .env and fill them in."
        )
