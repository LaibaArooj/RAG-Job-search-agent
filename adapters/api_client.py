"""Adzuna and Remotive HTTP access. The only module in the project that imports requests.

One fetch path, used by JobSearchAgent: fetch_variant() fetches a single query variant from
both sources and returns {"jobs": [JobCard], "failed_sources": [str], "empty_sources": [str]}.

Each source needs its own compensation, and both are this module's business under the SDD
layering rule -- nothing above here should have to know how either API misbehaves.

**Adzuna** does a real keyword search, but `what=` is an AND match over the job text, so one
work-type word empties it. Measured 2026-09-20: "junior software engineer" returns 77 results,
"remote junior software engineer" returns 0. Worse, Adzuna reports that as HTTP 200 with no
results -- a legitimate empty search, not a failure -- so nothing upstream could tell that the
query itself was the problem. _adzuna_keywords strips those words out and the work type is
passed as Adzuna's own parameter instead.

**Remotive** ignores its `search` parameter completely and returns the same fixed list for
every request, verified with no parameters at all. It is therefore fetched once and filtered
HERE, against the job title. Say this plainly in the report and in the viva: Remotive is
fetched then filtered locally. It is not an API keyword search any more.

Three signals go back, not two. A source that FAILED and a source that succeeded but returned
NOTHING are different events, and collapsing them is what hid this bug: the user saw a full
page of irrelevant jobs with no warning, because Adzuna had politely returned zero.
"""

import re

import requests

import config

# JobCard imports nothing from this package, so this cannot cycle. Kept at the top where
# PEP 8 puts it: an import that only works lower down is hiding a cycle, not avoiding one.
from models.job_card import JobCard

ADZUNA_PER_VARIANT = 10
REMOTIVE_PER_VARIANT = 15

# Jobicy, added 2026-09-23. Asked for more than Remotive's hard cap of 18 because Jobicy
# actually honours `count`, and because geo=anywhere narrows the result set before we see it.
JOBICY_PER_VARIANT = 50

# Jobicy's own value for "no geographic restriction". Sent as a request parameter, so the
# filtering happens on their side and we never pay to rank jobs the user cannot apply for.
# Measured 2026-09-23: geo=anywhere returned 100 jobs, every one of them jobGeo="Anywhere".
# Their geo vocabulary is their own -- geo=asia returns 0 -- so do not pass a country here
# without checking it first.
JOBICY_GEO_ANYWHERE = "anywhere"

# Adzuna's own work-type parameters, verified live on 2026-09-20 against a control: a made-up
# parameter returns HTTP 400, so these three are genuinely honoured rather than ignored.
#
# "remote" is deliberately absent. Adzuna has no remote filter -- `where=remote` returns 0 --
# so remote intent is served by removing the word from the keywords (which is what was
# breaking the search) and by Remotive, which is an all-remote board.
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

# Two characters is too short to be evidence of anything; "ai" would match "said".
MIN_TOKEN_LENGTH = 3

# A query word may match a job title word plus one of these endings, and nothing else. A bare
# prefix match was tried first and was too loose -- it matched "car" against "Cardiac Nurse".
# Anchoring the end to a known inflection keeps "engineer" -> "Engineering" and "develop" ->
# "Developer" while refusing the accidental ones.
_INFLECTIONS = r"(?:s|es|ed|er|ers|ing|ings|ment|ments)?"

# Title words that give a job's seniority away, used by _wrong_level below.
#
# Why this is needed on top of the title-token filter: a Remotive job titled "Senior Golang
# Developer" matches the token "developer" from an expanded variant, so it passes the topic
# test while being exactly the wrong level. That is the shape of the 2026-09-20 report --
# a beginner query returning senior roles.
_SENIOR_MARKERS = (
    "senior", "snr", "lead", "principal", "staff engineer", "head of",
    "director", "chief", "architect",
)
_JUNIOR_MARKERS = (
    "junior", "jnr", "graduate", "entry level", "entry-level", "trainee",
    "intern", "apprentice",
)


def _adzuna_keywords(query):
    """Strip work-type words from a variant, leaving keywords Adzuna's AND match can satisfy."""
    cleaned = query.lower()
    for term in _WORK_TYPE_TERMS:
        cleaned = re.sub(rf"\b{re.escape(term)}\b", " ", cleaned)
    cleaned = " ".join(cleaned.split())
    # A query that is nothing BUT work-type words ("remote work") would otherwise become an
    # empty keyword search. Falling back to the original is no worse than the old behaviour.
    return cleaned or query


def _query_tokens(query):
    """Return the meaningful words of a query, used to match Remotive jobs by title."""
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
    # Applied ONLY to Remotive, and only when a level was actually stated. Adzuna results are
    # never filtered this way -- Adzuna ran the real search, so its answers are earned and
    # overruling them would be second-guessing a genuine keyword match. Remotive ignores its
    # search parameter entirely, so its contribution is ours to justify.
    title = (title or "").lower()
    if experience == "entry level":
        return any(m in title for m in _SENIOR_MARKERS)
    if experience == "senior":
        return any(m in title for m in _JUNIOR_MARKERS)
    return False


def _filter_remotive(query, raw, experience=None):
    """Keep Remotive jobs whose TITLE matches the query and does not contradict the level."""
    # Remotive returns the same fixed list whatever is asked of it, so without this every
    # search inherits the same ~20 jobs and the ranker orders noise. Measured against that
    # list: "nurse" keeps 0, "freelance copywriter" keeps exactly "Freelance Copywriter".
    #
    # Title only, not title + description. It scored almost identically (7 kept vs 8 on a
    # test query) and it is far tighter -- a description is a long HTML advert whose
    # boilerplate matches almost anything -- and it states in one sentence.
    #
    # A word match that tolerates an inflected ending, so "engineer" matches "Engineering"
    # but "car" does not match "Cardiac" and "art" does not match "Smart".
    #
    # A query with no meaningful words left after stripping ("remote work") has nothing to
    # filter the topic on, so the feed passes the token test rather than collapsing to zero.
    # The level test below still applies to it.
    tokens = _query_tokens(query)
    kept = []
    for job in raw:
        title = (job.get("title") or "").lower()
        if _wrong_level(title, experience):
            continue
        if not tokens or any(
            re.search(rf"\b{re.escape(t)}{_INFLECTIONS}\b", title) for t in tokens
        ):
            kept.append(job)
    return kept


def _fetch_adzuna_raw(query, app_id, app_key, count, work_type=None):
    """Call Adzuna and return (raw results, ok) — ok is False only on a transport or HTTP error."""
    try:
        url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": count,
            # The work-type words are removed rather than passed through. `what` is an AND
            # match, so leaving "remote" in it returns nothing at all.
            "what": _adzuna_keywords(query),
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


def _fetch_remotive_raw(query, count):
    """Call Remotive and return (raw results, ok) — ok is False only on a transport or HTTP error."""
    # The search and limit parameters are still sent, and Remotive still ignores both. They
    # are kept so the call matches Remotive's documented contract rather than silently
    # encoding our workaround; the filtering that compensates happens in fetch_variant.
    try:
        url = "https://remotive.com/api/remote-jobs"
        response = requests.get(
            url, params={"search": query, "limit": count}, timeout=10
        )
        if response.status_code != 200:
            print(f"Remotive returned HTTP {response.status_code}")
            return [], False
        return response.json().get("jobs", []), True
    except Exception as e:
        print(f"Remotive API error: {e}")
        return [], False


def _fetch_jobicy_raw(query, count):
    """Call Jobicy for worldwide-eligible jobs and return (raw results, ok)."""
    # `tag` is an AND match like Adzuna's `what`, and it collapses just as hard. Measured
    # 2026-09-23 with geo=anywhere:
    #
    #   "junior software engineer"        ->  5      "software"     -> 50
    #   "entry level marketing no degree" ->  0      "marketing"    -> 17
    #   "something creative ... home"     ->  0      "creative"     -> 18
    #
    # So the work-type and stopword stripping that already exists for Adzuna is applied
    # first, and if the result is still empty ONE retry is made on the single longest
    # token. Two HTTP calls per variant is the cap; Jobicy publishes no rate limit and an
    # unbounded retry loop against an API whose limits are unknown is not worth the jobs.
    tokens = _query_tokens(query)
    attempts = [" ".join(tokens) or query]
    if len(tokens) > 1:
        attempts.append(max(tokens, key=len))

    ok = False
    for tag in attempts:
        try:
            response = requests.get(
                "https://jobicy.com/api/v2/remote-jobs",
                params={
                    "count": count,
                    "geo": JOBICY_GEO_ANYWHERE,
                    "tag": tag,
                },
                timeout=10,
            )
            if response.status_code != 200:
                print(f"Jobicy returned HTTP {response.status_code}")
                continue
            ok = True
            jobs = response.json().get("jobs", []) or []
            if jobs:
                return jobs, True
        except Exception as e:
            print(f"Jobicy API error: {e}")
    # ok stays False only if EVERY attempt failed at the transport or HTTP level. A 200 that
    # matched nothing is an empty result, not a failed source -- the same distinction Adzuna
    # and Remotive already report, and TC-018 depends on it.
    return [], ok


def _filter_jobicy_level(raw, experience):
    """Drop Jobicy results whose title contradicts the experience level the user asked for."""
    # Same rule and the same helper Remotive is filtered with. Jobicy's geo filter is
    # server-side but it has no level filter, so a "senior" title can still come back for an
    # entry-level search. Applied here rather than left to the ranker for the reason
    # _wrong_level documents: cosine similarity rates "junior" and "senior" as near-synonyms.
    return [j for j in raw if not _wrong_level((j.get("jobTitle") or "").lower(), experience)]


def fetch_variant(query, app_id, app_key, work_type=None, experience=None):
    """Fetch one variant from both sources, reporting failed and empty sources separately."""
    jobs = []
    failed_sources = []
    empty_sources = []

    # Remotive first. Those listings are genuinely global, and the agent keeps the FIRST
    # occurrence of a duplicate, so the order here decides which copy of a syndicated
    # listing the user ends up seeing.
    remotive_raw, remotive_ok = _fetch_remotive_raw(query, REMOTIVE_PER_VARIANT)
    if not remotive_ok:
        failed_sources.append("Remotive")
    else:
        # The compensation for Remotive ignoring its own search parameter. Without it every
        # search inherits the same fixed list and the ranker is handed noise to order.
        remotive_raw = _filter_remotive(query, remotive_raw, experience)
        if not remotive_raw:
            empty_sources.append("Remotive")
    jobs.extend(JobCard.from_remotive(raw) for raw in remotive_raw)

    adzuna_raw, adzuna_ok = _fetch_adzuna_raw(
        query, app_id, app_key, ADZUNA_PER_VARIANT, work_type
    )
    if not adzuna_ok:
        failed_sources.append("Adzuna")
    elif not adzuna_raw:
        # The signal that was missing. Adzuna answering "200, nothing here" is not a failure,
        # but it does mean the only source that genuinely searches contributed nothing, and
        # the caller has to be able to tell.
        empty_sources.append("Adzuna")
    jobs.extend(JobCard.from_adzuna(raw) for raw in adzuna_raw)

    # Jobicy last, and that ordering is load-bearing: the agent keeps the FIRST occurrence
    # of a duplicate, so putting Jobicy after Adzuna means a listing syndicated to both
    # keeps Adzuna's copy and its eligibility stays honestly "local". Putting it first would
    # relabel the same job "open worldwide" purely because of fetch order.
    jobicy_raw, jobicy_ok = _fetch_jobicy_raw(query, JOBICY_PER_VARIANT)
    if not jobicy_ok:
        failed_sources.append("Jobicy")
    else:
        jobicy_raw = _filter_jobicy_level(jobicy_raw, experience)
        if not jobicy_raw:
            empty_sources.append("Jobicy")
    jobs.extend(JobCard.from_jobicy(raw) for raw in jobicy_raw)

    # Not deduplicated here. Deduplication is across ALL variants, which only the agent can
    # see; doing a partial pass here would just be work repeated three times.
    return {"jobs": jobs, "failed_sources": failed_sources, "empty_sources": empty_sources}
