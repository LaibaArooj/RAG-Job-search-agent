"""Search, feed, save, reject and profile routes.

Covers TC-005 to TC-018. profile() (M1) and search() (M2) are implemented; save_job and
reject_job stay as stubs tagged with the milestone that fills them in, because a stub that
silently returns None is how an unimplemented function gets shipped.

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
    redirect,
    render_template,
    request,
    url_for,
)

from config import EXPERIENCE_LEVELS, WORK_TYPES
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
    )


@ui_bp.route("/feed")
@require_auth
def feed():
    """Render the For You feed from the user's top-scoring categories (TC-012, TC-014; TC-005)."""
    # Registered and protected in M1 so TC-005 — /feed while logged out redirects to /login —
    # can be tested now. The ranking itself is M3; the placeholder is explicit rather than an
    # empty page that could be mistaken for a working but empty feed.
    return render_template(
        "feed.html",
        feed_jobs=[],
        top_categories=[],
        user=None,
        pending_message="The personalised feed arrives in milestone M3.",
    )


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


def save_job():
    """Save a job to the user's list and raise that category's score by 1 (TC-010, TC-013)."""
    raise NotImplementedError("M3")


def reject_job():
    """Record a rejection and lower that category's score by 1 (TC-011)."""
    raise NotImplementedError("M3")
