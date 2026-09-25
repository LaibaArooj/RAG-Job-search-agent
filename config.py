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

# --- Countries ---
# Where the user is, as ISO 3166-1 alpha-2. Added 2026-09-23.
#
# This exists for ONE decision: whether a given job source can serve this user at all. Adzuna
# is a country-market API -- jobs/<country>/search -- and it has no endpoint for a country it
# does not cover, so querying it on behalf of a user in an uncovered country returns jobs that
# will reject them on sight. See ADZUNA_COUNTRIES below.
#
# The full list is stored rather than a "supported / other" flag. A sentinel would collapse
# Pakistan, Nigeria and the UAE into one value, which is the same two-meanings-in-one-field
# mistake that made JobCard.location unreadable, and it would have to be undone the moment
# region matching (does "APAC" include this user?) is attempted.
#
# Sovereign states only. That is a principled boundary; "the ten countries I picked" is not,
# and an arbitrary list is exactly the kind of choice a viva pulls on.
COUNTRIES = {
    "af": "Afghanistan", "al": "Albania", "dz": "Algeria", "ad": "Andorra", "ao": "Angola",
    "ag": "Antigua and Barbuda", "ar": "Argentina", "am": "Armenia", "au": "Australia",
    "at": "Austria", "az": "Azerbaijan", "bs": "Bahamas", "bh": "Bahrain", "bd": "Bangladesh",
    "bb": "Barbados", "by": "Belarus", "be": "Belgium", "bz": "Belize", "bj": "Benin",
    "bt": "Bhutan", "bo": "Bolivia", "ba": "Bosnia and Herzegovina", "bw": "Botswana",
    "br": "Brazil", "bn": "Brunei", "bg": "Bulgaria", "bf": "Burkina Faso", "bi": "Burundi",
    "kh": "Cambodia", "cm": "Cameroon", "ca": "Canada", "cv": "Cape Verde",
    "cf": "Central African Republic", "td": "Chad", "cl": "Chile", "cn": "China",
    "co": "Colombia", "km": "Comoros", "cg": "Congo", "cd": "Congo (DRC)", "cr": "Costa Rica",
    "ci": "Côte d'Ivoire", "hr": "Croatia", "cu": "Cuba", "cy": "Cyprus", "cz": "Czechia",
    "dk": "Denmark", "dj": "Djibouti", "dm": "Dominica", "do": "Dominican Republic",
    "ec": "Ecuador", "eg": "Egypt", "sv": "El Salvador", "gq": "Equatorial Guinea",
    "er": "Eritrea", "ee": "Estonia", "sz": "Eswatini", "et": "Ethiopia", "fj": "Fiji",
    "fi": "Finland", "fr": "France", "ga": "Gabon", "gm": "Gambia", "ge": "Georgia",
    "de": "Germany", "gh": "Ghana", "gr": "Greece", "gd": "Grenada", "gt": "Guatemala",
    "gn": "Guinea", "gw": "Guinea-Bissau", "gy": "Guyana", "ht": "Haiti", "hn": "Honduras",
    "hu": "Hungary", "is": "Iceland", "in": "India", "id": "Indonesia", "ir": "Iran",
    "iq": "Iraq", "ie": "Ireland", "il": "Israel", "it": "Italy", "jm": "Jamaica",
    "jp": "Japan", "jo": "Jordan", "kz": "Kazakhstan", "ke": "Kenya", "ki": "Kiribati",
    "kw": "Kuwait", "kg": "Kyrgyzstan", "la": "Laos", "lv": "Latvia", "lb": "Lebanon",
    "ls": "Lesotho", "lr": "Liberia", "ly": "Libya", "li": "Liechtenstein", "lt": "Lithuania",
    "lu": "Luxembourg", "mg": "Madagascar", "mw": "Malawi", "my": "Malaysia",
    "mv": "Maldives", "ml": "Mali", "mt": "Malta", "mh": "Marshall Islands",
    "mr": "Mauritania", "mu": "Mauritius", "mx": "Mexico", "fm": "Micronesia",
    "md": "Moldova", "mc": "Monaco", "mn": "Mongolia", "me": "Montenegro", "ma": "Morocco",
    "mz": "Mozambique", "mm": "Myanmar", "na": "Namibia", "nr": "Nauru", "np": "Nepal",
    "nl": "Netherlands", "nz": "New Zealand", "ni": "Nicaragua", "ne": "Niger",
    "ng": "Nigeria", "kp": "North Korea", "mk": "North Macedonia", "no": "Norway",
    "om": "Oman", "pk": "Pakistan", "pw": "Palau", "ps": "Palestine", "pa": "Panama",
    "pg": "Papua New Guinea", "py": "Paraguay", "pe": "Peru", "ph": "Philippines",
    "pl": "Poland", "pt": "Portugal", "qa": "Qatar", "ro": "Romania", "ru": "Russia",
    "rw": "Rwanda", "kn": "Saint Kitts and Nevis", "lc": "Saint Lucia",
    "vc": "Saint Vincent and the Grenadines", "ws": "Samoa", "sm": "San Marino",
    "st": "São Tomé and Príncipe", "sa": "Saudi Arabia", "sn": "Senegal", "rs": "Serbia",
    "sc": "Seychelles", "sl": "Sierra Leone", "sg": "Singapore", "sk": "Slovakia",
    "si": "Slovenia", "sb": "Solomon Islands", "so": "Somalia", "za": "South Africa",
    "kr": "South Korea", "ss": "South Sudan", "es": "Spain", "lk": "Sri Lanka",
    "sd": "Sudan", "sr": "Suriname", "se": "Sweden", "ch": "Switzerland", "sy": "Syria",
    "tw": "Taiwan", "tj": "Tajikistan", "tz": "Tanzania", "th": "Thailand",
    "tl": "Timor-Leste", "tg": "Togo", "to": "Tonga", "tt": "Trinidad and Tobago",
    "tn": "Tunisia", "tr": "Türkiye", "tm": "Turkmenistan", "tv": "Tuvalu", "ug": "Uganda",
    "ua": "Ukraine", "ae": "United Arab Emirates", "gb": "United Kingdom",
    "us": "United States", "uy": "Uruguay", "uz": "Uzbekistan", "vu": "Vanuatu",
    "va": "Vatican City", "ve": "Venezuela", "vn": "Vietnam", "ye": "Yemen",
    "zm": "Zambia", "zw": "Zimbabwe",
}

# The country markets Adzuna actually serves, VERIFIED EMPIRICALLY on 2026-09-23 by calling
# jobs/<code>/search for each candidate: these 19 returned HTTP 200, and ru, se, pk, ae and ng
# returned 404. Adzuna does not publish this list -- its docs show only `gb` -- so it was
# measured rather than assumed, and it should be re-measured if searches start failing.
#
# A user outside these 19 has Adzuna SKIPPED, not filtered afterwards: the call would spend a
# unit of the 250/day quota to fetch jobs the user cannot take. Note this is not "Pakistan is
# excluded" -- there is no jobs/pk/search endpoint to call.
ADZUNA_COUNTRIES = frozenset(
    {
        "at", "au", "be", "br", "ca", "ch", "de", "es", "fr", "gb",
        "in", "it", "mx", "nl", "nz", "pl", "sg", "us", "za",
    }
)

# Used for a user whose document predates the country field. Keeping the old behaviour for
# them is deliberate: if "no country" meant "skip Adzuna", every existing account would
# silently lose most of its results the moment this shipped -- a data migration wearing a
# feature's clothes.
DEFAULT_ADZUNA_COUNTRY = "gb"

# --- Search autocomplete (FR-011, TC-007) ---
# The "predefined categories" half of the SRS's autocomplete source; the other half is the
# user's own search_history, added at render time by controllers/ui_controller.py.
#
# Deliberately NOT config.CATEGORIES. Those are database keys -- "customer_support",
# "technology" -- and showing a database key to a job seeker is showing them our schema.
# TC-007 expects typing "tec" to suggest "Technology" and "Tech Support", which the CATEGORIES
# tuple cannot produce: it has no "Tech Support" and its keys are lowercase with underscores.
#
# These are search phrases, not a closed set that anything is validated against -- the user
# stays free to type whatever they like, and the suggestion list only saves them typing.
SEARCH_SUGGESTIONS = (
    "Technology", "Tech Support", "Software Developer", "Web Developer",
    "Data Analyst", "Writing", "Content Writer", "Copywriter",
    "Design", "Graphic Designer", "UX Designer",
    "Marketing", "Digital Marketing", "Social Media Manager",
    "Sales", "Account Executive",
    "Finance", "Accountant", "Financial Analyst",
    "Healthcare", "Nurse", "Care Assistant",
    "Education", "Teacher", "Tutor",
    "Engineering", "Mechanical Engineer", "Electrical Engineer",
    "Customer Support", "Customer Service", "Help Desk",
    "Human Resources", "Recruiter",
    "Legal", "Paralegal",
    "Remote", "Entry Level", "Part Time", "Freelance",
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
# Settled 2026-09-21 (this was the TODO(M3) open question): neither API taxonomy is
# consulted. Adzuna tags jobs with its own categories, Remotive with a different set, and
# reconciling them would mean two mapping tables at different granularities with no answer
# for a job whose source omits the field. Instead every job -- whichever source it came from
# -- is classified locally from its own title and description against CATEGORY_HINTS below,
# by core.intent_parser.classify_category. One rule for both sources, so a user's score for
# a category cannot fragment according to which API happened to return the job.
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

# How each category is recognised in free text. Used in two places that must agree, for the
# same reason WORK_TYPE_HINTS above lives here: core/intent_parser.py matches a user's QUERY
# against this table in its keyword fallback, and the same module's classify_category matches
# a fetched JOB's title and description against it. If the two ever used separate tables, a
# query parsed as "writing" and a job classified as "content" would score different keys and
# the preference loop would silently fragment.
#
# Every key must be a member of CATEGORIES. That is what keeps this table and
# DatabaseManager._score_path's whitelist in agreement -- a hint key outside CATEGORIES would
# produce a category the database layer then refuses.
#
# Matching is substring, first key wins, and dict iteration is insertion order -- so the
# ORDER of this table is the tie-break rule for a job that mentions two fields. It is a crude
# matcher and the report must say so: a job whose text names no category word at all lands in
# "other". This is keyword classification, not classification by meaning.
CATEGORY_HINTS = {
    "writing": ("writing", "writer", "content", "copywrit", "editor", "journalis"),
    "design": ("design", "ux", "ui", "graphic", "illustrat", "creative"),
    "technology": (
        "developer", "software", "programm", "python", "data",
        "web dev", "devops", "coding",
    ),
    "marketing": ("marketing", "seo", "social media", "brand", "advertis"),
    "sales": ("sales", "account executive", "business development"),
    "finance": ("finance", "account", "audit", "bookkeep", "financial"),
    "healthcare": ("health", "nurse", "medical", "clinical", "care assistant"),
    "education": ("teach", "tutor", "lectur", "education", "school"),
    "customer_support": (
        "customer support", "customer service", "help desk", "call centre",
    ),
    "hr": ("human resources", "recruit", "talent acquisition"),
    "legal": ("legal", "lawyer", "solicitor", "paralegal", "compliance"),
    "engineering": ("mechanical", "electrical", "civil engineer", "manufacturing"),
}

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
