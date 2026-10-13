"""Prove the search pipeline against the REAL Adzuna, Himalayas, Groq and Atlas.

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

(Remotive and Jobicy were removed on 2026-10-13 -- both had shrunk to a handful of jobs, and
Remotive's terms forbid our call rate. Himalayas replaced them; its live contract is section 1b.)

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

        # Added 2026-09-26. Adzuna's `what=` is an AND match, so before the keyword narrowing
        # a natural-language query matched no advert at all -- 16 of the 20 evaluation queries
        # returned zero, reported as HTTP 200 with no results. This is the live proof that the
        # narrowing works against the real API rather than only against a unit test.
        natural, natural_ok = api_client._fetch_adzuna_raw(
            "paralegal position no prior experience",
            cfg.ADZUNA_APP_ID, cfg.ADZUNA_APP_KEY, 10, None, "gb",
        )
        check("a natural-language query now returns Adzuna results",
              natural_ok and len(natural) > 0)

        print("\n1b. Himalayas — the contract a non-UK seeker's results depend on")
        # Added 2026-10-13, written BEFORE it breaks, which is the lesson of Remotive and
        # Jobicy: both changed underneath this project (one stopped searching, one shrank from
        # 100 eligible jobs to 11) and each was only noticed by using the app.
        pk_raw, pk_ok = api_client._fetch_himalayas_raw("customer service", "pk")
        check("Himalayas reachable and returning results for a plain query",
              pk_ok and len(pk_raw) > 0)
        note(f"Himalayas returned {len(pk_raw)} jobs for 'customer service' as pk")

        if pk_raw:
            lists = [j.get("locationRestrictions") or [] for j in pk_raw]
            # The guarantee the eligibility badges rest on: with country=PK, every job is
            # either unrestricted or names Pakistan. If Himalayas ever starts ignoring the
            # filter -- as Remotive did with `search` -- this is what catches it.
            check("country=PK returns only unrestricted jobs or ones naming Pakistan",
                  all(not lst or "Pakistan" in lst for lst in lists))
            cards = [JobCard.from_himalayas(j, "Pakistan") for j in pk_raw]
            check("every Himalayas job badges as open or open-to-your-country",
                  all(c.eligibility in ("open", "country") for c in cards))
            check("a Himalayas job carries a usable apply link",
                  all(c.url.startswith("http") for c in cards))

        # Himalayas' `q` is an AND match like Adzuna's: a sentence returns nothing. Measured
        # through _himalayas_request, which sends the string unmodified -- this script may not
        # import requests (SDD layering), so the raw call has to come from the adapter.
        raw_sentence = api_client._himalayas_request(
            "entry level remote data analyst job in pakistan", "pk", 20)
        sentence_jobs = (raw_sentence.json().get("jobs") or []) if raw_sentence is not None \
            and raw_sentence.status_code == 200 else None
        check("a whole sentence still returns nothing from Himalayas (why we narrow)",
              sentence_jobs == [])
        if sentence_jobs:
            note("Himalayas now answers sentences — re-check whether narrowing is still needed.")
        narrowed, _ = api_client._fetch_himalayas_raw(
            "somewhere I can use my writing and actually get paid", "pk")
        check("the same kind of sentence returns jobs through the field-word retry",
              len(narrowed) > 0)

        print("\n1b2. The Groq model chain is still on the account")
        # Added 2026-09-26. Groq has retired this project's LLM twice in two weeks, and both
        # times the AI panel simply vanished -- FR-018's fallback is graceful enough to hide
        # the cause, so the second retirement went unnoticed for two days. This asks the live
        # catalogue directly, so verify_all.py says a model died BEFORE a demo rather than
        # the demo saying it.
        from groq import Groq  # noqa: E402
        from core.rag_pipeline import GROQ_MODELS  # noqa: E402

        try:
            catalogue = {m.id for m in Groq(api_key=cfg.GROQ_API_KEY).models.list().data}
        except Exception as e:
            catalogue = set()
            note(f"could not read the Groq model list: {e}")

        if catalogue:
            retired = [m for m in GROQ_MODELS if m not in catalogue]
            check("the primary model is still offered", GROQ_MODELS[0] in catalogue)
            # Reported per model rather than as one pass/fail, because losing the primary and
            # losing a spare need different reactions: one is urgent, the other is a note.
            check("every model in the fallback chain is still offered", not retired)
            if retired:
                note(f"RETIRED, update core/rag_pipeline.py GROQ_MODELS: {retired}")
            note(f"{len(catalogue)} models on the account; chain is {list(GROQ_MODELS)}")

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
            check("a source badge is shown", "Adzuna" in real or "Himalayas" in real)
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
            # Names the offending title. A check that reports only a count sends the reader
            # guessing, which cost several runs on 2026-09-26.
            offenders = [t for t in bt[:5] if any(w in t.lower() for w in SENIOR_WORDS)]
            check(f"no senior titles in the top 5 (found {n_sen}: {offenders})", n_sen == 0)
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
            # for every query, because the candidate pool was never empty. (Remotive was
            # removed on 2026-10-13; this stays to prove gibberish still finds nothing.)
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
        # assumed Adzuna was the only source that genuinely searches. Himalayas now does too
        # (Jobicy did before it), and Adzuna is skipped entirely for a user whose country it
        # cannot serve -- so the real invariant is that a cached pool contains at least one
        # SEARCHING source, whichever it happens to be. Stating it that way is also what caught
        # the bug: the old check passed for the wrong reason until a pk-profile run put a
        # Remotive-only entry in the cache.
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
