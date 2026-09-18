import requests

# JobCard imports nothing from this package, so this cannot cycle. Kept at the top where
# PEP 8 puts it: an import that only works lower down is hiding a cycle, not avoiding one.
from models.job_card import JobCard


def fetch_adzuna_jobs(query, app_id, app_key, count=10):
    """
    Fetch jobs from Adzuna API.
    Returns a list of normalized job objects.
    """
    try:
        url = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
        params = {
            "app_id": app_id,
            "app_key": app_key,
            "results_per_page": count,
            "what": query,
            "content-type": "application/json"
        }
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return []

        jobs = response.json().get("results", [])

        # Normalize to common format
        normalized = []
        for job in jobs:
            normalized.append({
                "title":       job.get("title", "Unknown Title"),
                "company":     job.get("company", {}).get("display_name", "Unknown"),
                "location":    job.get("location", {}).get("display_name", "Unknown"),
                "description": job.get("description", ""),
                "url":         job.get("redirect_url", "#"),
                "salary":      job.get("salary_min", None),
                "source":      "Adzuna"
            })
        return normalized

    except Exception as e:
        print(f"Adzuna API error: {e}")
        return []


def fetch_remotive_jobs(query, count=10):
    """
    Fetch genuinely global remote jobs from Remotive API.
    No API key required. Companies hire from anywhere worldwide.
    Returns a list of normalized job objects.
    """
    try:
        url = "https://remotive.com/api/remote-jobs"
        params = {
            "search": query,
            "limit": count
        }
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return []

        jobs = response.json().get("jobs", [])

        # Normalize to common format
        normalized = []
        for job in jobs:
            normalized.append({
                "title":       job.get("title", "Unknown Title"),
                "company":     job.get("company_name", "Unknown"),
                "location":    job.get("candidate_required_location", "Remote — Worldwide"),
                "description": job.get("description", "")[:500],
                "url":         job.get("url", "#"),
                "salary":      job.get("salary", None),
                "source":      "Remotive"
            })
        return normalized

    except Exception as e:
        print(f"Remotive API error: {e}")
        return []


def fetch_all_jobs(query, app_id, app_key):
    """
    Fetch from both APIs and combine results.
    Remotive first since those are genuinely accessible globally.
    """
    remotive_jobs = fetch_remotive_jobs(query, count=15)
    adzuna_jobs   = fetch_adzuna_jobs(query, app_id, app_key, count=10)

    all_jobs = remotive_jobs + adzuna_jobs

    # Deduplicate by title + company
    seen = set()
    unique = []
    for job in all_jobs:
        key = job['title'].lower() + job['company'].lower()
        if key not in seen:
            seen.add(key)
            unique.append(job)

    return unique

# --- variant fetch used by JobSearchAgent -----------------------------------------
#
# Everything above returns [] for a rate limit and [] for a genuine zero-result search
# alike, so a caller cannot tell them apart. TC-018 needs exactly that distinction: Adzuna
# returning 429 must produce "Job data temporarily unavailable", not "no jobs matched".
# fetch_variant is that missing signal. It reports which sources FAILED separately from
# what they returned.
#
# fetch_all_jobs above is deliberately left untouched: the live search route in app.py
# still calls it, and it is retired when that route moves into ui_controller.

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

    # Remotive first, matching fetch_all_jobs: those listings are genuinely global, and the
    # agent keeps the first occurrence of a duplicate, so ordering here decides which copy
    # of a syndicated listing the user sees.
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
