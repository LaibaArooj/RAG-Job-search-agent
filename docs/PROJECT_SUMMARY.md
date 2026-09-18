# Project Summary — RAG-Based Intelligent Job Search Agent

**Laiba Arooj** · Dept. of Computer Science · Supervisor: Dr Ali Sammad
Final Year Project · Summary as at **2026-09-19**

> A standing overview for supervision and viva preparation. For session-level working notes
> (blockers, next actions, where we stopped) see `PROJECT_STATUS.md`; for the full requirement
> set see `PROJECT_SPEC.md`.

---

## 1. What the system does

A Flask web application that lets a job seeker search in plain English — "something creative I
can do from home, I'm just starting out" — instead of keywords.

1. The query is sent to a Groq-hosted LLM, which returns **structured intent** (work type,
   experience level, category) plus 2–3 alternative phrasings of the query.
2. Each phrasing is sent to the **Adzuna** and **Remotive** job APIs. Results are unioned and
   deduplicated.
3. A **locally-run sentence-transformer** (`all-MiniLM-L6-v2`, 384-dim) embeds the query and
   every returned job, and **re-ranks** them by cosine similarity.
4. The top 5 go back to the LLM, which returns **three explained recommendations**.
5. Saving or rejecting a job adjusts a per-category preference score, which personalises later
   rankings and a "For You" feed.

### What it does not do — stated deliberately

**The system re-ranks the candidate pool that keyword search returns. It cannot retrieve a job
the APIs never fetched.** Recall is bounded by Adzuna's and Remotive's own keyword matching.
Query expansion widens that pool; it does not remove the ceiling.

This is the project's main technical weakness and it is documented rather than hidden. Any
description that implies semantic *retrieval* rather than semantic *re-ranking* is inaccurate,
and the code comments are written to match.

---

## 2. Constraints

| Constraint | Source | Status |
|---|---|---|
| Every tool, API and service free, no credit card | SRS, hard requirement | Held — Adzuna free tier, Remotive unauthenticated, Groq free tier, Atlas M0, embeddings local |
| No vector database | Design decision | Held — embeddings computed per request and discarded; the corpus is external and changes constantly, so an index would serve stale postings |
| No JS framework | SRS | Held — server-rendered Jinja2 + Bootstrap 5.3 |
| Passwords never stored in plain text | SRS §3.5 | Held — Werkzeug PBKDF2 hashes only |
| Secrets never hardcoded | SRS §3.5 | Held — all via `.env`, which is gitignored |

---

## 3. Architecture

Monolithic Flask application; all AI/ML runs in-process. No microservices, no model server.

```
app.py            Flask app + the search route
config.py         env-driven config, category vocabulary, cache TTL
controllers/      auth_controller, ui_controller
core/             agent, semantic_engine, rag_pipeline, intent_parser
adapters/         api_client (Adzuna, Remotive), db_manager (MongoDB)
models/           user, job_card
templates/        Jinja2 + Bootstrap 5.3
```

### The graded design property

Strict layering. Each external dependency has exactly one door into the system:

| Dependency | Sole importer |
|---|---|
| `pymongo` | `adapters/db_manager.py` |
| `requests` | `adapters/api_client.py` |
| `sentence_transformers` | `core/semantic_engine.py` |
| `werkzeug.security` | `controllers/auth_controller.py` |

The test of whether this is real: swapping any one of them should mean editing one file.

---

## 4. Current progress

### Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Auth, profile, database | **Complete (2026-09-19)** — TC-001 to TC-005 pass against live Atlas |
| M2 | Search pipeline: intent, expansion, dedupe, ranking | **Next** (a working prototype of the ranking path exists) |
| M3 | RAG, save/reject learning, For You feed | Not started |
| M4 | Evaluation (precision@5), filters, full test pass, demo | Not started |

### Component state

| Component | State | Notes |
|---|---|---|
| `config.py` | **Built** | Fails loudly at startup naming any missing variable |
| `adapters/api_client.py` | **Built** | Adzuna + Remotive, normalisation, dedupe |
| `core/semantic_engine.py` | **Built** | Loads from local cache; startup no longer needs the network |
| `core/rag_pipeline.py` | **Built** | Groq call with a working fallback |
| `adapters/db_manager.py` | **Built, verified** | 27/27 checks pass against the live cluster |
| `verify_db.py` | **Built, passing** | 27 pass / 0 fail |
| `controllers/auth_controller.py` | **Built** | `auth` blueprint: register, login, logout, `require_auth`, CSRF |
| `verify_auth.py` | **Built, passing** | 31 pass / 0 fail, covering TC-001 to TC-005 |
| `controllers/ui_controller.py` | **Part built** | `profile` (M1) and a protected `feed` placeholder; `search`/`save_job`/`reject_job` still stubs |
| `core/agent.py`, `core/intent_parser.py` | Stub | M2 |
| `models/user.py` | **Built** | `from_document` / `to_document` |
| `models/job_card.py` | Stub | M2 |

Stubs raise `NotImplementedError` with their milestone rather than `pass`, so an unimplemented
function cannot silently return `None` and reach a demo unnoticed.

### What has actually been demonstrated

Verified by running it, not by inspection:

- **Search runs end to end without a database.** Query "remote python developer" returns
  **24 deduplicated jobs from both Adzuna and Remotive**, ranks them semantically (top result
  0.674 similarity), and Groq returns a populated three-pick recommendation panel.
- **FR-018 holds.** Pointed at a non-existent Groq model, the 404 is caught, the AI panel is
  hidden, ranked results still render, no stack trace, no exception escapes.
- **Injection guard works.** A category of `writing.$ne` is rejected before it can reach a
  MongoDB field path.
- **Nothing connects at import.** A database outage cannot crash application startup.
- **The full auth cycle works against live Atlas (2026-09-19).** Register, log in, edit the
  profile, log out, log back in. `verify_auth.py` asserts 31 properties over the real routes,
  the real signed session cookie and the real database, including all of TC-001 to TC-005.
- **Passwords are never stored in plain text.** The stored value is asserted to be a Werkzeug
  hash and to not contain the submitted password.

---

## 5. Notable design decisions

| Decision | Why |
|---|---|
| Live retrieval, no vector DB | The corpus is external and changes constantly; an index would serve stale postings |
| Local MiniLM embeddings | Free (a hard constraint); ~200 ms for 42 jobs |
| MongoDB over SQL | `category_scores` gains new keys with no migration |
| One denormalised user document | A single read returns the whole search context — no joins |
| LLM intent parsing over if-statements | The SRS defines an Agent as autonomously deciding its steps; keyword matching does not meet that definition |
| Duplicate username enforced by a unique index | A read-then-write check can be beaten by a concurrent signup; the index cannot |
| One login-failure message for both causes | Distinct messages for "no such user" and "wrong password" turn the login form into a username oracle |
| No fallback secret key — startup fails without one | A known session-signing key lets any visitor forge a session cookie for any username, which makes the auth decorative |
| CSRF hand-rolled, not Flask-WTF | No new dependency, and a per-session token compared with `hmac.compare_digest` can be explained line by line in the viva |
| Save/reject as one atomic conditional update | The filter requires the job not already be saved, so a repeat click cannot increment the score twice — TC-013 holds with no race |

---

## 6. Blockers

### Resolved — the Atlas connection

The data layer was untestable from 2026-09-13 to 2026-09-19 because TLS on port 27017 timed out
against all three shards while TLS on :443 completed normally — a middlebox on that port, not a
credential fault. The layer-by-layer probe (DNS → TCP → TLS → auth) is what ruled the password
out: authentication happens *after* the TLS handshake, so a handshake that never completes
cannot be a password problem.

The network path now works and nothing in the code was changed to fix it. If it recurs on
campus, the symptom is a TLS timeout on :27017 only, and a phone hotspot is the test.

### Blocking — `FLASK_SECRET_KEY` absent from `.env`

The app now refuses to start without it, deliberately: a known signing key makes the session
cookie forgeable. Generate one with
`python -c "import secrets; print(secrets.token_urlsafe(32))"` and add it to `.env`.
`verify_auth.py` injects a throwaway key into its own process, which is why the checks run today.

### Non-blocking

- The venv is **Python 3.14.6**; the SRS specifies **3.11**. Either rebuild or record as a
  deviation. An examiner may ask.
- The save/reject buttons in `feed.html` post to `/save_job` and `/reject_job`, which are not
  yet routes. They are unreachable today because the feed renders no jobs, but they must be
  wired in M3 or removed.

---

## 7. Deviations from SRS v1.0 — five, all documented

Four intentional, one forced. Each needs a line in the final report; **all need supervisor
sign-off.** Full justifications in `PROJECT_SPEC.md` § Deviations.

| # | Change | Reason |
|---|---|---|
| 1 | Intent parsing calls Groq for structured intent + variants; keywords are the fallback | The SRS's own definition of an Agent is not met by if-statements |
| 2 | Query expansion — 2–3 variants unioned and deduped | Softens the recall ceiling |
| 3 | Evaluation (precision@5) is a deliverable | The project claims semantic ranking is better; that claim needs evidence |
| 4 | **LLM model is `groq/compound-mini`, not Llama 3** | **Forced — Groq decommissioned Llama 3 mid-project.** Verified against the live model list: no Llama chat model remains. Same provider, same free tier; the model id is one constant, so a revert is one line |
| 5 | `rejected_jobs` stores `job_id`, not job titles | Titles are not unique across employers; title-keyed rejection would hide every job sharing a title. Field type unchanged |

---

## 8. Open questions

- **How is a job's category derived?** Adzuna and Remotive use different taxonomies and neither
  matches the project's category list. The whole save/reject scoring loop depends on one
  consistent category per job. **Must be settled before M3.**
- Does the For You feed hit the live APIs on every visit? At 250 Adzuna requests/day that quota
  disappears quickly during testing. `job_cache` (60-min TTL) exists to mitigate this.
- The **0.02 category-boost coefficient** is hand-picked with no justification. Either tune it
  during evaluation or state it plainly as a heuristic.
- Whether to swap `all-MiniLM-L6-v2` for `msmarco-MiniLM-L6-v3`, which is trained for
  short-query-to-long-document matching. One-line change, but it deviates from the model named
  in the SRS — needs sign-off.

---

## 9. Immediate next steps

1. Add `FLASK_SECRET_KEY` to `.env` — the app will not start without it.
2. Drive TC-001 to TC-005 once in a real browser. `verify_auth.py` exercises the routes and the
   session cookie, not the rendered forms.
3. Begin M2 on a `feat/search-pipeline` branch: `core/intent_parser.py`, then `core/agent.py`,
   then move the search route out of `app.py` into `ui_controller.search`.
4. Decide the category taxonomy before M3 work begins.

**Highest-value remaining single day of work:** the precision@5 evaluation (M4). It is what
converts "semantic ranking is better" from an assertion into a measured result. The 20
evaluation queries must be written **before** any results are looked at.
