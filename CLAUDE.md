# RAG-Based Intelligent Job Search Agent

Final Year Project — Laiba Arooj, Dept. of Computer Science. Supervisor: Dr Ali Sammad.

## Goal

A Flask web app that lets job seekers search in plain English instead of keywords. It fetches
live listings from Adzuna, Remotive and Jobicy, ranks them by semantic similarity using a
local sentence-transformer, and passes five to an LLM via Groq to produce three explained
picks. Every card states whether the employer will hire a candidate in the user's location.
Saving and rejecting jobs updates per-category preference scores that personalise future
rankings and a "For You" feed.

Project type: **academic deliverable — must be demonstrable and defensible in a viva**
Current milestone: **M4 — evaluation (precision@5), filters, autocomplete, demo** (M3 closed
2026-09-21: categorisation, the save/reject loop and the For You feed all shipped)

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
| LLM | **Groq** API (not Grok), a FALLBACK CHAIN in `GROQ_MODELS` (`openai/gpt-oss-120b` → `qwen/qwen3.8-27b` → `openai/gpt-oss-20b`), because Groq has retired this project's model twice — Groq decommissioned Llama 3 *and then* `groq/compound-mini`, see `docs/PROJECT_SPEC.md` § Deviations. Model id lives only in `GROQ_MODEL` in `rag_pipeline.py`. **It is a reasoning model: hidden reasoning tokens count against `max_tokens`, so changing it means rechecking the budget at both call sites** |
| Auth | Werkzeug password hashing (ships with Flask) |
| Job data | Adzuna API (250 req/day free, UK market) + Remotive API (no auth; capped at 18 jobs, ignores `search`) + Jobicy API (no auth; `geo=anywhere` filters candidate eligibility server-side) |
| Env | pip + venv, dependencies pinned in `requirements.txt` |

Hard constraint from the SRS: **every tool, API and service must be free with no credit card.**
Never propose a paid service. Never propose a vector database — embeddings are computed
in memory per request and discarded by design.

## Commands

```bash
python -m venv venv && venv\Scripts\activate    # Windows
pip install -r requirements.txt
python app.py                                    # dev server
python verify_db.py                              # prove the data layer against Atlas
python verify_auth.py                            # prove the auth routes, TC-001 to TC-005
python verify_routes.py                          # prove save/reject, categorisation and /feed, TC-010/011/012/013
python verify_intent.py                          # prove intent parsing, TC-019/TC-020 (live Groq call)
python verify_agent.py                           # prove the pipeline and the feed, TC-006/012/014/016/017/018/021/022 (offline)
python verify_live.py                            # prove it against the REAL Adzuna/Remotive/Groq + rendered pages
python verify_all.py                             # run all six, one summary. --offline skips the quota-spending one
python evaluation/score.py                       # re-score the judged sheets into evaluation/results.md (--check: validate only)
```

`verify_*.py` are standalone pass/fail scripts, not pytest — pytest is not a dependency.

**`python verify_all.py` is the pre-demo check.** 528 assertions, about 290 seconds --
485 of them offline, measured 2026-09-26; verify_live.py contributes the other 43. Use
`--offline` while iterating — it skips `verify_live.py`, the only one that spends Adzuna quota.
Everything except `verify_agent.py` touches a live service, so a failure can mean an outage
rather than a regression; read which check failed before assuming the code broke.

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

## Deviations from the SRS — seven

The SRS is v1.0 and authoritative, but seven changes have been made since — five deliberate,
two forced by Groq retiring models mid-implementation. All are recorded in
`docs/PROJECT_SPEC.md` § Deviations with justifications. Don't revert to the SRS behaviour
without asking:

1. `parse_intent` calls Groq for structured intent plus 2–3 query variants; keyword matching
   is the fallback path, not the primary one.
2. The APIs are called once per query variant, results unioned and deduplicated on `job_id`.
3. Evaluation (precision@5) is a deliverable, not optional.
4. **Forced:** the LLM is `openai/gpt-oss-120b`, not Llama 3 — Groq decommissioned Llama 3
   and then decommissioned its replacement too.
5. `rejected_jobs` stores `job_id`, not job titles.
6. **Jobicy is a third job source**, because neither Adzuna nor Remotive can say whether an
   employer will hire a candidate in a given country.
7. The AI panel explains the top five jobs the seeker **can apply for**, not the top five by
   score. Ranking itself is unchanged.

Groq is therefore called **twice per search**. Both calls need try/except with a working
fallback — FR-018 says the app never crashes when the LLM is unavailable, and that now applies
to intent parsing too.

## Honesty about limitations

This system re-ranks what keyword search returns; it cannot retrieve what keyword search
missed. And **measured on 2026-09-30, the re-ranking did not beat keyword order**
(`evaluation/results.md`), so never write that semantic ranking gives better results. Don't write comments, docstrings or report text implying otherwise. If I ask you to
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
