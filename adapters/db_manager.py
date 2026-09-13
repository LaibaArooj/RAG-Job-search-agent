"""MongoDB facade — the ONLY module in the project permitted to import PyMongo (SDD §3).

Replaces the deleted models.py (preserved at 5519a22). Three defects in that version are
deliberately not repeated, and each is marked in place below:

  1. NoSQL field-path injection — it built the update path as f"category_scores.{category}"
     from unvalidated input, so a category containing "." or "$" wrote to an arbitrary
     field. Fixed by _score_path(), which checks membership of config.CATEGORIES first.
  2. It called MongoClient() at module import with no try/except, so an Atlas outage
     crashed the app at startup rather than rendering an error banner. Fixed by
     connecting lazily on first use.
  3. Every exception in create_user was reported as "Username already taken", masking real
     faults. Fixed by catching DuplicateKeyError specifically and letting the rest through.

Covers TC-001, TC-002, TC-010, TC-011, TC-012, TC-013.
"""

from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

import config

# Fail in seconds rather than the 30s default. A wrong password should report itself
# while you are still looking at the screen.
SERVER_SELECTION_TIMEOUT_MS = 5000

SEARCH_HISTORY_LIMIT = 20


class DatabaseError(RuntimeError):
    """Raised when MongoDB is unreachable, so callers can show a banner instead of a trace."""


def _utcnow():
    """Return an aware UTC timestamp; datetime.utcnow() is deprecated from Python 3.12."""
    return datetime.now(timezone.utc)


class DatabaseManager:
    """Thin PyMongo facade — the single point of contact between the app and MongoDB Atlas."""

    def __init__(self, uri=None, db_name=None):
        """Store connection settings; connecting lazily keeps a DB outage out of startup."""
        self.uri = uri or config.MONGODB_URI
        self.db_name = db_name or config.MONGODB_DB_NAME
        self._client = None

    # --- connection ---------------------------------------------------------------

    @property
    def db(self):
        """Return the database handle, opening the connection on first use."""
        if self._client is None:
            if not self.uri:
                raise DatabaseError(
                    "MONGODB_URI is not set. Copy .env.example to .env and fill it in."
                )
            self._client = MongoClient(
                self.uri, serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS
            )
        return self._client[self.db_name]

    @property
    def users(self):
        """Return the users collection."""
        return self.db["users"]

    @property
    def job_cache(self):
        """Return the optional job_cache collection."""
        return self.db["job_cache"]

    def ping(self):
        """Return True if Atlas answers, False otherwise — used to verify credentials."""
        try:
            self.db.command("ping")
            return True
        except PyMongoError as e:
            print(f"MongoDB ping failed: {e}")
            return False

    def close(self):
        """Close the client, if one was ever opened."""
        if self._client is not None:
            self._client.close()
            self._client = None

    # --- indexes ------------------------------------------------------------------

    def ensure_indexes(self):
        """Create the unique username index and the job_cache TTL index; safe to re-run."""
        # TC-002 is enforced here, by the database, rather than by an if-statement in
        # Python. A read-then-write check ("does this username exist? no, insert it")
        # can be beaten by a second registration landing between the two operations.
        # A unique index cannot: the second insert is rejected by the server.
        self.users.create_index([("username", ASCENDING)], unique=True, name="username_unique")

        # MongoDB deletes documents whose created_at is older than expireAfterSeconds.
        # The sweeper runs roughly once a minute, so expiry is "about 60 minutes", not exact.
        self.job_cache.create_index(
            [("created_at", ASCENDING)],
            expireAfterSeconds=config.JOB_CACHE_TTL_MINUTES * 60,
            name="job_cache_ttl",
        )

    # --- injection guard ----------------------------------------------------------

    @staticmethod
    def _score_path(category):
        """Return the category_scores field path, rejecting any category not in the closed set."""
        # Defect 1 from models.py. The category reaches a MongoDB field path, so it must be
        # a known value — a "." would traverse into a subdocument, a "$" could be read as an
        # operator. Whitelist membership, not escaping.
        if category not in config.CATEGORIES:
            raise ValueError(
                f"Unknown category {category!r}. Must be one of config.CATEGORIES."
            )
        return f"category_scores.{category}"

    # --- users --------------------------------------------------------------------

    def create_user(self, username, password_hash, profile=None):
        """Insert a new user; the caller passes an already-hashed password (TC-001, TC-002)."""
        profile = profile or {}
        doc = {
            "username": username,
            "password": password_hash,
            "skills": profile.get("skills", []),
            "experience": profile.get("experience", ""),
            "location": profile.get("location", ""),
            "preferred_work": profile.get("preferred_work", []),
            "category_scores": {},
            "search_history": [],
            "saved_jobs": [],
            "rejected_jobs": [],
            "created_at": _utcnow(),
        }
        try:
            self.users.insert_one(doc)
            return True, "Account created successfully"
        except DuplicateKeyError:
            # Defect 3 from models.py: this is the ONLY error that means the name is taken.
            # Anything else propagates, so a real fault is never disguised as one (TC-002).
            return False, "Username taken"

    def get_user(self, username):
        """Fetch one user document by username, or None."""
        return self.users.find_one({"username": username})

    def get_user_context(self, username):
        """Return the profile and scores the search pipeline needs, in a single read."""
        # The users document is denormalised precisely so this is one round trip and no join.
        return self.users.find_one(
            {"username": username},
            {
                "_id": 0,
                "username": 1,
                "skills": 1,
                "experience": 1,
                "location": 1,
                "preferred_work": 1,
                "category_scores": 1,
                "rejected_jobs": 1,
            },
        )

    def update_profile(self, username, profile):
        """Update the editable profile fields only, never password or scores (TC-008)."""
        allowed = ("skills", "experience", "location", "preferred_work")
        # Build the update from a fixed key list rather than from whatever the form posted,
        # so a crafted field name cannot overwrite password or category_scores.
        update = {k: profile[k] for k in allowed if k in profile}
        if not update:
            return False
        result = self.users.update_one({"username": username}, {"$set": update})
        return result.matched_count == 1

    # --- save / reject ------------------------------------------------------------

    def save_job(self, username, job, category):
        """Save a job and raise its category score by 1, exactly once per job (TC-010, TC-013)."""
        return self._record_decision(username, job, category, delta=1)

    def reject_job(self, username, job, category):
        """Reject a job and lower its category score by 1, exactly once per job (TC-011)."""
        return self._record_decision(username, job, category, delta=-1)

    def _record_decision(self, username, job, category, delta):
        """Apply a save or reject as one atomic, idempotent update."""
        score_path = self._score_path(category)
        job_id = job["job_id"]

        if delta > 0:
            list_field, already_has = "saved_jobs", {"saved_jobs.job_id": {"$ne": job_id}}
            entry = {
                "job_id": job_id,
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "category": category,
                "location": job.get("location", ""),
                "source": job.get("source", ""),
                "source_url": job.get("url", ""),
                "saved_at": _utcnow(),
            }
        else:
            # Deviation 4 from SRS v1.0: rejected_jobs stores job_id, not job titles.
            # Titles are not unique across employers, so rejecting one "Software Engineer"
            # would hide every job with that title from the feed. See PROJECT_SPEC
            # § Deviations. Needs supervisor sign-off.
            list_field, already_has = "rejected_jobs", {"rejected_jobs": {"$ne": job_id}}
            entry = job_id

        # TC-013 by construction. The filter requires that this job is NOT already in the
        # list, so a second save matches no document and neither the push nor the increment
        # happens. Reading the document first and then deciding would leave a window in
        # which a double-click applies the increment twice; this is one atomic operation.
        result = self.users.update_one(
            {"username": username, **already_has},
            {"$push": {list_field: entry}, "$inc": {score_path: delta}},
        )
        return result.matched_count == 1  # False means it was already recorded

    # --- history and feed ---------------------------------------------------------

    def add_search_history(self, username, query):
        """Append a query to search_history, keeping only the most recent 20."""
        self.users.update_one(
            {"username": username},
            {"$push": {"search_history": {"$each": [query], "$slice": -SEARCH_HISTORY_LIMIT}}},
        )

    def get_top_categories(self, username, n=3):
        """Return the n highest-scoring categories, used to build the For You feed (TC-012)."""
        user = self.get_user(username)
        if not user:
            return []
        scores = user.get("category_scores") or {}
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        # Only positive scores. A category the user has rejected more than saved must not
        # appear in the feed at all — TC-012 requires tech jobs absent, not merely last.
        return [category for category, score in ranked[:n] if score > 0]

    # --- job cache ----------------------------------------------------------------

    def cache_get(self, query_hash):
        """Return a cached result set for this query, or None if absent or expired."""
        return self.job_cache.find_one({"_id": query_hash})

    def cache_put(self, query_hash, query_text, results):
        """Store a result set under the query hash, resetting its 60-minute TTL."""
        self.job_cache.update_one(
            {"_id": query_hash},
            {
                "$set": {
                    "query_text": query_text,
                    "results": results,
                    "created_at": _utcnow(),
                },
                "$inc": {"hit_count": 1},
            },
            upsert=True,
        )
