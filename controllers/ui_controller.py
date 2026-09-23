"""Search, feed, save, reject and profile routes.

Covers TC-005 to TC-018. profile() (M1), search() (M2), the save/reject pair (M3,
TC-010/TC-011/TC-013) and feed() (M3, TC-012/TC-014) are all implemented.

search() serves "/" and replaced the inline route in app.py on 2026-09-20, closing the
deferral recorded in docs/ARCHITECTURE.md § Module layout. It stays on "/" rather than moving
to "/search" because verify_auth.py asserts that "/" returns 200 to a logged-in user and 302
to an anonymous one — TC-003 and TC-005 are both measured on that URL.

Route handlers stay thin: they capture input, call JobSearchAgent or DatabaseManager, and
render a template. No requests, no PyMongo and no sentence-transformers imports here —
that is the layering rule the SDD is graded on.

Every error path renders a visible Bootstrap banner. Never a blank page, never a stack trace.
"""

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from config import (
    ADZUNA_COUNTRIES,
    CATEGORIES,
    COUNTRIES,
    EXPERIENCE_LEVELS,
    WORK_TYPES,
)
from controllers.auth_controller import check_csrf, current_username, require_auth

ui_bp = Blueprint("ui", __name__)


def _db():
    """Return the application's DatabaseManager, the only route into MongoDB."""
    return current_app.config["DB"]


def _agent():
    """Return the application's JobSearchAgent, built once at startup in app.py."""
    # Same indirection as _db(): reached through current_app.config rather than by importing
    # app, which would be a circular import. It also means the agent's collaborators are
    # constructed in exactly one place that owns process lifetime.
    return current_app.config["AGENT"]


@ui_bp.route("/profile", methods=["GET", "POST"])
@require_auth
def profile():
    """Display and update the user's skills, experience, location and work preference."""
    username = current_username()

    if request.method == "POST":
        if not check_csrf():
            flash("Your session expired. Please try again.", "error")
            return redirect(url_for("ui.profile"))

        update = {
            "skills": [
                s.strip() for s in request.form.get("skills", "").split(",") if s.strip()
            ],
            "location": request.form.get("location", "").strip(),
        }

        # Membership checks, not free text. update_profile already whitelists which *fields*
        # may be written; this whitelists the *values*, so the profile cannot become a store
        # for arbitrary strings that later reach a prompt or a query.
        experience = request.form.get("experience", "")
        if experience in EXPERIENCE_LEVELS:
            update["experience"] = experience

        # Same whitelist as registration. An unrecognised country is ignored rather than
        # stored, so the user keeps whichever one they had instead of silently losing Adzuna.
        country = request.form.get("country", "").strip().lower()
        if country in COUNTRIES:
            update["country"] = country

        update["preferred_work"] = [
            w for w in request.form.getlist("preferred_work") if w in WORK_TYPES
        ]

        try:
            _db().update_profile(username, update)
            flash("Profile updated.", "success")
        except Exception as e:
            current_app.logger.error("profile update failed: %s", e)
            flash("Could not save your profile. Please try again.", "error")

        return redirect(url_for("ui.profile"))

    try:
        user = _db().get_user(username)
    except Exception as e:
        current_app.logger.error("profile load failed: %s", e)
        flash("Could not load your profile. Please try again.", "error")
        user = {}

    return render_template(
        "profile.html",
        user=user or {},
        work_types=WORK_TYPES,
        experience_levels=EXPERIENCE_LEVELS,
        countries=COUNTRIES,
        adzuna_countries=ADZUNA_COUNTRIES,
    )


@ui_bp.route("/feed")
@require_auth
def feed():
    """Render the For You feed from the user's top-scoring categories (TC-012, TC-014; TC-005)."""
    # As thin as search(). Which categories, which jobs and what counts as empty are all
    # agent decisions -- this route only chooses the template. @require_auth is what TC-005
    # measures on this URL and is unchanged by the M3 body.
    try:
        result = _agent().build_feed(current_username())
    except Exception as e:
        # build_feed handles its own database and API failures and has no path that should
        # reach here. This is the last line before a stack trace would render, and the SRS
        # requires a banner instead of a blank page on every error path without exception.
        current_app.logger.error("feed build failed: %s", e)
        result = {
            "feed_jobs": [],
            "top_categories": [],
            "error": "Could not build your feed right now. Please try again.",
            "warning": None,
        }

    return render_template("feed.html", **result)


def _blank_page(error=None):
    """Return the same key set JobSearchAgent.run() returns, for a page with nothing to show."""
    # Mirrors JobSearchAgent._empty_result deliberately. A GET and a rejected POST hand the
    # template the identical variables a completed search does, so index.html never has to
    # test which branch produced them.
    return {
        "jobs": [],
        "query": "",
        "intent": None,
        "ai_recommendations": None,
        "error": error,
        "warning": None,
    }


@ui_bp.route("/", methods=["GET", "POST"])
@require_auth
def search():
    """Handle the search form, run JobSearchAgent and render ranked results (TC-006, TC-007,
    TC-017 empty query, TC-018 rate-limit banner)."""
    if request.method == "POST":
        if not check_csrf():
            flash("Your session expired. Please search again.", "error")
            return render_template("index.html", **_blank_page())

        # The whole pipeline lives behind one call. The route does not read the profile, does
        # not strip the query and does not decide what an empty result means — the agent owns
        # every one of those and returns the same keys on every exit path.
        result = _agent().run(current_username(), request.form.get("query", ""))
        return render_template("index.html", **result)

    # GET. agent.run() is deliberately NOT called here: with an empty query it returns
    # TC-017's "Please enter a search term", so every first visit to the search page would
    # open with an error banner. That message belongs to an empty *submit*, not to arrival.
    return render_template("index.html", **_blank_page())


# --- save / reject ------------------------------------------------------------------
#
# These two answer with JSON rather than a redirect, and that is a deliberate choice worth
# being able to state. The ranked result list is not persisted anywhere -- it exists only in
# the response that rendered it -- so a POST-redirect-GET would either lose the results the
# user is looking at or re-run the whole pipeline, including a second Groq call, for every
# click. static/js/decisions.js posts here with fetch and flips the button in place instead.
#
# The body is form-encoded, not JSON, specifically so check_csrf() works unchanged: it reads
# request.form, and a JSON body would leave request.form empty and fail every token check.
#
# No JavaScript framework is involved -- one delegated listener and fetch(), which the stack
# constraint in CLAUDE.md permits. The degradation story if JS is off is that the buttons do
# nothing; the search itself is a plain form POST and is unaffected.


def _posted_job():
    """Build the job dict the database layer expects out of the posted form fields."""
    # Read field by field from a fixed list rather than passing request.form through. The form
    # is attacker-controlled and this dict is written into the user's document; a crafted POST
    # must not be able to add keys of its own to a stored saved_jobs entry.
    return {
        "job_id": (request.form.get("job_id") or "").strip(),
        "title": (request.form.get("title") or "").strip(),
        "company": (request.form.get("company") or "").strip(),
        "location": (request.form.get("location") or "").strip(),
        "source": (request.form.get("source") or "").strip(),
        "url": (request.form.get("url") or "").strip(),
    }


def _record(decision):
    """Run one save or reject, validating the request before the database layer sees it."""
    if not check_csrf():
        return jsonify(ok=False, error="Your session expired. Please reload the page."), 400

    job = _posted_job()
    if not job["job_id"]:
        # Without an id the entry could never be deduplicated on a second save (TC-013) and
        # could never be matched against the feed later, so it is refused here rather than
        # stored as something unusable.
        return jsonify(ok=False, error="That job is missing an identifier."), 400

    category = (request.form.get("category") or "").strip().lower()
    if category not in CATEGORIES:
        # Defence in depth, not the only defence. DatabaseManager._score_path raises
        # ValueError on the same condition because the category reaches a MongoDB field path
        # -- but an unhandled ValueError reaches the user as a 500, and this is a bad request,
        # not a server fault. Checking here makes the status code tell the truth.
        return jsonify(ok=False, error="Unknown job category."), 400

    username = current_username()
    action = _db().save_job if decision == "save" else _db().reject_job

    try:
        recorded = action(username, job, category)
    except Exception as e:
        current_app.logger.error("%s failed for %s: %s", decision, username, e)
        return jsonify(ok=False, error="Could not save that right now. Please try again."), 503

    # recorded is False when this job was already in the list. That is TC-013's case and it is
    # a success, not an error: the score was incremented exactly once, by the first click. The
    # button still settles into its decided state, so a double click looks the same as one.
    return jsonify(ok=True, already=not recorded, category=category)


@ui_bp.route("/save_job", methods=["POST"])
@require_auth
def save_job():
    """Save a job to the user's list and raise that category's score by 1 (TC-010, TC-013)."""
    return _record("save")


@ui_bp.route("/reject_job", methods=["POST"])
@require_auth
def reject_job():
    """Record a rejection and lower that category's score by 1 (TC-011)."""
    return _record("reject")
