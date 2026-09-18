"""Flask application — wiring, plus the search route still deferred here from M2.

Every secret is read through config.py, which reads .env. Nothing is hardcoded and there is
no fallback secret key: a known signing key lets anyone forge a session cookie for any
username, so a missing FLASK_SECRET_KEY is fatal at startup rather than silently insecure.
"""

from flask import Flask, flash, render_template, request

import config
from adapters.api_client import fetch_all_jobs
from adapters.db_manager import DatabaseManager
from controllers.auth_controller import (
    auth_bp,
    check_csrf,
    csrf_token,
    current_username,
    require_auth,
)
from controllers.ui_controller import ui_bp
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

# Load both AI components once at startup
engine = SemanticEngine()
rag = RAGPipeline()


@app.context_processor
def inject_csrf_token():
    """Make csrf_token() callable from every template, so no form can forget it."""
    return {"csrf_token": csrf_token}


@app.route("/", methods=["GET", "POST"])
@require_auth
def home():
    """Run a semantic job search for the logged-in user and render the ranked results."""
    jobs = []
    query = ""
    ai_recommendations = None

    try:
        user = db.get_user_context(current_username()) or {}
    except Exception as e:
        app.logger.error("could not load user context: %s", e)
        flash("Could not load your profile; showing unpersonalised results.", "error")
        user = {}

    if request.method == "POST":
        if not check_csrf():
            flash("Your session expired. Please search again.", "error")
            return render_template("index.html", jobs=[], query="", user=user)

        query = request.form.get("query", "").strip()

        if query:
            # 1. Fetch from Adzuna and Remotive, normalised and deduplicated
            jobs = fetch_all_jobs(query, config.ADZUNA_APP_ID, config.ADZUNA_APP_KEY)

            if jobs:
                # 2. Semantic ranking. The profile is injected into the query text, not into
                # the job text — TC-016 expects Python roles to rank higher for a user whose
                # profile lists Python, which means moving the query vector, not the jobs.
                skills = ", ".join(user.get("skills", []))
                experience = user.get("experience", "")
                enriched_query = (
                    f"job search: {query}. Skills: {skills}. Level: {experience}."
                )
                query_vector = engine.encode(enriched_query)

                job_texts = [
                    f"{job['title']}. {job.get('description', '')}" for job in jobs
                ]
                job_vectors = engine.batch_encode(job_texts)

                for job, vector in zip(jobs, job_vectors):
                    job["similarity_score"] = engine.similarity(query_vector, vector)

                jobs.sort(key=lambda j: j["similarity_score"], reverse=True)

                # Normalize scores for display, relative to the best match.
                # Cosine similarity can be zero or negative, so guard the divide.
                top_score = jobs[0]["similarity_score"]
                for job in jobs:
                    if top_score > 0:
                        job["normalized_score"] = (
                            job["similarity_score"] / top_score
                        ) * 100
                    else:
                        job["normalized_score"] = 0.0

                # 3. RAG pipeline — pass top 5 to LLM
                ai_recommendations = rag.run(query, jobs)

            try:
                db.add_search_history(current_username(), query)
            except Exception as e:
                # History is a nicety. Losing it must never cost the user their results.
                app.logger.error("could not record search history: %s", e)

    return render_template(
        "index.html",
        jobs=jobs,
        query=query,
        ai_recommendations=ai_recommendations,
        user=user,
    )


if __name__ == "__main__":
    app.run(debug=True)
