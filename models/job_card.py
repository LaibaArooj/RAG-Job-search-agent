"""JobCard — normalises Adzuna and Remotive responses into one field shape.

Covers TC-022.

The two APIs disagree about shape, and that has already caused a real bug (Adzuna returns
company and location as nested objects; passing them to the template raw rendered Python
dicts on the page). The normalising used to live inline in adapters/api_client.py; it lives
here now, so there is exactly one place where a field-shape difference is resolved.

job_id is a SHA hash of title + company. It is what deduplication keys on when both APIs
syndicate the same listing, and what duplicate-save detection uses later.

The dataclass is an internal shape only. Everything downstream — RAGPipeline.build_prompt,
DatabaseManager._record_decision, the Jinja templates — already reads jobs as dicts, so the
agent calls to_dict() at the boundary. One normalised shape inside, no ripple outside.
"""

import hashlib
from dataclasses import asdict, dataclass

# The hexdigest is truncated because the full 64 characters buy nothing here and make every
# stored saved_jobs entry longer. 16 hex characters is 64 bits; at the few hundred jobs a
# single search produces, a collision is not a realistic failure mode.
JOB_ID_LENGTH = 16

# Remotive descriptions are full HTML job adverts and can run to tens of kilobytes. They are
# truncated before embedding because all-MiniLM-L6-v2 only reads the first 256 word-pieces
# anyway, so the rest is stored and sent to Groq for nothing.
DESCRIPTION_LIMIT = 500


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
        # The two .get({}) defaults are the fix for the rendered-dict bug: Adzuna omits these
        # objects entirely on some results, so chaining .get on a missing key would raise.
        raw = raw or {}
        title = raw.get("title") or "Unknown Title"
        company = (raw.get("company") or {}).get("display_name") or "Unknown"
        return cls(
            job_id=cls.make_job_id(title, company),
            title=title,
            company=company,
            location=(raw.get("location") or {}).get("display_name") or "Unknown",
            description=raw.get("description") or "",
            url=raw.get("redirect_url") or "#",
            salary=raw.get("salary_min"),
            source="Adzuna",
        )

    @classmethod
    def from_remotive(cls, raw):
        """Normalise one Remotive result, whose company and location are already flat strings."""
        raw = raw or {}
        title = raw.get("title") or "Unknown Title"
        company = raw.get("company_name") or "Unknown"
        return cls(
            job_id=cls.make_job_id(title, company),
            title=title,
            company=company,
            # Remotive's own wording for "no location restriction" is an empty string, which
            # would render as a bare em dash next to the company name.
            location=raw.get("candidate_required_location") or "Remote — Worldwide",
            description=(raw.get("description") or "")[:DESCRIPTION_LIMIT],
            url=raw.get("url") or "#",
            salary=raw.get("salary"),
            source="Remotive",
        )

    @staticmethod
    def make_job_id(title, company):
        """Return the SHA-256 hash of title + company used for deduplication (TC-022)."""
        # Lowercased and stripped because that is precisely what TC-022 tests: the same
        # listing syndicated to both APIs arrives with different casing and padding, and a
        # byte-exact comparison would call the two copies different jobs.
        #
        # The "|" separator matters. Without it, ("Data", "Xco") and ("DataX", "co") hash to
        # the same string and one real job would silently swallow the other.
        key = f"{(title or '').strip().lower()}|{(company or '').strip().lower()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:JOB_ID_LENGTH]

    def to_dict(self):
        """Return the plain dict shape the templates, RAGPipeline and DatabaseManager read."""
        return asdict(self)
