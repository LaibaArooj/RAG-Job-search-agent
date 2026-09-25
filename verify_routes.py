"""Prove the M3 save/reject routes against the live app and Atlas — TC-010, TC-011, TC-013.

Run with the dev server stopped:  python verify_routes.py

verify_db.py already asserts TC-010/011/013 at the DATA layer, by calling DatabaseManager
directly. This script asserts the same test cases through the HTTP routes the buttons
actually post to, which is a different claim: it covers the CSRF check, the category
whitelist, the JSON contract decisions.js depends on, and @require_auth. A green verify_db.py
with broken routes would have meant three test cases passing in a script and failing in the
demo — exactly the gap that TC-021 sat in until 2026-09-20.

Same test-client approach and the same check()/summary shape as verify_auth.py, so
verify_all.py can parse it. Deliberately not pytest: pytest is not in requirements.txt.

Every user it creates is named with a random suffix and deleted at the end, so it is safe to
re-run.
"""

import io
import os
import uuid

# The app refuses to start without a signing key. Supply one for this process only if .env
# has not set it, so the checks can run before that key is added.
os.environ.setdefault("FLASK_SECRET_KEY", "verify-routes-only-not-for-serving")

import app as flask_app  # noqa: E402  (must follow the env default above)
from core.agent import JobSearchAgent  # noqa: E402
from core.intent_parser import classify_category  # noqa: E402

PASSED = []
FAILED = []

# A job in the shape decisions.js posts: the data-* attributes off one rendered card.
JOB = {
    "job_id": "verify-routes-0001",
    "title": "Technical Writer",
    "company": "Example Ltd",
    "location": "Remote",
    "source": "Remotive",
    "url": "https://example.com/job/1",
    "category": "writing",
}

OTHER_JOB = {
    "job_id": "verify-routes-0002",
    "title": "Backend Developer",
    "company": "Example Ltd",
    "location": "London",
    "source": "Adzuna",
    "url": "https://example.com/job/2",
    "category": "technology",
}


def check(label, condition, detail=""):
    """Record one assertion and print it as it happens."""
    (PASSED if condition else FAILED).append(label)
    suffix = f"  [{detail}]" if detail and not condition else ""
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{suffix}")


def csrf_from(client, path):
    """Fetch a page and pull the CSRF token out of its form."""
    html = client.get(path).get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def score(db, username, category):
    """Return one category's current score, or 0 if it has never been touched."""
    user = db.get_user(username) or {}
    return (user.get("category_scores") or {}).get(category, 0)


def post(client, path, job, token):
    """Post one decision the way decisions.js does, and return (status, parsed json)."""
    data = dict(job)
    if token is not None:
        data["csrf_token"] = token
    response = client.post(path, data=data)
    try:
        return response.status_code, response.get_json()
    except Exception:
        return response.status_code, None


def main():
    """Run every M3 route check in order and print a summary."""
    client_app = flask_app.app
    client_app.config["TESTING"] = True
    db = client_app.config["DB"]

    username = f"verify_{uuid.uuid4().hex[:10]}"
    password = "correct-horse-battery"

    try:
        print("\n1. Categorisation — the value the routes score")
        # Offline and pure, but it belongs here: a category that is not in config.CATEGORIES
        # is rejected by the route with a 400, so the classifier and the whitelist agreeing
        # is what makes every check below reachable at all.
        check(
            "a writing title classifies as writing",
            classify_category("Senior Technical Writer") == "writing",
            classify_category("Senior Technical Writer"),
        )
        check(
            "a nursing title classifies as healthcare",
            classify_category("Registered Nurse, ICU") == "healthcare",
            classify_category("Registered Nurse, ICU"),
        )
        check(
            "unmatched text falls back to the intent's category",
            classify_category("Zxqv Wibble Officer", "design") == "design",
        )
        check(
            "unmatched text with no fallback lands in other",
            classify_category("Zxqv Wibble Officer") == "other",
        )
        check(
            "a fallback outside CATEGORIES is refused, not passed through",
            classify_category("Zxqv Wibble Officer", "'; drop") == "other",
        )

        classified = JobSearchAgent.classify(
            [
                {"title": "Content Writer", "description": ""},
                {"title": "Zxqv Officer", "description": "nothing useful here"},
            ],
            "technology",
        )
        check(
            "agent.classify writes a category onto every job",
            [j["category"] for j in classified] == ["writing", "technology"],
            str([j["category"] for j in classified]),
        )

        print("\n2. Authentication and CSRF")
        with client_app.test_client() as c:
            r = c.post("/save_job", data=JOB)
            check("TC-005  /save_job redirects when logged out", r.status_code == 302)
            check(
                "redirect target is /login",
                "/login" in r.headers.get("Location", ""),
                r.headers.get("Location", ""),
            )
            r = c.post("/reject_job", data=OTHER_JOB)
            check("/reject_job redirects when logged out", r.status_code == 302)
            r = c.get("/feed")
            check("TC-005  /feed redirects when logged out", r.status_code == 302)
            check(
                "the feed's redirect target is /login",
                "/login" in r.headers.get("Location", ""),
                r.headers.get("Location", ""),
            )

        # Register and log in, then reuse this client for the rest.
        client = client_app.test_client()
        token = csrf_from(client, "/register")
        client.post(
            "/register",
            data={"csrf_token": token, "username": username, "password": password,
                  "country": "gb"},
        )
        check("throwaway user registered", db.get_user(username) is not None)

        print("\n2b. The For You feed before any preference exists")
        # Run BEFORE the saves below, while this user still has no positive category score.
        # build_feed returns at that point without fetching, so this check costs no Adzuna
        # quota -- which is what lets verify_all.py go on listing this script as free.
        feed_html = client.get("/feed").get_data(as_text=True)
        check("a fresh user's feed returns the empty state",
              "No personalised feed yet" in feed_html)
        check("the M3 placeholder is gone",
              "arrives in milestone M3" not in feed_html)
        check("no job cards render on an empty feed",
              "js-decision-group" not in feed_html)
        check("the feed page still renders its nav, not a stack trace",
              "Traceback" not in feed_html and "For You" in feed_html)

        status, payload = post(client, "/save_job", JOB, token=None)
        check("POST without a CSRF token is rejected with 400", status == 400, str(status))
        check(
            "the rejection says so in JSON, not HTML",
            isinstance(payload, dict) and payload.get("ok") is False,
            str(payload),
        )
        check("no score moved on the rejected post", score(db, username, "writing") == 0)

        print("\n3. Validation")
        token = csrf_from(client, "/")

        bad_category = dict(JOB, category="adzuna")
        status, payload = post(client, "/save_job", bad_category, token)
        # This is the exact shape feed.html used to post before 2026-09-21: category was the
        # source name lowercased, which is not in CATEGORIES.
        check(
            "a category outside CATEGORIES is a 400, not a 500",
            status == 400,
            str(status),
        )
        check(
            "the field-path injection guard is never reached with a bad value",
            isinstance(payload, dict) and payload.get("ok") is False,
            str(payload),
        )

        status, payload = post(client, "/save_job", dict(JOB, category="writing.$ne"), token)
        check("a category carrying a field path is refused", status == 400, str(status))

        status, payload = post(client, "/save_job", dict(JOB, job_id=""), token)
        check("a job with no job_id is refused", status == 400, str(status))
        check("still nothing saved", len(db.get_user(username).get("saved_jobs", [])) == 0)

        print("\n4. Save — TC-010")
        status, payload = post(client, "/save_job", JOB, token)
        check("save returns 200", status == 200, str(status))
        check("save returns ok", isinstance(payload, dict) and payload.get("ok") is True)
        check("save reports it was not already recorded", payload.get("already") is False)
        check(
            "TC-010  writing score is +1",
            score(db, username, "writing") == 1,
            str(score(db, username, "writing")),
        )
        saved = db.get_user(username).get("saved_jobs", [])
        check("saved_jobs holds one entry", len(saved) == 1, str(len(saved)))
        check(
            "the stored entry keeps the classified category, not the source name",
            saved and saved[0].get("category") == "writing",
            str(saved[0].get("category")) if saved else "no entry",
        )
        check(
            "the stored entry carries only the whitelisted fields",
            saved
            and set(saved[0]) == {
                "job_id", "title", "company", "category",
                "location", "source", "source_url", "saved_at",
            },
            str(sorted(saved[0])) if saved else "no entry",
        )

        # The saved entry renames the job's `url` to `source_url` on the way into Mongo, so
        # the profile page is reading a DIFFERENT key from the one index.html and feed.html
        # read off a live JobCard. Until 2026-09-22 profile.html asked for job.url, which does
        # not exist on a stored entry; Jinja rendered the undefined as "" and the browser
        # resolved href="" to the current document, so "View" reloaded /profile. Asserting on
        # the full href rather than the bare URL is deliberate -- the URL alone would still be
        # found in the page if the attribute were empty and the link text held it.
        profile_html = client.get("/profile").get_data(as_text=True)
        check(
            "a saved job's View link carries its source_url, not an empty href",
            f'href="{JOB["url"]}"' in profile_html,
            "href is empty or missing" if JOB["url"] not in profile_html else "URL present but not in href",
        )

        print("\n5. Same job saved twice — TC-013")
        status, payload = post(client, "/save_job", JOB, token)
        check("a second save still returns 200", status == 200, str(status))
        check(
            "TC-013  it reports already=true rather than failing",
            payload.get("ok") is True and payload.get("already") is True,
            str(payload),
        )
        check(
            "TC-013  score is still +1, not +2",
            score(db, username, "writing") == 1,
            str(score(db, username, "writing")),
        )
        check(
            "TC-013  saved_jobs still holds one entry",
            len(db.get_user(username).get("saved_jobs", [])) == 1,
        )

        print("\n6. Reject — TC-011")
        status, payload = post(client, "/reject_job", OTHER_JOB, token)
        check("reject returns 200", status == 200, str(status))
        check("reject returns ok", payload.get("ok") is True)
        check(
            "TC-011  technology score is -1",
            score(db, username, "technology") == -1,
            str(score(db, username, "technology")),
        )
        check(
            "rejected_jobs stores the job_id (Deviation 4)",
            db.get_user(username).get("rejected_jobs") == [OTHER_JOB["job_id"]],
            str(db.get_user(username).get("rejected_jobs")),
        )
        check(
            "a rejected job does not land in saved_jobs",
            len(db.get_user(username).get("saved_jobs", [])) == 1,
        )

        status, payload = post(client, "/reject_job", OTHER_JOB, token)
        check(
            "a second reject reports already=true and does not double-decrement",
            payload.get("already") is True and score(db, username, "technology") == -1,
            str(score(db, username, "technology")),
        )

        print("\n7. The rendered buttons")
        # The routes above are only reachable if the page actually renders buttons wired to
        # them. A green script with unwired markup is exactly the gap TC-021 sat in until
        # 2026-09-20, so the markup is asserted here rather than assumed.
        html = client.get("/").get_data(as_text=True)
        check("the CSRF token is exposed as a meta tag for fetch", 'name="csrf-token"' in html)
        check("decisions.js is loaded", "js/decisions.js" in html)

        with client_app.test_request_context("/"):
            from flask import render_template, session

            session["csrf_token"] = "token-for-render-only"
            card_html = render_template(
                "index.html",
                jobs=[dict(JOB, description="writes documentation", normalized_score=93.4)],
                query="writing job",
                intent=None,
                ai_recommendations=None,
                error=None,
                warning=None,
            )

        check("a job card renders a decision group", "js-decision-group" in card_html)
        check("Save and Reject buttons render",
              ">Save<" in card_html and ">Reject<" in card_html)
        check("the card carries the classified category, not the source",
              'data-category="writing"' in card_html)
        check("the card carries the job_id the routes deduplicate on",
              'data-job-id="' + JOB["job_id"] + '"' in card_html)
        # feed.html used to post category="{{{{ job.source | lower }}}}", which is not in
        # CATEGORIES -- every click would have been a 400 (or, before the route validated,
        # a 500 out of _score_path).
        feed_src = io.open("templates/feed.html", encoding="utf-8").read()
        check("feed.html no longer posts the source name as a category",
              "job.source | lower" not in feed_src)
        # As of 2026-09-25 both templates render cards through templates/_job_card.html, so
        # this asserts the DUPLICATION IS GONE rather than that two copies happen to agree.
        # The job.source|lower bug above existed because there were two copies and only one
        # was fixed; with one definition that particular drift cannot recur.
        index_src = io.open("templates/index.html", encoding="utf-8").read()
        check("feed.html renders cards through the shared macro",
              "_job_card.html" in feed_src and "job_card(" in feed_src)
        check("index.html renders cards through the same macro",
              "_job_card.html" in index_src and "job_card(" in index_src)
        check("neither template still carries its own copy of the decision markup",
              "js-decision-group" not in feed_src and "js-decision-group" not in index_src)
        check("feed.html still loads decisions.js", "js/decisions.js" in feed_src)

        # Rendered directly rather than through the route, so a populated feed can be
        # asserted without the live fetch a real one would trigger.
        with client_app.test_request_context("/feed"):
            from flask import render_template, session

            session["csrf_token"] = "token-for-render-only"
            feed_html = render_template(
                "feed.html",
                feed_jobs=[dict(JOB, description="writes documentation",
                                normalized_score=93.4, match_band="Top Match")],
                top_categories=["writing"],
                error=None,
                warning=None,
            )

        check("FR-019  the feed renders a match-quality badge",
              "Top Match" in feed_html)
        check("the feed renders the top-category badges", ">writing<" in feed_html)
        check("a feed card renders a decision group", "js-decision-group" in feed_html)
        check("the feed card carries the classified category",
              'data-category="writing"' in feed_html)
        check("a populated feed shows no empty-state message",
              "No personalised feed yet" not in feed_html)

        print("\n7b. TC-009 — the AI band is hidden when Groq is unavailable")
        # verify_agent.py proves RAGPipeline returns None on an outage and that the agent
        # passes that through. TC-009's remaining claim is about the PAGE: "AI section hidden
        # gracefully, raw ranked results shown, no crash". That is a rendering fact, so it is
        # asserted on rendered HTML. Rendered directly rather than POSTed, so it costs no
        # Adzuna quota and no Groq call -- the same trick the feed check above uses.
        ranked = [dict(JOB, description="writes documentation", normalized_score=91.2,
                       eligibility="open", candidate_location="Worldwide")]

        with client_app.test_request_context("/"):
            from flask import render_template, session

            session["csrf_token"] = "token-for-render-only"
            page_args = dict(jobs=ranked, query="technical writer", intent=None,
                             error=None, warning=None)
            down_html = render_template("index.html", ai_recommendations=None, **page_args)
            # ai_recommendations is a list of REAL job dicts carrying ai_reason since
            # 2026-09-25, not prose -- the panel renders live cards with working buttons.
            up_html = render_template(
                "index.html",
                ai_recommendations=[dict(ranked[0], ai_reason="Matches your search.")],
                **page_args
            )

        check("TC-009  the AI Recommendations band is absent when Groq failed",
              "AI Recommendations" not in down_html)
        check("TC-009  the ranked results are still rendered",
              JOB["title"] in down_html and "js-decision-group" in down_html)
        check("TC-009  the page shows no error banner for an LLM outage",
              "alert-danger" not in down_html)
        check("TC-009  no stack trace reaches the page", "Traceback" not in down_html)
        # The control. Without it, a template that never rendered the band under ANY
        # condition would pass every assertion above -- the check would be measuring a typo
        # in the section name rather than the fallback.
        check("TC-009  the same page DOES show the band when Groq answers",
              "AI Recommendations" in up_html)

        # Issue #2 from the 2026-09-23 browser session: the AI picks were a <pre> block, so
        # the three most prominent jobs on the page were the only ones you could not act on.
        check("an AI pick renders as a real card with a decision group",
              up_html.count("js-decision-group") == 2)
        check("the AI pick carries the job_id the routes deduplicate on",
              up_html.count('data-job-id="' + JOB["job_id"] + '"') == 2)
        check("the AI pick's Save and Reject buttons render",
              up_html.count(">Save<") == 2 and up_html.count(">Reject<") == 2)
        check("the AI pick shows the model's reason", "Matches your search." in up_html)
        check("the reason is labelled as AI-generated",
              'class="badge bg-warning text-dark me-1">AI<' in up_html)
        # Compact: the same three jobs appear again in full below, so repeating the
        # description would make the user scroll past identical text twice.
        check("the AI card omits the description the ranked card shows",
              up_html.count("writes documentation") == 1)

        print("\n8. The scores the feed reads")
        tops = db.get_top_categories(username)
        check("TC-012  top categories include writing", "writing" in tops, str(tops))
        check("TC-012  negatively scored technology excluded", "technology" not in tops, str(tops))

    finally:
        print("\n9. Cleanup")
        try:
            db.users.delete_many({"username": username})
            check("throwaway user removed", db.get_user(username) is None)
        except Exception as e:
            check(f"cleanup failed: {e}", False)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for label in FAILED:
        print(f"  FAILED: {label}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
