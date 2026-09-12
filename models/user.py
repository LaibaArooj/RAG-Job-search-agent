"""User dataclass — mirrors the denormalised users document in docs/PROJECT_SPEC.md § Data model.

STUB — filled in during M1.

One document per user, denormalised on purpose: a single read returns the entire context
the search pipeline needs, with no joins. category_scores is a dynamic object specifically
so that a new category adds a key rather than requiring a schema migration.

This class holds data only. It performs no persistence — that belongs to
adapters/db_manager.py, which is the sole PyMongo consumer.
"""

from dataclasses import dataclass, field


@dataclass
class User:
    """A user's profile, learned category preferences and saved/rejected job references."""

    username: str = ""
    password_hash: str = ""
    skills: list = field(default_factory=list)
    experience: str = ""
    location: str = ""
    preferred_work: str = ""
    category_scores: dict = field(default_factory=dict)
    search_history: list = field(default_factory=list)
    saved_jobs: list = field(default_factory=list)
    rejected_jobs: list = field(default_factory=list)
    created_at: object = None

    @classmethod
    def from_document(cls, doc):
        """Build a User from a raw MongoDB document, tolerating missing optional fields."""
        raise NotImplementedError("M1")

    def to_document(self):
        """Serialise to a MongoDB document, omitting anything the schema does not define."""
        raise NotImplementedError("M1")
