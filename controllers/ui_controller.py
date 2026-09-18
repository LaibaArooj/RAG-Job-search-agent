"""Search, feed, save, reject and profile routes.

Covers TC-005 to TC-018. Only profile() is implemented — it belongs to M1. The rest stay as
stubs tagged with the milestone that fills them in; a stub that silently returns None is how
an unimplemented function gets shipped.

The search route is still inline in app.py. It is the one fully working code path in the
project and moving it here is M2 work, recorded as a deliberate deferral in
docs/ARCHITECTURE.md.

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

from controllers.auth_controller import check_csrf, current_username, require_auth

ui_bp = Blueprint("ui", __name__)

# The work types offered at registration and on the profile form. A closed set, so a crafted
# POST cannot store arbitrary values in preferred_work.
WORK_TYPES = ("remote", "full-time", "part-time", "freelance")

EXPERIENCE_LEVELS = ("entry level", "mid level", "senior")


def _db():
    """Return the application's DatabaseManager, the only route into MongoDB."""
    return current_app.config["DB"]


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


def search():
    """Handle the search form, run JobSearchAgent and render ranked results (TC-006, TC-007,
    TC-017 empty query, TC-018 rate-limit banner)."""
    raise NotImplementedError("M2")


def save_job():
    """Save a job to the user's list and raise that category's score by 1 (TC-010, TC-013)."""
    raise NotImplementedError("M3")


def reject_job():
    """Record a rejection and lower that category's score by 1 (TC-011)."""
    raise NotImplementedError("M3")
