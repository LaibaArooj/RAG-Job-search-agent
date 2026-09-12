# RAG-Based Intelligent Job Search Agent

Final Year Project — Laiba Arooj, Dept. of Computer Science. Supervisor: Dr Ali Sammad.

## Goal

A Flask web app that lets job seekers search in plain English instead of keywords. It fetches
live listings from Adzuna and Remotive, ranks them by semantic similarity using a local
sentence-transformer, and passes the top 5 to Llama 3 via Groq to produce three explained
picks. Saving and rejecting jobs updates per-category preference scores that personalise
future rankings and a "For You" feed.

Project type: **academic deliverable — must be demonstrable and defensible in a viva**
Current milestone: **M1 — Auth, profile and database**

This is graded work. Correctness and my ability to explain the design matter more than speed
or cleverness. When you make a design decision, tell me why, so I can defend it.

## Context files

- `docs/PROJECT_SPEC.md` — requirements distilled from the SRS and SDD. Source of truth.
- `docs/ARCHITECTURE.md` — layers, classes, module layout, data model.
- `docs/PROJECT_STATUS.md` — milestones, what's done, where we left off. **Read at session start.**
- `docs/CHANGELOG.md` — history of what shipped.
- `docs/EVALUATION.md` — how the ranking claim gets measured. Do not skip this.
- `docs/LEARNING_LOG.md` — concept inventory and my self-rated understanding of each.
- `docs/VIVA_PREP.md` — question bank and demo rehearsal checklist.
- The full SRS and SDD are the authoritative academic documents. If anything here contradicts
  them, the SRS/SDD wins — tell me about the conflict rather than silently picking one.

## Stack — do not substitute any of this

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Web framework | Flask 3.0+ (Jinja2 templates, server-rendered) |
| Frontend | HTML5 + CSS + Bootstrap 5.3 — **no React, Vue or any JS framework** |
| Database | MongoDB Atlas 7.0+ (free tier) via PyMongo 4.6+ |
| Embeddings | sentence-transformers 2.7+, model `all-MiniLM-L6-v2`, runs locally, 384-dim |
| LLM | **Groq** API (not Grok), model `groq/compound-mini` — Groq decommissioned Llama 3, see `docs/PROJECT_SPEC.md` § Deviations. Model id lives only in `GROQ_MODEL` in `rag_pipeline.py` |
| Auth | Werkzeug password hashing (ships with Flask) |
| Job data | Adzuna API (250 req/day free) + Remotive API (no auth, no limit) |
| Env | pip + venv, dependencies pinned in `requirements.txt` |

Hard constraint from the SRS: **every tool, API and service must be free with no credit card.**
Never propose a paid service. Never propose a vector database — embeddings are computed
in memory per request and discarded by design.

## Commands

```bash
python -m venv venv && venv\Scripts\activate    # Windows
pip install -r requirements.txt
python app.py                                    # dev server
```

## Constraints

- Never hardcode secrets. Adzuna, Groq and the Mongo URI all come from `.env` via python-dotenv.
- `.env` must stay in `.gitignore`. Never commit it.
- Never store a plain-text password. Werkzeug `generate_password_hash` only.
- Never interpolate user input directly into a MongoDB query filter (NoSQL injection).
- Every external API call must be wrapped in try/except. The app must never show a stack trace
  or a blank page — always a friendly error banner.
- If Groq fails, hide the AI Recommendations section and show the raw ranked results. Never crash.
- No emails, no notifications, no direct job applications, no employer features, no mobile app.
- Ask before adding a dependency or changing the MongoDB schema.

## Deviations from the SRS — three, all deliberate

The SRS is v1.0 and authoritative, but three changes have been agreed since. They're recorded
in `docs/PROJECT_SPEC.md` § Deviations with justifications. Don't revert to the SRS behaviour
without asking:

1. `parse_intent` calls Groq for structured intent plus 2–3 query variants; keyword matching
   is the fallback path, not the primary one.
2. The APIs are called once per query variant, results unioned and deduplicated on `job_id`.
3. Evaluation (precision@5) is a deliverable, not optional.

Groq is therefore called **twice per search**. Both calls need try/except with a working
fallback — FR-018 says the app never crashes when the LLM is unavailable, and that now applies
to intent parsing too.

## Honesty about limitations

This system re-ranks what keyword search returns; it cannot retrieve what keyword search
missed. Don't write comments, docstrings or report text implying otherwise. If I ask you to
describe what the system does, describe it accurately — overclaiming in the code or the write-up
is what gets picked apart in a viva.

## Architectural rules from the SDD — enforce these

Strict layering. Each of these is the *only* class allowed to touch its dependency:

- `DatabaseManager` — the only class that imports PyMongo
- `APIClient` — the only class that imports `requests`
- `SemanticEngine` — the only class that imports sentence-transformers

Everything else goes through those facades. This is a graded design property, not a preference.

## Repo etiquette

- Branch per milestone or feature: `feat/auth`, `feat/search-pipeline`
- Small commits with imperative messages: `add user registration route`
- Never push directly to `main`

## Style

- PEP 8. `snake_case` for Python and for MongoDB field names.
- One-line docstring on every function (this is an SRS maintainability requirement).
- Bootstrap 5 components; keep custom CSS minimal.
- Errors always render as a visible banner, never a blank page.

## Documentation upkeep

After finishing a feature: append to `docs/CHANGELOG.md`, update `docs/PROJECT_STATUS.md`,
and update `docs/ARCHITECTURE.md` if the structure changed. `/update-docs` does all three.

## Understanding upkeep — as important as the code

This is graded partly on whether I can explain it, so shipping a component isn't finishing it.

After completing any non-trivial component, **offer a comprehension check** before moving on:
one or two questions about what we just built and why. If my answer is vague, say so directly
rather than accepting it — a false pass here becomes a silence in the viva.

When I introduce a concept I clearly haven't met before (a new algorithm, a new library
behaviour, an unfamiliar pattern), add a row for it to `docs/LEARNING_LOG.md` rather than
just using it.

Never write a comment or docstring that overstates what the code does. If a function
re-ranks, the comment says re-ranks, not "retrieves semantically".

## Working style

- Use plan mode before writing code. Show me the plan first.
- Explain design decisions as you make them — I have to defend them in a viva.
- Ask when the SRS is ambiguous rather than inventing a requirement.
- Where a requirement has a test case in the SRS (TC-001 to TC-018), make the code satisfy
  that exact test.
