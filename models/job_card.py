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

# The wordings a remote board uses to mean "we will hire you wherever you live". Both
# Remotive and Jobicy state it in free text rather than a flag, so this is the one place
# that text is interpreted.
UNRESTRICTED_TERMS = ("worldwide", "anywhere", "global", "remote - worldwide")


def remote_eligibility(candidate_location):
    """Bucket a remote board's candidate-location text as open, regional or unknown."""
    # Deliberately only three outcomes, and deliberately NOT a country matcher. Deciding
    # whether "APAC" or "EMEA" includes a particular user is a judgement this function is in
    # no position to make, and making it wrong means telling someone they can apply for a job
    # that will reject them -- the exact failure this field exists to prevent. Anything not
    # positively unrestricted is "regional", and the raw text is shown so the user can judge.
    text = (candidate_location or "").strip().lower()
    if not text:
        # Remotive uses an empty string for "no restriction" (see from_remotive). Jobicy
        # never returns empty under geo=anywhere. An empty value is therefore either
        # unrestricted or unstated, and the two cannot be told apart here.
        return "unknown"
    if any(term in text for term in UNRESTRICTED_TERMS):
        return "open"
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
    # IS, Remotive's "Worldwide" is where the candidate MAY LIVE. Both were being written
    # into `location` and rendered in the same slot, so a user in Pakistan could not tell a
    # job that would hire them from one that would reject them on sight.
    #
    # candidate_location is the raw text the source gave us, kept verbatim for display.
    # eligibility is the coarse bucket the template badges, one of:
    #   "open"     - no geographic restriction stated (Worldwide / Anywhere)
    #   "regional" - restricted to named regions or countries; read candidate_location
    #   "local"    - an on-site or single-market role (every Adzuna listing)
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
            candidate_location=raw.get("candidate_required_location") or "",
            eligibility=remote_eligibility(raw.get("candidate_required_location")),
        )

    @classmethod
    def from_jobicy(cls, raw):
        """Normalise one Jobicy result; its field names are camelCase and all its own."""
        # Added 2026-09-23. Jobicy is the only free source that BOTH searches properly and
        # filters by candidate eligibility server-side (geo=anywhere), which is why it was
        # added -- see adapters/api_client.py for the measurements that justified it.
        raw = raw or {}
        title = raw.get("jobTitle") or "Unknown Title"
        company = raw.get("companyName") or "Unknown"
        return cls(
            job_id=cls.make_job_id(title, company),
            title=title,
            company=company,
            location="Remote",
            # jobExcerpt is the short summary; jobDescription is full HTML and can be large.
            # Preferring the excerpt keeps the embedded text closer to MiniLM's 256-token
            # window than a truncated HTML advert would be.
            description=(raw.get("jobExcerpt") or raw.get("jobDescription") or "")[
                :DESCRIPTION_LIMIT
            ],
            url=raw.get("url") or "#",
            salary=raw.get("salaryMin"),
            source="Jobicy",
            candidate_location=raw.get("jobGeo") or "",
            eligibility=remote_eligibility(raw.get("jobGeo")),
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
