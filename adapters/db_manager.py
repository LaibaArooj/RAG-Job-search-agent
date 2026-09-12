"""MongoDB facade — the ONLY module in the project permitted to import PyMongo (SDD §3).

STUB — filled in during M1. Replaces the deleted models.py, which is preserved in git
history at 5519a22. Three defects in that version must NOT be carried over:

  1. NoSQL field-path injection: it built the update path as f"category_scores.{category}"
     from unvalidated input. A category containing a dot writes to an arbitrary field.
     Validate `category` against a known set before it reaches a field path.
  2. It called MongoClient() at module import with no try/except, so an Atlas outage
     crashed the app at startup instead of showing an error banner.
  3. Every exception in create_user was reported as "Username already taken", masking
     real faults. Catch DuplicateKeyError specifically.

Also note: models.py used datetime.utcnow(), deprecated from Python 3.12 onward.
Use datetime.now(timezone.utc) here.

Covers TC-001 to TC-005.
"""


class DatabaseManager:
    """Thin PyMongo facade — the single point of contact between the app and MongoDB Atlas."""

    def __init__(self, uri, db_name):
        """Store connection settings; connecting lazily keeps a DB outage out of startup."""
        raise NotImplementedError("M1")

    def ping(self):
        """Return True if Atlas answers, False otherwise — used to verify credentials."""
        raise NotImplementedError("M1")

    def ensure_indexes(self):
        """Create the unique index on users.username that makes duplicate signups fail."""
        raise NotImplementedError("M1")

    def create_user(self, username, password_hash, profile):
        """Insert a new user document; the caller passes an already-hashed password (TC-001)."""
        raise NotImplementedError("M1")

    def get_user(self, username):
        """Fetch one user document by username, or None."""
        raise NotImplementedError("M1")

    def get_user_context(self, user_id):
        """Return the profile and category_scores the search pipeline needs, in one read."""
        raise NotImplementedError("M1")

    def increment_score(self, username, category, delta):
        """Adjust one category preference score: +1 on save, -1 on reject (TC-011)."""
        raise NotImplementedError("M3")

    def add_saved_job(self, username, job):
        """Add a job to the user's saved list, keyed by job_id to avoid duplicates (TC-009)."""
        raise NotImplementedError("M3")

    def add_rejected_job(self, username, job_id):
        """Record a rejected job so it can be filtered out of later results (TC-010)."""
        raise NotImplementedError("M3")

    def add_search_history(self, username, query):
        """Append a query to search_history, keeping only the most recent 20."""
        raise NotImplementedError("M3")

    def get_top_categories(self, username, n=3):
        """Return the n highest-scoring categories, used to build the For You feed (TC-013)."""
        raise NotImplementedError("M3")
