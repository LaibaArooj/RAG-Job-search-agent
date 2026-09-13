"""JobCard — normalises Adzuna and Remotive responses into one field shape.

STUB — filled in during M2. Covers TC-022.

The two APIs disagree about shape, and that has already caused a real bug (Adzuna returns
company and location as nested objects; passing them to the template raw rendered Python
dicts on the page). The normalising currently lives inline in adapters/api_client.py and
moves here in M2, so there is exactly one place where a field-shape difference is resolved.

job_id is a SHA hash of title + company. It is what deduplication keys on when both APIs
syndicate the same listing, and what duplicate-save detection uses later.
"""

from dataclasses import dataclass


@dataclass
class JobCard:
    """One job listing in the single normalised shape the rest of the app expects."""

    job_id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    salary: object = None
    source: str = ""
    category: str = ""
    similarity_score: float = 0.0

    @classmethod
    def from_adzuna(cls, raw):
        """Normalise one Adzuna result, flattening its nested company and location objects."""
        raise NotImplementedError("M2")

    @classmethod
    def from_remotive(cls, raw):
        """Normalise one Remotive result, whose company and location are already flat strings."""
        raise NotImplementedError("M2")

    @staticmethod
    def make_job_id(title, company):
        """Return the SHA hash of title + company used for deduplication (TC-022)."""
        raise NotImplementedError("M2")
