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
