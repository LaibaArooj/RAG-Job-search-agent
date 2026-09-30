# RAG-Based Intelligent Job Search Agent

Final Year Project — Laiba Arooj, Dept. of Computer Science. Supervisor: Dr Ali Sammad.

A Flask web app that lets job seekers search for work in plain English instead of keywords.
It fetches live listings from Adzuna, Remotive and Jobicy, **re-ranks** them by semantic
similarity using a locally-run sentence-transformer, and passes five to a Groq-hosted LLM to
produce three explained recommendations. Every card states whether the employer will hire a
candidate in the user's country. Saving and rejecting jobs adjusts per-category preference
scores, which personalise later rankings and a "For You" feed.

## What this system does and does not do

It re-ranks the candidate pool that keyword search returns. It **cannot retrieve a job that
keyword search never fetched** — recall is bounded by what the job APIs return for the query.
Query expansion (2–3 variants per search) widens that pool but does not remove the ceiling.
See `docs/PROJECT_SPEC.md` § Known limitations.

**Measured, 2026-09-30:** on 20 pre-registered, blind-judged queries, the semantic re-ranking
did not beat Adzuna's own keyword order (precision@5 0.32 vs 0.31). See
`evaluation/results.md`.

## Setup

```bash
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Then fill in `.env`: a MongoDB Atlas connection string, an Adzuna app id and key
(250 requests/day free), and a Groq API key. Every service used is free and requires no
credit card — a hard constraint from the SRS.

The embedding model `all-MiniLM-L6-v2` (~90 MB) downloads from Hugging Face on first run and
is cached locally thereafter.

```bash
python app.py
```

## Layout (SDD Appendix B)

```
app.py            Flask app and, for now, the search route
config.py         environment-driven configuration
controllers/      auth_controller, ui_controller
core/             agent, semantic_engine, rag_pipeline, intent_parser
adapters/         api_client (Adzuna, Remotive), db_manager (MongoDB)
models/           user, job_card
templates/        Jinja2 + Bootstrap 5.3
static/           css, js
docs/             spec, architecture, status, changelog, evaluation, learning log, viva prep
```

**The layering rule is a graded design property.** `adapters/db_manager.py` is the only module
that imports PyMongo, `adapters/api_client.py` the only one that imports `requests`, and
`core/semantic_engine.py` the only one that imports sentence-transformers. Swapping any of
those dependencies means editing one file.

## Stack

Python 3.11 · Flask 3 · Jinja2 + Bootstrap 5.3 (no JS framework) · MongoDB Atlas via PyMongo ·
sentence-transformers `all-MiniLM-L6-v2` (384-dim, local) · Groq API · Werkzeug password hashing

## Status

See `docs/PROJECT_STATUS.md` — current milestone, blockers and where the last session stopped.
