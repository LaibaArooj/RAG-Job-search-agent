"""Flask application — wiring only. Every route now lives in a blueprint.

Every secret is read through config.py, which reads .env. Nothing is hardcoded and there is
no fallback secret key: a known signing key lets anyone forge a session cookie for any
username, so a missing FLASK_SECRET_KEY is fatal at startup rather than silently insecure.

The search route moved to controllers/ui_controller.search on 2026-09-20. This module's only
remaining job is to construct the three long-lived objects — DatabaseManager, SemanticEngine,
RAGPipeline — assemble JobSearchAgent from them, and hand both the agent and the database to
the blueprints through app.config.
"""

from flask import Flask

import config
from adapters.db_manager import DatabaseManager
from controllers.auth_controller import auth_bp, csrf_token
from controllers.ui_controller import ui_bp
from core.agent import JobSearchAgent
from core.rag_pipeline import RAGPipeline
from core.semantic_engine import SemanticEngine

config.validate()

app = Flask(__name__)

if not config.SECRET_KEY:
    raise config.ConfigError(
        "FLASK_SECRET_KEY is not set. Sessions cannot be signed safely without it."
    )
app.secret_key = config.SECRET_KEY

# One DatabaseManager for the process, reached by the controllers through current_app.config
# rather than by importing app (which would be a circular import). It connects lazily, so
# constructing it cannot fail here.
db = DatabaseManager()
app.config["DB"] = db

app.register_blueprint(auth_bp)
app.register_blueprint(ui_bp)

# Index creation is idempotent and cheap, but Atlas may be unreachable. A database outage
# must produce an error banner in a request, not a crash before the server ever listens.
try:
    db.ensure_indexes()
except Exception as e:
    app.logger.error("could not create indexes at startup: %s", e)

# Load both AI components once at startup. SemanticEngine pulls an 88 MB model into memory;
# doing it per request would make every search unusable.
engine = SemanticEngine()
rag = RAGPipeline()

# The agent is assembled here and nowhere else. It takes its three collaborators as arguments
# rather than constructing them, which is what lets verify_agent.py run the whole pipeline
# offline against doubles — no model load, no Atlas, no Adzuna quota.
app.config["AGENT"] = JobSearchAgent(db, engine, rag)


@app.context_processor
def inject_csrf_token():
    """Make csrf_token() callable from every template, so no form can forget it."""
    return {"csrf_token": csrf_token}


if __name__ == "__main__":
    # PORT lets a second copy run beside one already on 5000 (the default, unchanged).
    import os
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
