"""JobCard — normalises Adzuna and Himalayas responses into one field shape.

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

# Remote-board descriptions are full HTML job adverts and can run to tens of kilobytes. They are
# truncated before embedding because all-MiniLM-L6-v2 only reads the first 256 word-pieces
# anyway, so the rest is stored and sent to Groq for nothing.
DESCRIPTION_LIMIT = 500

def restriction_eligibility(restrictions, country_name):
    """Bucket a STRUCTURED list of allowed countries as open, country or regional."""
    # Added 2026-10-13 with Himalayas, which states eligibility as a list of country names
    # (`locationRestrictions`) rather than free text. That difference is the whole reason an
    # exact country match is allowed here when it never was for Remotive's or Jobicy's prose:
    #
    #   - free text ("APAC", "EMEA or APAC time zones") would need a JUDGEMENT about whether
    #     a region includes the user, and a wrong judgement wastes an application;
    #   - a list either contains "Pakistan" or it does not. No judgement, nothing guessed.
    #
    # An empty list is Himalayas' own encoding of "no restriction" (measured 2026-10-13:
    # country=Pakistan with worldwide=true returns only empty lists).
    names = [str(n).strip().lower() for n in (restrictions or []) if str(n).strip()]
    if not names:
        return "open"
    if country_name and country_name.strip().lower() in names:
        return "country"
    return "regional"


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

    # Added 2026-09-23. `location` and `candidate_location` answer two DIFFERENT questions
    # and conflating them is what made this invisible: Adzuna's "London" is where the job
    # IS, a remote board's "Worldwide" is where the candidate MAY LIVE. Both were being written
    # into `location` and rendered in the same slot, so a user in Pakistan could not tell a
    # job that would hire them from one that would reject them on sight.
    #
    # candidate_location is the raw text the source gave us, kept verbatim for display.
    # eligibility is the coarse bucket the template badges, one of:
    #   "open"     - no geographic restriction stated (Worldwide / Anywhere)
    #   "country"  - restricted to a list of countries that names the USER'S country
    #                (added 2026-10-13; only ever set from a structured list, never prose)
    #   "regional" - restricted to named regions or countries; read candidate_location
    #   "local"    - an on-site role in the market that was queried (Adzuna).
    #                Sources are chosen per country, so that market is the user's own
    #   "unknown"  - the source said nothing usable; DO NOT guess, say so
    # "unknown" exists on purpose. Guessing whether "APAC" includes Pakistan would produce
    # a confident wrong answer, which is worse than an honest one -- the same lesson as the
    # "ui" substring bug. The user is shown the raw text and decides.
    candidate_location: str = ""
    eligibility: str = "unknown"

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
            # Adzuna is a country-market board: every listing is a local role in the market
            # that was queried, and the API has no concept of hiring a remote candidate from
            # abroad. So this is "local" as a fact about the SOURCE, not a guess about the
            # job. Do not describe Adzuna results as remote-eligible anywhere.
            candidate_location=(raw.get("location") or {}).get("display_name") or "",
            eligibility="local",
        )

    @classmethod
    def from_himalayas(cls, raw, country_name=None):
        """Normalise one Himalayas result, reading eligibility from its structured country list."""
        # Added 2026-10-13, replacing Remotive and Jobicy. Himalayas is queried with the
        # user's country (adapters/api_client.py), so every result is EITHER unrestricted OR
        # names that country; "regional" is kept for the day their filter disagrees with
        # their data, and is then shown honestly rather than hidden.
        raw = raw or {}
        title = raw.get("title") or "Unknown Title"
        company = raw.get("companyName") or "Unknown"
        restrictions = raw.get("locationRestrictions") or []
        return cls(
            job_id=cls.make_job_id(title, company),
            title=title,
            company=company,
            location="Remote",
            # The excerpt is a short plain-text summary; `description` is full HTML. Same
            # reasoning as before: closer to MiniLM's 256-token window than truncated HTML.
            description=(raw.get("excerpt") or raw.get("description") or "")[
                :DESCRIPTION_LIMIT
            ],
            url=raw.get("applicationLink") or "#",
            salary=raw.get("minSalary"),
            source="Himalayas",
            candidate_location=", ".join(restrictions) if restrictions else "Worldwide",
            eligibility=restriction_eligibility(restrictions, country_name),
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
