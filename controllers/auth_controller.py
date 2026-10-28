"""Registration, login, logout and route protection. Covers TC-001 to TC-005.

This is the only module permitted to import werkzeug.security. Passwords are stored as
Werkzeug hashes and never in plain text (SRS §3.5) — no exceptions, not even for testing.

Rewritten from the version at 5519a22, which called the deleted models.py. Four defects in
that version are deliberately not repeated, and each is marked in place below:

  1. It rendered templates/login.html, a file that has never existed in the repo, so TC-003
     and TC-004 would both have raised TemplateNotFound. The template is now written.
  2. It fell back to a hardcoded secret key when the env var was missing. A known secret key
     means any visitor can forge a signed session cookie for any username. Now fatal at
     startup instead — see app.py.
  3. It read SECRET_KEY; config.py defines FLASK_SECRET_KEY. Settled on config.SECRET_KEY as
     the single source.
  4. It passed the plain password to create_user. Hashing is the controller's job; the
     database layer receives a hash and nothing else.

CSRF is hand-rolled rather than taken from Flask-WTF, to avoid a dependency and to keep the
mechanism explainable: a random token per session, echoed in every form, compared in constant
time on every POST.
"""

import hmac
import secrets
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import config

auth_bp = Blueprint("auth", __name__)

# Short enough not to obstruct a demo, long enough to defend. SRS §3.5 says "strong
# password" without quantifying it; this is the quantification.
MIN_PASSWORD_LENGTH = 8

# One message for "no such user" and for "wrong password". Two different messages turn the
# login form into a username oracle: an attacker learns which accounts exist (TC-004).
INVALID_CREDENTIALS = "Invalid username or password."


# --- CSRF ---------------------------------------------------------------------------


def csrf_token():
    """Return this session's CSRF token, minting one on first use."""
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def check_csrf():
    """Return True if the POSTed token matches the session's, compared in constant time."""
    # compare_digest rather than == so the comparison time does not leak how many leading
    # characters were correct.
    submitted = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(expected) and hmac.compare_digest(submitted, expected)


# --- session helpers ----------------------------------------------------------------


def is_logged_in():
    """Return True if the current session identifies a logged-in user."""
    return "username" in session


def current_username():
    """Return the logged-in username, or None."""
    return session.get("username")


def require_auth(view):
    """Decorator redirecting unauthenticated requests to /login before the view runs (TC-005)."""
    # wraps preserves the function's __name__, which Flask uses as the endpoint name. Without
    # it every decorated view would register as "wrapper" and the second one would collide.
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapper


def _db():
    """Return the application's DatabaseManager, the only route into MongoDB."""
    return current_app.config["DB"]


# --- routes -------------------------------------------------------------------------


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Validate the signup form, hash the password and create the user (TC-001, TC-002)."""
    if is_logged_in():
        return redirect(url_for("ui.search"))

    if request.method == "POST":
        if not check_csrf():
            flash("Your session expired. Please try again.", "error")
            return render_template("register.html", countries=config.COUNTRIES,
                               adzuna_countries=config.ADZUNA_COUNTRIES)

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html", countries=config.COUNTRIES,
                               adzuna_countries=config.ADZUNA_COUNTRIES)

        if len(password) < MIN_PASSWORD_LENGTH:
            flash(
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", "error"
            )
            return render_template("register.html", countries=config.COUNTRIES,
                               adzuna_countries=config.ADZUNA_COUNTRIES)

        # Membership of the closed set, not free text. The country reaches an Adzuna URL
        # path, so it is whitelisted here for the same reason config.CATEGORIES is checked
        # before a category reaches a MongoDB field path.
        country = request.form.get("country", "").strip().lower()
        if country not in config.COUNTRIES:
            flash("Please choose the country you are based in.", "error")
            return render_template("register.html", countries=config.COUNTRIES,
                                   adzuna_countries=config.ADZUNA_COUNTRIES)

        profile = {
            "skills": [
                s.strip() for s in request.form.get("skills", "").split(",") if s.strip()
            ],
            "experience": request.form.get("experience", "entry level"),
            "location": request.form.get("location", "remote"),
            "country": country,
            "preferred_work": request.form.getlist("preferred_work"),
        }

        # Defect 4: the database layer never sees the plain password. Werkzeug's default is
        # pbkdf2:sha256 with a per-user random salt, so two users with the same password
        # still store different hashes.
        password_hash = generate_password_hash(password)

        try:
            created, message = _db().create_user(username, password_hash, profile)
        except Exception as e:  # Atlas unreachable — banner, never a stack trace
            current_app.logger.error("register failed: %s", e)
            flash("Service temporarily unavailable. Please try again.", "error")
            return render_template("register.html", countries=config.COUNTRIES,
                               adzuna_countries=config.ADZUNA_COUNTRIES)

        if created:
            session.clear()
            session["username"] = username
            flash("Account created. Welcome.", "success")
            return redirect(url_for("ui.search"))

        # TC-002 — the unique index rejected the insert, not an if-statement here.
        flash(message, "error")

    return render_template("register.html", countries=config.COUNTRIES,
                               adzuna_countries=config.ADZUNA_COUNTRIES)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Check submitted credentials against the stored hash and open a session (TC-003, TC-004)."""
    if is_logged_in():
        return redirect(url_for("ui.search"))

    if request.method == "POST":
        if not check_csrf():
            flash("Your session expired. Please try again.", "error")
            return render_template("login.html")

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        try:
            user = _db().get_user(username)
        except Exception as e:
            current_app.logger.error("login failed: %s", e)
            flash("Service temporarily unavailable. Please try again.", "error")
            return render_template("login.html")

        if user and check_password_hash(user.get("password", ""), password):
            # Drop any pre-existing session before granting one. If an attacker can set a
            # victim's cookie before login (session fixation), clearing here means the token
            # they planted is not the one that ends up authenticated.
            session.clear()
            session["username"] = username
            return redirect(url_for("ui.search"))

        # TC-004 — same message whether the user is absent or the password is wrong.
        flash(INVALID_CREDENTIALS, "error")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Clear the Flask session and redirect to the login page."""
    session.clear()
    return redirect(url_for("auth.login"))
