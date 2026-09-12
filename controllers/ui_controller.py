"""Search, feed, save, reject and profile routes.

STUB — the search route currently still lives inline in app.py, which is the one working
code path in the project. Moving it here as a blueprint is M2 work and is recorded as an
open item in docs/ARCHITECTURE.md; it was deliberately not done during the restructure so
that a pure file move could be verified as behaviour-preserving.

Covers TC-006 to TC-014.

Route handlers stay thin: they capture input, call JobSearchAgent or DatabaseManager, and
render a template. No requests, no PyMongo and no sentence-transformers imports here —
that is the layering rule the SDD is graded on.

Every error path renders a visible Bootstrap banner. Never a blank page, never a stack trace.
"""


def search():
    """Handle the search form, run JobSearchAgent and render ranked results (TC-006, TC-007)."""
    raise NotImplementedError("M2")


def save_job():
    """Save a job to the user's list and raise that category's score by 1 (TC-009, TC-011)."""
    raise NotImplementedError("M3")


def reject_job():
    """Record a rejection and lower that category's score by 1 (TC-010, TC-012)."""
    raise NotImplementedError("M3")


def feed():
    """Render the For You feed, built from the user's top-scoring categories (TC-013, TC-014)."""
    raise NotImplementedError("M3")


def profile():
    """Display and update the user's skills, experience, location and work preference (TC-008)."""
    raise NotImplementedError("M1")
