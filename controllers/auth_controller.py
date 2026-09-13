"""Registration, login, logout and route protection.

STUB — filled in during M1. Covers TC-001 to TC-005.

A working version of these routes exists in git history at 5519a22 and is the starting
point when M1 resumes; it needs rewiring onto adapters/db_manager.py rather than the
deleted models.py.

This is the only module permitted to import werkzeug.security. Passwords are stored as
Werkzeug hashes and never in plain text (SRS §3.5) — no exceptions, not even for testing.
Every form posts a CSRF token.
"""


def register():
    """Validate the signup form, hash the password and create the user (TC-001, TC-002)."""
    raise NotImplementedError("M1")


def login():
    """Check submitted credentials against the stored hash and open a session (TC-003, TC-004)."""
    raise NotImplementedError("M1")


def logout():
    """Clear the Flask session and redirect to the login page."""
    raise NotImplementedError("M1")


def require_auth(view):
    """Decorator redirecting unauthenticated requests to /login before the view runs (TC-005)."""
    raise NotImplementedError("M1")
