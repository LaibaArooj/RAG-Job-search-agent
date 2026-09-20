"""Adzuna and Remotive HTTP access. The only module in the project that imports requests.

One fetch path, used by JobSearchAgent: fetch_variant() fetches a single query variant from
both sources and returns {"jobs": [JobCard], "failed_sources": [str]}.

The failed_sources list is the signal TC-018 needs. The earlier fetch_adzuna_jobs /
fetch_remotive_jobs / fetch_all_jobs trio returned [] for a rate limit and [] for a genuine
zero-result search alike, so the caller could not tell "come back later" from "search for
something else". All three were deleted on 2026-09-20 once the inline route in app.py stopped
calling them — they also still carried the pre-JobCard inline normalising, which is the code
that once rendered Python dicts into the page. They are preserved in git history; keeping two
fetch paths alive is how the two diverge.
"""

import requests

# JobCard imports nothing from this package, so this cannot cycle. Kept at the top where
# PEP 8 puts it: an import that only works lower down is hiding a cycle, not avoiding one.
from models.job_card import JobCard

ADZUNA_PER_VARIANT = 10
REMOTIVE_PER_VARIANT = 15


def _fetch_adzuna_raw(query, app_id, app_key, count):
    """Call Adzuna and return (raw results, ok) — ok is False only on a transport or HTTP error."""
    try:
        url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": count,
            "what": query,
            "content-type": "application/json",
        }
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


def fetch_variant(query, app_id, app_key):
    """Fetch one query variant from both sources, reporting failed sources separately (TC-018)."""
    jobs = []
    failed_sources = []

    # Remotive first. Those listings are genuinely global, and the agent keeps the FIRST
    # occurrence of a duplicate, so the order here decides which copy of a syndicated
    # listing the user ends up seeing.
    remotive_raw, remotive_ok = _fetch_remotive_raw(query, REMOTIVE_PER_VARIANT)
    if not remotive_ok:
        failed_sources.append("Remotive")
    jobs.extend(JobCard.from_remotive(raw) for raw in remotive_raw)

    adzuna_raw, adzuna_ok = _fetch_adzuna_raw(query, app_id, app_key, ADZUNA_PER_VARIANT)
    if not adzuna_ok:
        failed_sources.append("Adzuna")
    jobs.extend(JobCard.from_adzuna(raw) for raw in adzuna_raw)

    # Not deduplicated here. Deduplication is across ALL variants, which only the agent can
    # see; doing a partial pass here would just be work repeated three times.
    return {"jobs": jobs, "failed_sources": failed_sources}
