"""User dataclass — mirrors the denormalised users document in docs/PROJECT_SPEC.md § Data model.

One document per user, denormalised on purpose: a single read returns the entire context
the search pipeline needs, with no joins. category_scores is a dynamic object specifically
so that a new category adds a key rather than requiring a schema migration.

This class holds data only. It performs no persistence — that belongs to
adapters/db_manager.py, which is the sole PyMongo consumer.
"""

from dataclasses import asdict, dataclass, field

# The document field is "password" and always holds a Werkzeug hash. The attribute is named
# password_hash so that nothing in the codebase can read `user.password` and believe it has
# a usable password.
_PASSWORD_FIELD = "password"


@dataclass
class User:
    """A user's profile, learned category preferences and saved/rejected job references."""

    username: str = ""
    password_hash: str = ""
    skills: list = field(default_factory=list)
    experience: str = ""
    location: str = ""
    preferred_work: list = field(default_factory=list)
    category_scores: dict = field(default_factory=dict)
    search_history: list = field(default_factory=list)
    saved_jobs: list = field(default_factory=list)
    rejected_jobs: list = field(default_factory=list)
    created_at: object = None

    @classmethod
    def from_document(cls, doc):
        """Build a User from a raw MongoDB document, tolerating missing optional fields."""
        # get_user_context() projects away most fields, so a partial document is normal and
        # must not raise. Defaults come from the dataclass, not from this call site.
        if not doc:
            return None
        return cls(
            username=doc.get("username", ""),
            password_hash=doc.get(_PASSWORD_FIELD, ""),
            skills=doc.get("skills") or [],
            experience=doc.get("experience", ""),
            location=doc.get("location", ""),
            preferred_work=doc.get("preferred_work") or [],
            category_scores=doc.get("category_scores") or {},
            search_history=doc.get("search_history") or [],
            saved_jobs=doc.get("saved_jobs") or [],
            rejected_jobs=doc.get("rejected_jobs") or [],
            created_at=doc.get("created_at"),
        )

    def to_document(self):
        """Serialise to a MongoDB document, omitting anything the schema does not define."""
        doc = asdict(self)
        doc[_PASSWORD_FIELD] = doc.pop("password_hash")
        return doc
