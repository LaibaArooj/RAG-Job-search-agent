"""Prove the search pipeline against the REAL Adzuna, Remotive, Groq and Atlas.

Run with the dev server stopped:  python verify_live.py

This is the one script that is deliberately NOT offline. verify_agent.py stubs every
collaborator, which is why it runs in a second and costs no quota — but that also means it
proves the logic and nothing whatsoever about how the live APIs behave. Both of the real
defects found on 2026-09-20 were invisible to it:

  - Remotive had stopped honouring its `search` parameter and was returning the same fixed
    list for every query, so every search inherited ~20 irrelevant jobs.
  - Adzuna's `what=` is an AND keyword match, so one work-type word ("remote") emptied the
    search — and Adzuna reports that as HTTP 200 with no results, not as a failure.

verify_agent.py passed 57/57 throughout both. That is the gap this script exists to close.

Uses Flask's test client rather than a browser, exactly as verify_auth.py does, so it needs
no running server and no new dependency — but it renders the real templates and makes the
real outbound calls. The throwaway user it creates is deleted at the end.

COST: roughly a dozen Adzuna requests out of the 250/day free allowance, and several Groq
calls. Run it deliberately, not in a loop, and not five minutes before a demo.
"""

import os
import re
import sys
import uuid

# The Windows console defaults to cp1252, which cannot encode the em dashes and
# arrows these scripts print, and an encoding crash midway through a check run is a
# uniquely unhelpful failure.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# The app refuses to start without a signing key. Supply one for this process only if .env
# has not set it, so the checks can run before that key is added.
os.environ.setdefault("FLASK_SECRET_KEY", "verify-live-only-not-for-serving")

import app as flask_app  # noqa: E402  (must follow the env default above)
import config as cfg  # noqa: E402
from adapters import api_client  # noqa: E402
from core import agent as agent_module  # noqa: E402
from models.job_card import JobCard  # noqa: E402

PASSED = []
FAILED = []
NOTES = []

# Title words used only to judge whether a result set is at the right seniority. This is the
# checking script's own yardstick, deliberately wider than api_client._SENIOR_MARKERS, so a
# result that slipped through the filter is still counted here rather than excused by it.
SENIOR_WORDS = ("senior", "snr", "lead", "principal", "staff", "head of", "architect",
                "director", "chief", "manager")


def check(label, condition):
    """Record one assertion and print it as it happens."""
    (PASSED if condition else FAILED).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")


def note(text):
    """Record something worth seeing that is not a pass/fail condition."""
    NOTES.append(text)
    print(f"  ..    {text}")


def csrf_from(client, path):
    """Fetch a page and pull the CSRF token out of its form."""
    html = client.get(path).get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def search(client, query):
    """POST a search and return the rendered HTML."""
    return client.post(
        "/", data={"csrf_token": csrf_from(client, "/"), "query": query}
    ).get_data(as_text=True)


def titles_in(html):
    """Pull the rendered job titles out of the results page, in ranked order."""
    return [t.strip() for t in re.findall(r'class="card-title mb-0">([^<]+)<', html)]


def senior_count(titles):
    """Count how many of these titles advertise a senior role."""
    return sum(1 for t in titles if any(w in t.lower() for w in SENIOR_WORDS))


def main():
    """Run every live check in order and print a summary."""
    client_app = flask_app.app
    client_app.config["TESTING"] = True
    db = client_app.config["DB"]

    username = f"live_{uuid.uuid4().hex[:10]}"
    password = "correct-horse-battery"

    try:
        print("\n1. The two API contracts this project depends on")
        # Checked directly, because every higher-level result below is meaningless if these
        # two facts have changed again. An API that quietly alters its behaviour is exactly
        # what caused both 2026-09-20 defects.
        plain, plain_ok = api_client._fetch_adzuna_raw(
            "junior software engineer", cfg.ADZUNA_APP_ID, cfg.ADZUNA_APP_KEY, 10
        )
        check("Adzuna reachable and returning results for a plain query",
              plain_ok and len(plain) > 0)

        # The fix, end to end: a query carrying a work-type word now returns results, where
        # before 2026-09-20 it returned none. Note this goes through _fetch_adzuna_raw, which
        # applies the stripping — that is the point, and it is why this cannot double as a
        # test of Adzuna's raw AND behaviour.
        #
        # That raw behaviour is deliberately NOT re-measured here: doing so needs an
        # unmodified HTTP call, and adapters/api_client.py is the only module in this project
        # permitted to import requests. The measurement (78 results without "remote", 0 with
        # it) is recorded in docs/CHANGELOG.md and reproducible with a one-off script.
        with_remote, ok_remote = api_client._fetch_adzuna_raw(
            "remote junior software engineer", cfg.ADZUNA_APP_ID, cfg.ADZUNA_APP_KEY, 10
        )
        check("a work-type word no longer empties an Adzuna search", ok_remote and with_remote)
        check("_adzuna_keywords is what removes it",
              api_client._adzuna_keywords("remote junior software engineer")
              == "junior software engineer")
        check("an ordinary query is left untouched",
              api_client._adzuna_keywords("junior software engineer")
              == "junior software engineer")

        rem_a, ok_a = api_client._fetch_remotive_raw("nurse", 15)
        rem_b, ok_b = api_client._fetch_remotive_raw("software engineer", 15)
        check("Remotive reachable", ok_a and ok_b)
        same_feed = [j.get("title") for j in rem_a] == [j.get("title") for j in rem_b]
        check("Remotive still ignores `search` (why we filter it locally)", same_feed)
        if not same_feed:
            note("Remotive appears to honour `search` again — re-check whether the local "
                 "filter in api_client is still the right call, and update the docs.")

        kept_nurse = api_client._filter_remotive("nurse", rem_a)
        kept_dev = api_client._filter_remotive("software developer engineer", rem_b)
        check("the local filter drops an unrelated feed entirely", len(kept_nurse) == 0)
        note(f"Remotive feed {len(rem_b)} jobs, {senior_count([j.get('title','') for j in rem_b])} "
             f"senior-titled; a developer query keeps {len(kept_dev)}")

        entry_kept = api_client._filter_remotive(
            "software developer engineer", rem_b, "entry level"
        )
        check("an entry-level query keeps no senior-titled Remotive job",
              senior_count([j.get("title", "") for j in entry_kept]) == 0)

        print("\n1b. Jobicy — the contract the eligibility work depends on")
        # Added 2026-09-25. Jobicy shipped on 2026-09-23 and nothing in the live suite
        # exercised it, so the source that supplies most of a non-UK user's results could
        # have gone down without any script noticing. Adzuna and Remotive each got a section
        # here only after they broke; this one is written before that happens.
        jobicy_raw, jobicy_ok = api_client._fetch_jobicy_raw("developer", 25)
        check("Jobicy reachable and returning results for a plain query",
              jobicy_ok and len(jobicy_raw) > 0)

        if jobicy_raw:
            geos = {(j.get("jobGeo") or "").strip().lower() for j in jobicy_raw}
            # The whole point of the source: geo=anywhere filters eligibility SERVER-side, so
            # we never pay to rank jobs the user cannot apply for. If Jobicy ever starts
            # ignoring it -- as Remotive did with `search` -- this is what catches it.
            check("geo=anywhere returns only unrestricted jobs",
                  all("anywhere" in g or "worldwide" in g for g in geos))
            cards = [JobCard.from_jobicy(j) for j in jobicy_raw]
            check("every Jobicy job normalises to an eligibility bucket",
                  all(c.eligibility in ("open", "regional", "local", "unknown") for c in cards))
            check("Jobicy jobs come back marked open",
                  all(c.eligibility == "open" for c in cards))
            check("a Jobicy job carries a usable apply link",
                  all(c.url.startswith("http") for c in cards))

        # Jobicy's tag is an AND match that collapses on long queries, which is why
        # _fetch_jobicy_raw retries on the longest token. Proven against the real API here
        # rather than assumed, because the retry is invisible when it works.
        long_raw, _ = api_client._fetch_jobicy_raw("entry level marketing no degree", 25)
        check("a long query still returns results via the token retry", len(long_raw) > 0)

        print("\n1c. Adzuna is skipped for a country it has no market for")
        # The rule the whole country feature rests on, checked against the live API rather
        # than against config: if Adzuna ever adds a pk market, this tells us.
        check("adzuna_market maps the user's own country to None",
              api_client.adzuna_market("pk") is None)
        check("and maps a covered country to itself", api_client.adzuna_market("gb") == "gb")
        pk_result = api_client.fetch_variant(
            "developer", cfg.ADZUNA_APP_ID, cfg.ADZUNA_APP_KEY, country="pk"
        )
        pk_sources = {c.source for c in pk_result["jobs"]}
        check("a pk search returns no Adzuna listings at all",
              "Adzuna" not in pk_sources)
        # The subtle half: a skipped source must not look like an outage, or TC-018's banner
        # would fire on every search this user ever runs.
        check("the skipped source is not reported as failed",
              "Adzuna" not in pk_result["failed_sources"])
        check("nor as empty, which would stop the fetch being cached",
              "Adzuna" not in pk_result["empty_sources"])
        check("a pk search still finds jobs", len(pk_result["jobs"]) > 0)

        print("\n2. Account and search page")
        with client_app.test_client() as c:
            c.post("/register", data={
                "csrf_token": csrf_from(c, "/register"),
                "username": username, "password": password,
                # gb, not pk: this script asserts on Adzuna behaviour, and a pk profile
                # would skip Adzuna entirely and the assertions would have nothing to read.
                "country": "gb",
                "skills": "Python, Flask",
                # Deliberately MID level: the 2026-09-20 report was a mid-level profile
                # searching for beginner work, where the profile fought the query.
                "experience": "mid level",
                "location": "Remote", "preferred_work": ["remote"],
            })
            check("registration opened a session", c.get("/").status_code == 200)

            home = c.get("/").get_data(as_text=True)
            check("GET / renders with no error banner", "alert-danger" not in home)
            check("GET / does not show the empty-query message (TC-017 is about submitting)",
                  "Please enter a search term" not in home)

            print("\n3. TC-017 — empty submit")
            empty = search(c, "   ")
            check("TC-017  the SRS message is shown", "Please enter a search term" in empty)
            check("TC-017  no job cards rendered", empty.count("% match") == 0)

            print("\n4. TC-006 — a real search returns ranked, relevant results")
            real = search(c, "python developer")
            t = titles_in(real)
            check("results rendered", len(t) > 0)
            check("match badges rendered", "% match" in real)
            check("a source badge is shown", "Adzuna" in real or "Remotive" in real)
            # The descendant of a real bug: Adzuna nests company and location, and passing
            # them through raw once rendered Python dicts into the page.
            check("no raw Python dict or nested API field leaked into the page",
                  "{'" not in real and "display_name" not in real)
            if "AI Recommendations" in real:
                check("TC-008  the AI Recommendations panel rendered", True)
            else:
                # FR-018: a Groq failure must cost the explanation and nothing else.
                check("FR-018  Groq failed but the ranked results still rendered", len(t) > 0)
                note("AI panel hidden — Groq was unavailable. That is the designed fallback, "
                     "not a failure, but do not demo in this state if it persists.")

            print("\n5. The 2026-09-20 report — a beginner query must not return senior jobs")
            beg = search(c, "beginner level software engineer")
            bt = titles_in(beg)
            n_sen = senior_count(bt[:5])
            check("results were returned", len(bt) > 0)
            check(f"no senior titles in the top 5 (found {n_sen})", n_sen == 0)
            for title in bt[:5]:
                note(f"top5: {title[:56]}")

            print("\n6. The same filter must work upwards, or it is just a junior bias")
            sen = search(c, "senior python developer")
            st = titles_in(sen)
            check("results were returned", len(st) > 0)
            check(f"senior titles DO appear for a senior query (found {senior_count(st[:5])})",
                  senior_count(st[:5]) > 0)

            print("\n7. TC-018 — 'no results' is reachable again")
            # It was dead code in production for as long as Remotive returned its fixed list
            # for every query, because the candidate pool was never empty.
            junk = search(c, "qwertyuiop zxcvbnm asdfgh")
            check("TC-018  'No jobs matched that search.' is shown",
                  "No jobs matched that search." in junk)
            check("TC-018  it is NOT the source-outage message",
                  "Job data temporarily unavailable" not in junk)
            check("no job cards rendered for gibberish", junk.count("% match") == 0)

        print("\n8. TC-021 — query expansion really happened")
        cached = list(db.db["job_cache"].find({}))
        check("the job cache holds more than one variant (expansion is live)", len(cached) > 1)
        # The degraded state that made the 2026-09-20 bug persist for an hour at a time.
        #
        # Restated 2026-09-25. This used to read "no entry built from Remotive alone", which
        # assumed Adzuna was the only source that genuinely searches. Jobicy now does too,
        # and Adzuna is skipped entirely for a user whose country it cannot serve -- so the
        # real invariant is that a cached pool contains at least one SEARCHING source,
        # whichever it happens to be. Stating it that way is also what caught the bug: the
        # old check passed for the wrong reason until a pk-profile run put a Remotive-only
        # entry in the cache.
        unsearched = [
            d for d in cached
            if d.get("results")
            and not ({r.get("source") for r in d["results"]} & set(agent_module.SEARCHING_SOURCES))
        ]
        check("no cached entry was built without a searching source", not unsearched)
        note(f"{len(cached)} cached variants, keyed per phrasing")

    finally:
        print("\n9. Cleanup")
        try:
            db.users.delete_one({"username": username})
            check("throwaway user removed", db.get_user(username) is None)
        except Exception as e:
            check(f"throwaway user removed (cleanup failed: {e})", False)

    print("\n" + "=" * 70)
    print(f"{len(PASSED)} passed, {len(FAILED)} failed")
    for f in FAILED:
        print(f"  FAILED: {f}")
    print("=" * 70)
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
