import requests


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