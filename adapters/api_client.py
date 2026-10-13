"""Adzuna and Himalayas HTTP access. The only module in the project that imports requests.

One fetch path, used by JobSearchAgent: fetch_variant() fetches a single query variant from
every source that can serve the user's country and returns
{"jobs": [JobCard], "failed_sources": [str], "empty_sources": [str]}.

Each source needs its own compensation, and all of it is this module's business under the SDD
layering rule -- nothing above here should have to know how any API misbehaves.

**Adzuna** and **Himalayas** both do a real keyword search, and both treat it as an AND match,
so one extra word empties it. Measured 2026-09-20 on Adzuna: "junior software engineer"
returns 77 results, "remote junior software engineer" returns 0. Measured 2026-10-13 on
Himalayas: "data analyst" 174, "entry level remote data analyst job in Pakistan" 0. Both report
that as HTTP 200 with no results -- a legitimate empty search, not a failure -- so nothing
upstream could tell that the query itself was the problem. Work-type words are stripped, and ONE
narrowed retry is allowed, under the same rule for every source (_narrowed_attempts).

**Remotive and Jobicy were removed on 2026-10-13.** Remotive ignored its `search` parameter
(16 identical jobs for every query) and its own API notice asks for at most 4 calls a day, which
one call per variant per search already broke. Jobicy's worldwide-eligible pool had shrunk from
100 jobs (2026-09-23) to 11. Neither could serve a seeker in Pakistan; Himalayas returned 3,947
jobs open to that seeker on the same day. See docs/CHANGELOG.md 2026-10-13.

Three signals go back, not two. A source that FAILED and a source that succeeded but returned
NOTHING are different events, and collapsing them is what once hid a bug: the user saw a full
page of irrelevant jobs with no warning, because Adzuna had politely returned zero.
"""

import re

import requests

import config

# JobCard imports nothing from this package, so this cannot cycle. Kept at the top where
# PEP 8 puts it: an import that only works lower down is hiding a cycle, not avoiding one.
from models.job_card import JobCard

ADZUNA_PER_VARIANT = 10

# Himalayas, added 2026-10-13. The search endpoint returns at most 20 per page whatever is
# asked for (measured: limit=50 still returned 20), so 20 is the honest number to request.
HIMALAYAS_URL = "https://himalayas.app/jobs/api/search"
HIMALAYAS_PER_VARIANT = 20

# Adzuna's own work-type parameters, verified live on 2026-09-20 against a control: a made-up
# parameter returns HTTP 400, so these three are genuinely honoured rather than ignored.
#
# "remote" is deliberately absent. Adzuna has no remote filter -- `where=remote` returns 0 --
# so remote intent is served by removing the word from the keywords (which is what was
# breaking the search) and by Himalayas, which is an all-remote board.
ADZUNA_WORK_TYPE_PARAMS = {
    "full-time": {"full_time": 1},
    "part-time": {"part_time": 1},
    "freelance": {"contract": 1},
}

# Longest first, so "work from home" is removed before "from" or "home" can match inside it.
_WORK_TYPE_TERMS = sorted(
    {term for terms in config.WORK_TYPE_HINTS.values() for term in terms},
    key=len,
    reverse=True,
)

# Every hint word from config.CATEGORY_HINTS, flattened once at import. Used by
# _signal_terms to decide which words of a query name a field of work.
_CATEGORY_WORDS = tuple(
    hint for hints in config.CATEGORY_HINTS.values() for hint in hints
)

# Two characters is too short to be evidence of anything; "ai" would match "said".
MIN_TOKEN_LENGTH = 3

# Title words that give a job's seniority away, used by _wrong_level below.
#
# Why this is needed: a job titled "Senior Golang Developer" matches the word "developer" from
# an expanded or narrowed variant, so it passes the keyword search while being exactly the
# wrong level. That is the shape of the 2026-09-20 report -- a beginner query returning
# senior roles (then from Remotive, which has since been removed).
_SENIOR_MARKERS = (
    "senior", "snr", "sr", "lead", "principal", "head of", "director", "chief",
    "architect", "manager", "vp", "experienced",
    # Roman numeral grades. "iv" is deliberately absent: it collides with intravenous, and a
    # "Registered Nurse IV Therapy" is not a senior role.
    "ii", "iii",
    # "staff" is NOT here on its own, because a Staff Nurse is an entry-level clinical role in
    # the UK and dropping it would be a serious miss for a healthcare search. The engineering
    # sense is matched by the longer phrases instead, which costs the rarer wordings.
    "staff engineer", "staff software engineer",
)
_JUNIOR_MARKERS = (
    "junior", "jnr", "graduate", "entry level", "entry-level", "trainee",
    "intern", "apprentice",
)

# Phrases where a seniority word is part of the JOB'S SUBJECT rather than its rank. Stripped
# from the title before the test, so "Senior Care Assistant" -- an entry-level role caring for
# older people -- and "Lead Generation Specialist" -- entry-level sales and marketing -- are
# not mistaken for senior appointments.
#
# This list is the honest cost of keyword seniority detection: every word that signals rank in
# one industry means something else in another, and there is no way to know which from a title
# alone. Expect to add to it, and say so in the report rather than implying the rule is
# general.
_SENIORITY_EXCEPTIONS = (
    "senior care", "senior living", "senior citizen", "seniors",
    "lead generation", "leads",
)


def _compile_markers(markers):
    """Compile title markers to whole-word patterns, so "lead" cannot match "leadership"."""
    # Word boundaries, for the same reason CATEGORY_HINTS needed them on 2026-09-22: a bare
    # substring test on "lead" dropped "Lead Generation Specialist" and "Leadership
    # Development Intern", both entry-level roles. Measured 2026-09-26: nine of nine
    # deliberately chosen junior titles were being filtered out as senior.
    return tuple(re.compile(r"\b" + re.escape(m) + r"\b") for m in markers)


_SENIOR_PATTERNS = _compile_markers(_SENIOR_MARKERS)
_JUNIOR_PATTERNS = _compile_markers(_JUNIOR_MARKERS)
_EXCEPTION_PATTERNS = _compile_markers(_SENIORITY_EXCEPTIONS)


def _matches_any(patterns, text):
    """Return True if any compiled pattern occurs in text."""
    return any(pattern.search(text) for pattern in patterns)


def _adzuna_keywords(query):
    """Strip work-type words from a variant, leaving keywords Adzuna's AND match can satisfy."""
    cleaned = query.lower()
    for term in _WORK_TYPE_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", " ", cleaned)
    cleaned = " ".join(cleaned.split())
    # A query that is nothing BUT work-type words ("remote work") would otherwise become an
    # empty keyword search. Falling back to the original is no worse than the old behaviour.
    return cleaned or query


def _signal_terms(query):
    """Return the query's job-domain words, for a narrower retry when a search finds nothing."""
    # Adzuna's `what=` is an AND match: every word must appear in the advert. Measured
    # 2026-09-26 over the twenty pre-registered evaluation queries, only 3 returned the five
    # results precision@5 needs and 16 returned NOTHING AT ALL -- including
    # "paralegal position no prior experience", where "paralegal" alone returns plenty. The
    # casual, constraint-heavy phrasing the SRS says users actually type is exactly what an
    # AND match cannot answer, so the keyword baseline was failing for the queries this
    # project exists to serve.
    #
    # The words kept are the ones that name a FIELD OF WORK, decided by the same
    # CATEGORY_HINTS vocabulary the classifier uses. Reusing that table rather than writing a
    # second one is the point: a word worth classifying a job by is a word worth searching on,
    # and two tables would drift.
    #
    # Falls back to the plain meaningful tokens when nothing in the query names a field, e.g.
    # "work with numbers but not boring" -- which needs interpretation ("numbers" means
    # finance) that only the LLM's query expansion can supply.
    tokens = _query_tokens(query)
    signal = [
        token for token in tokens
        if any(token.startswith(hint) or hint.startswith(token) for hint in _CATEGORY_WORDS)
    ]
    return signal or tokens


def _query_tokens(query):
    """Return the meaningful words of a query, with work-type words and stopwords removed."""
    stripped = _adzuna_keywords(query)
    return [
        t
        for t in re.findall(r"[a-z0-9+#]{%d,}" % MIN_TOKEN_LENGTH, stripped.lower())
        if t not in config.QUERY_STOPWORDS
    ]


def _wrong_level(title, experience):
    """Return True if a title's seniority clearly contradicts the level the user asked for."""
    # Keyword-based on purpose. The embedding cannot do this job: cosine similarity rates
    # "junior developer" against "senior developer" at 0.806, so the two are near-synonyms in
    # that space. An explicit word test is the only thing that separates them reliably.
    #
    # Applied to every source, and only when a level is known -- see _filter_level for why
    # even the sources that genuinely search are not exempt.
    #
    # The level now reaches here from the user's PROFILE when the query does not state one
    # (see core/agent.py). Before 2026-09-26 it came only from the parsed query, so a recent
    # graduate typing "software engineer" -- which is what someone who does not know the
    # vocabulary types -- had no filtering at all and got 51% senior-titled results.
    title = (title or "").lower()
    if not experience:
        return False

    # Strip the phrases where "senior" names the client group before testing seniority.
    for pattern in _EXCEPTION_PATTERNS:
        title = pattern.sub(" ", title)

    if experience == "entry level":
        # A junior marker WINS. "Junior Team Lead", "Graduate Architect" and "Trainee
        # Architect" all carry a senior word and are unambiguously entry-level posts; before
        # this override every one of them was dropped.
        if _matches_any(_JUNIOR_PATTERNS, title):
            return False
        return _matches_any(_SENIOR_PATTERNS, title)

    if experience == "senior":
        # Symmetrically, an explicit senior word wins over a junior one.
        if _matches_any(_SENIOR_PATTERNS, title):
            return False
        return _matches_any(_JUNIOR_PATTERNS, title)

    return False


def adzuna_market(country):
    """Return the Adzuna market to query for this user's country, or None if it has none."""
    # The single place the "can this source serve this user?" question is answered for Adzuna.
    # A country Adzuna does not cover has no jobs/<code>/search endpoint at all, so there is
    # nothing to call -- see config.ADZUNA_COUNTRIES for how the list was measured.
    #
    # A user whose document predates the country field falls back to the old behaviour rather
    # than losing Adzuna silently.
    code = (country or "").strip().lower()
    if not code:
        return config.DEFAULT_ADZUNA_COUNTRY
    return code if code in config.ADZUNA_COUNTRIES else None


def _narrowed_attempts(query):
    """Return the keyword strings to try for one variant: the stripped query, then at most one narrowing."""
    # ONE rule for every searching source, so there is one thing to defend in the viva.
    #
    # The first attempt is the variant with work-type words and stopwords removed. The retry,
    # if any, keeps only the words that NAME A FIELD OF WORK (_signal_terms). If the query has
    # no such word, _signal_terms returns the same tokens, the two strings are equal, and NO
    # retry is made -- the source honestly returns nothing for that variant.
    #
    # This replaced Jobicy's retry on 2026-10-13, which sent the single LONGEST word. That
    # word is usually not the meaningful one: "a job where I help people all day" retried on
    # "people", "I want to get into tech but I have no degree" on "degree", and a Pakistan
    # user got the same four interpreter jobs for both. A wrong retry is worse than no retry,
    # because the user cannot tell the results were never about their query.
    first = " ".join(_query_tokens(query)) or _adzuna_keywords(query)
    attempts = [first]
    narrowed = " ".join(_signal_terms(query))
    if narrowed and narrowed != first:
        attempts.append(narrowed)
    return attempts


def _fetch_adzuna_raw(query, app_id, app_key, count, work_type=None, market=None):
    """Call Adzuna, narrowing the keywords once if the full query matches nothing."""
    # Two attempts, capped. Adzuna's AND match means a natural-language query usually matches
    # no advert at all -- 16 of the 20 evaluation queries returned zero -- and Adzuna reports
    # that as HTTP 200 with no results, so nothing upstream could tell the query was the
    # problem. The retry sends only the words that name a field of work.
    #
    # The cap is a quota decision, not a design one: three variants times two attempts is six
    # of 250 daily calls per cold search, and the second attempt only happens when the first
    # returned nothing -- which today costs the user everything.
    ok = False
    for keywords in _narrowed_attempts(query):
        raw, attempt_ok = _adzuna_request(keywords, app_id, app_key, count, work_type, market)
        ok = ok or attempt_ok
        if raw:
            return raw, True
    return [], ok


def _adzuna_request(keywords, app_id, app_key, count, work_type=None, market=None):
    """Make one Adzuna call and return (raw results, ok)."""
    try:
        # The market is interpolated, not hardcoded. Until 2026-09-23 this read
        # ".../jobs/gb/search/1" while config.ADZUNA_COUNTRY was read from .env and consumed
        # by nothing, so setting that variable changed nothing and reported no error.
        # The value reaching this URL is always a member of config.ADZUNA_COUNTRIES, checked
        # by adzuna_market above -- it must never be raw user input.
        market = market or config.DEFAULT_ADZUNA_COUNTRY
        url = f"https://api.adzuna.com/v1/api/jobs/{market}/search/1"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": count,
            # The work-type words are removed rather than passed through. `what` is an AND
            # match, so leaving "remote" in it returns nothing at all.
            "what": keywords,
            "content-type": "application/json",
        }
        # Adzuna rejects an unknown parameter with HTTP 400, so only the three verified keys
        # in ADZUNA_WORK_TYPE_PARAMS may be added here. "remote" maps to nothing on purpose.
        params.update(ADZUNA_WORK_TYPE_PARAMS.get(work_type or "", {}))

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            # 429 is the one TC-018 names, but a 500 or a 403 leaves the user equally
            # without Adzuna data, so they are all reported the same way.
            print(f"Adzuna returned HTTP {response.status_code}")
            return [], False
        return response.json().get("results", []), True
    except Exception as e:
        print(f"Adzuna API error: {e}")
        return [], False


def _himalayas_request(keywords, country, count):
    """Make one Himalayas call and return (response or None); None means a transport error."""
    params = {"q": keywords, "limit": count}
    if country:
        params["country"] = country.upper()
    else:
        params["worldwide"] = "true"
    try:
        return requests.get(HIMALAYAS_URL, params=params, timeout=10)
    except Exception as e:
        print(f"Himalayas API error: {e}")
        return None


def _fetch_himalayas_raw(query, country=None, count=HIMALAYAS_PER_VARIANT):
    """Call Himalayas for remote jobs open to this user's country and return (raw results, ok)."""
    # `country` takes an ISO code (measured 2026-10-13: PK, GB, TR, CZ all accepted) and
    # returns jobs with NO restriction plus jobs whose restriction list names that country,
    # so eligibility is filtered server-side -- the guarantee geo=anywhere gave on Jobicy,
    # but over a pool of thousands rather than eleven. The code reaching here is always a key
    # of config.COUNTRIES (validated at registration) or empty -- never raw user input.
    #
    # A country Himalayas does not recognise is HTTP 400 "Invalid country". That switches to
    # worldwide-only jobs rather than being reported as a failure: the user still gets every
    # job open to anyone, which they can apply for.
    #
    # Rate-limited with 429 and no published number. A 429 is reported as a failure, so the
    # TC-018 banner shows; the 60-minute cache in core/agent.py keeps repeat searches off it.
    ok = False
    for keywords in _narrowed_attempts(query):
        response = _himalayas_request(keywords, country, count)
        if response is not None and response.status_code == 400 and country:
            print(f"Himalayas rejected country {country!r}; using worldwide jobs only")
            country = None
            response = _himalayas_request(keywords, country, count)
        if response is None:
            continue
        if response.status_code != 200:
            print(f"Himalayas returned HTTP {response.status_code}")
            continue
        ok = True
        try:
            jobs = response.json().get("jobs") or []
        except ValueError as e:
            print(f"Himalayas returned invalid JSON: {e}")
            jobs = []
        if jobs:
            return jobs, True
    # ok stays False only if EVERY attempt failed at the transport or HTTP level. A 200 that
    # matched nothing is an empty result, not a failed source -- TC-018 depends on that.
    return [], ok


def _filter_level(raw, title_key, experience):
    """Drop results whose title contradicts the experience level, for any source's raw shape."""
    # One function for every source; only the name of the title field differs.
    #
    # Adzuna used to be EXEMPT from this, and the reason was sound at the time: it ran a real
    # keyword search on the user's own words, so overruling it would be second-guessing a
    # genuine match. That premise died on 2026-09-26 when the keyword narrowing shipped --
    # "beginner level software engineer" narrows to "software" on the retry, so the source
    # never sees the word "beginner" and its results are no longer earned with respect to
    # level. Caught by verify_live.py: the query returned six "Lead Software Engineer".
    # Himalayas narrows the same way, so the same reasoning applies to it.
    #
    # Nothing is lost when the query WAS specific: _wrong_level only drops titles that
    # actively contradict the level, so a genuine match is untouched.
    return [j for j in raw if not _wrong_level((j.get(title_key) or "").lower(), experience)]


def fetch_variant(query, app_id, app_key, work_type=None, experience=None, country=None):
    """Fetch one variant from every source that can serve this user's country."""
    jobs = []
    failed_sources = []
    empty_sources = []

    # Adzuna is a country-market board. For a user whose country it does not cover there is no
    # endpoint to call, so it is SKIPPED rather than called and filtered -- the call would
    # spend one of 250 daily quota units fetching jobs that would reject the user on sight.
    #
    # A skipped source is reported in NEITHER failed_sources NOR empty_sources, and both
    # halves of that matter:
    #   - failed_sources drives TC-018's "Job data temporarily unavailable" banner, which
    #     would then fire on every single search a Pakistan-based user ran. Adzuna has not
    #     failed; it was never asked.
    #   - empty_sources marks a fetch as degraded in core/agent.py so it is not cached. Every
    #     such user's search would bypass the 60-minute cache forever.
    #
    # The local source comes FIRST and the remote board last, and that order is load-bearing:
    # the agent keeps the first occurrence of a duplicate, so a listing on both keeps the
    # local copy and its honest "local" badge rather than being relabelled by fetch order.
    market = adzuna_market(country)
    if market is not None:
        adzuna_raw, adzuna_ok = _fetch_adzuna_raw(
            query, app_id, app_key, ADZUNA_PER_VARIANT, work_type, market
        )
        if not adzuna_ok:
            failed_sources.append("Adzuna")
        else:
            adzuna_raw = _filter_level(adzuna_raw, "title", experience)
            if not adzuna_raw:
                # Adzuna answering "200, nothing here" is not a failure, but the caller has
                # to be able to tell it contributed nothing.
                empty_sources.append("Adzuna")
        jobs.extend(JobCard.from_adzuna(raw) for raw in adzuna_raw)

    # Himalayas serves every country: remote jobs that are unrestricted or name the user's
    # country. The display name goes to JobCard so a restriction list can be matched exactly
    # against it (models/job_card.py restriction_eligibility).
    code = (country or "").strip().lower()
    himalayas_raw, himalayas_ok = _fetch_himalayas_raw(query, code or None)
    if not himalayas_ok:
        failed_sources.append("Himalayas")
    else:
        himalayas_raw = _filter_level(himalayas_raw, "title", experience)
        if not himalayas_raw:
            empty_sources.append("Himalayas")
    country_name = config.COUNTRIES.get(code)
    jobs.extend(JobCard.from_himalayas(raw, country_name) for raw in himalayas_raw)

    # Not deduplicated here. Deduplication is across ALL variants, which only the agent can
    # see; doing a partial pass here would just be work repeated three times.
    return {"jobs": jobs, "failed_sources": failed_sources, "empty_sources": empty_sources}
