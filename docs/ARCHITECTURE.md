# Architecture — RAG-Based Intelligent Job Search Agent

Derived from SDD v1.0 §3–§5. Claude keeps this current as the code evolves.

Last updated: 2026-09-19 (M1 auth blueprints built; see § Module layout (as built))

## System overview

Monolithic Flask application. All AI/ML processing happens in-process in the same Python
runtime as the web routes — no microservices, no message queues, no separate model server.

```
Browser (Bootstrap 5 / Jinja2)
        |
        v
Flask application layer
  UIController · AuthController · JobSearchAgent
        |
        +--> AI/ML layer: SemanticEngine · RAGPipeline · intent_parser
        |
        +--> Data layer: MongoDB Atlas (users) · Flask session · job_cache (optional)
        |
        +--> External: Adzuna API · Remotive API · Groq (Llama 3)
```

## Layers

| Layer | Contents | Responsibility |
|---|---|---|
| Presentation | Server-rendered Jinja2 + Bootstrap 5.3 | Display and input capture only |
| Application | UIController, AuthController, JobSearchAgent | Business logic and orchestration |
| AI / ML | SemanticEngine, RAGPipeline, intent_parser | Pure Python, called synchronously |
| Data | MongoDB Atlas, Flask session, job_cache | Persistence |
| External | Adzuna, Remotive, Groq, HuggingFace (once) | Third-party services |

## The nine classes

| Class | Responsibility | Sole owner of |
|---|---|---|
| `User` | Profile data, scores, saved/rejected refs | — |
| `AuthController` | Hashing, credential check, session, route protection | Werkzeug security |
| `JobSearchAgent` | Orchestrates the full search pipeline via `run()` | — |
| `SemanticEngine` | Wraps all-MiniLM-L6-v2; encode / batch_encode / similarity | sentence-transformers |
| `RAGPipeline` | retrieve → augment → generate, plus `fallback()` | prompt construction |
| `intent_parser` | Groq-based structured intent + query variants, keyword fallback | intent schema |
| `APIClient` | Adzuna, Remotive, Groq calls; Adzuna rate limiter | `requests` |
| `DatabaseManager` | Thin PyMongo facade — `get_user_context`, `increment_score` | PyMongo |
| `JobCard` | Normalises Adzuna and Remotive field shapes into one | — |
| `UIController` | Flask route functions | Flask routing |

**The layering rule is a graded design property.** Only `DatabaseManager` imports PyMongo,
only `APIClient` imports `requests`, only `SemanticEngine` imports sentence-transformers.
Swapping any dependency should mean editing one file.

## Search request flow

1. Auth check — unauthenticated requests redirect to `/login` before anything else
2. `DatabaseManager.get_user_context(user_id)` — profile fetched before any API call
3. `parse_intent(query)` — Groq call returning structured JSON: work type, experience,
   category, and 2–3 alternative query phrasings. Falls back to keyword matching on failure
4. `enrich_query(query, context)` — profile injected into the query text
5. Query encoding, then Adzuna + Remotive fetched once per query variant.
   **Deferred, deliberately:** the SDD specifies a parallel fork here (query encoding ‖ Adzuna
   ‖ Remotive, ~800 ms saved). `core/agent.py` fetches *sequentially* as of 2026-09-19. With
   three variants that is six sequential HTTP calls and the demo is correspondingly slow. The
   trade: a threading bug that intermittently drops one variant's results is far harder to
   notice, and far harder to defend in a viva, than a search that takes a few seconds. Revisit
   only if demo latency becomes the binding problem.
   Each variant is read through the 60-minute `job_cache` first and written back on a clean
   fetch, keyed on a SHA-256 of the **variant** string rather than the user's query — two
   different searches that expand onto a shared phrasing then reuse one fetch. This is what
   keeps three variants from costing three Adzuna quota units on every repeat search. A
   *partial* fetch is never cached, or an outage would outlive the API's recovery by an hour.
6. Join, union all variants' results, deduplicate on `job_id` (SHA of title + company).
   If no jobs from any variant → friendly error banner, retry offered
7. `batch_encode` all job descriptions → cosine similarity vs query vector
8. Score = similarity + (`category_scores[job.category]` × 0.02); sort descending
9. Top 5 → `RAGPipeline.run()`. Wrapped in try/except:
   Groq failure → `fallback()`, AI section hidden, raw results still rendered
10. Render: AI Recommendations band, then the full ranked list

Five decision points the code must handle: empty query, unauthenticated, intent-parse
failure (fall back to keywords), no jobs returned, RAG failure (hide the AI panel).

**Groq is now called twice per search** — once for intent parsing, once for RAG generation.
Both sit behind try/except with a working fallback, so FR-018 still holds. Watch the free-tier
rate limit: two calls per search halves the number of searches you can demo per minute.

## Module layout (as built)

Matches SDD Appendix B. Every file named there exists; the ones not yet implemented are
stubs that `raise NotImplementedError` with the milestone that fills them in, rather than
`pass` — a stub that silently returns `None` is how an unimplemented function gets shipped.

```
app.py                          Flask app + the search route (see deferral below)
config.py                       env-driven config, validate() fails loudly on a missing
                                key; also the three closed vocabularies — CATEGORIES,
                                WORK_TYPES, EXPERIENCE_LEVELS
controllers/
    auth_controller.py          BUILT — auth blueprint: register, login, logout,
                                require_auth, csrf_token/check_csrf
    ui_controller.py            PART BUILT — ui blueprint: profile (M1), feed (placeholder
                                until M3); search/save_job/reject_job still stubs
core/
    semantic_engine.py          BUILT — SemanticEngine
    rag_pipeline.py             BUILT — RAGPipeline
    agent.py                    BUILT — JobSearchAgent; the pipeline orchestrator.
                                TC-006, TC-016 to TC-018, TC-021, TC-022
    intent_parser.py            BUILT — parse_intent (Groq + keyword fallback),
                                enrich_query; TC-019, TC-020
adapters/
    api_client.py               BUILT — Adzuna + Remotive fetch. fetch_variant() returns
                                jobs and failed_sources separately (TC-018); normalising
                                now delegated to JobCard. fetch_all_jobs is legacy, used
                                only by the inline route and retired with it
    db_manager.py               BUILT — MongoDB facade
models/
    user.py                     BUILT — User dataclass
    job_card.py                 BUILT — JobCard dataclass; the single place an Adzuna/
                                Remotive field-shape difference is resolved. make_job_id
                                (SHA-256 of title|company) is the dedupe key (TC-022)
templates/                      index, register, login, profile, feed
static/css/, static/js/
tests/                          empty — pytest is not yet a dependency
verify_db.py                    standalone pass/fail check of the data layer
verify_auth.py                  standalone pass/fail check of the auth routes (TC-001..005)
verify_intent.py                standalone check of intent parsing (TC-019, TC-020); makes
                                one live Groq call
verify_agent.py                 standalone check of the pipeline (TC-006, TC-016..018,
                                TC-021, TC-022). Entirely offline: every collaborator is a
                                double, which is why JobSearchAgent takes them as arguments
```

**Deferral, recorded deliberately.** Appendix B describes `app.py` as an app factory whose
search route lives in `controllers/ui_controller.py` as a blueprint. The route is still
inline in `app.py` because it is the one fully working code path in the project, and the
restructure was carried out as a pure move so that identical behaviour could be verified
before and after. Moving it is M2 work.

As of 2026-09-19 `JobSearchAgent` exists and is proven, but the inline route still does not
use it: the agent was built and verified *beside* the working route rather than in place of
it, so there was never a point where the app was broken. The two coexist until the route is
swapped over, which is the last piece of M2. `api_client.fetch_all_jobs` is retired at the
same time — it is the legacy path's only remaining caller, and two fetch paths left standing
is how the two drift apart.

**Removed:** `models.py` (flat module). It collided with the `models/` package — Python
resolves the name to one of them and the other silently disappears — and was already dead
code. Its functions are carried forward as named stubs in `adapters/db_manager.py`, which
also records the three defects in the original not to repeat: a NoSQL field-path injection
in `update_category_score`, a module-level `MongoClient` connect with no try/except, and a
bare `except` reporting every error as "Username already taken". Preserved at `5519a22`.

**Environment variable naming settled:** `MONGODB_URI` everywhere — code, `.env.example`
and docs. The earlier `MONGO_URI` spelling is retired.

## Authentication and session (M1)

`AuthController` is the `auth` blueprint and the sole importer of `werkzeug.security`.
Passwords are hashed there; `DatabaseManager.create_user` receives a hash and never a password.

| Concern | Decision | Why |
|---|---|---|
| Session | Flask's signed cookie, key from `FLASK_SECRET_KEY` | No server-side session store to run; free-tier constraint |
| Missing key | `ConfigError` at startup, **no fallback** | A known signing key lets anyone forge a session for any username |
| Route protection | `require_auth` decorator, `functools.wraps` | TC-005; `wraps` keeps the endpoint name Flask derives from `__name__` |
| Failed login | One message for unknown user and wrong password | Two messages turn the form into a username oracle (TC-004) |
| Session fixation | `session.clear()` before granting a session | A cookie planted pre-login is not the one that ends up authenticated |
| CSRF | Hand-rolled per-session token, `hmac.compare_digest` | No new dependency; mechanism is explainable line by line |

The CSRF token reaches templates through a context processor in `app.py`, so a form cannot
silently omit it by forgetting to pass a variable. `check_csrf()` is called by every POST
handler — `/register`, `/login`, `/profile` and the search route.

Input is whitelisted twice on the profile path: `update_profile` fixes which *fields* may be
written, and `ui_controller` fixes which *values* `experience` and `preferred_work` may take.

The same discipline applies to the LLM. `parse_intent` treats Groq's reply as untrusted
input: the allowed values are listed in the prompt *and* re-checked for membership on the
way out. The prompt steers the model; the membership test is the guarantee. This matters
most for `category`, which becomes part of a MongoDB field path in M3.

### Why the vocabularies live in `config.py`

`CATEGORIES`, `WORK_TYPES` and `EXPERIENCE_LEVELS` are all defined in `config.py`, which
imports nothing from the project. `WORK_TYPES` and `EXPERIENCE_LEVELS` started in
`controllers/ui_controller.py` and moved on 2026-09-19, because `core/intent_parser.py`
validates against the same sets and an AI-layer module importing from a controller both
inverts the layering above and creates a genuine import cycle:
`ui_controller` → `core.agent` → `core.intent_parser` → `ui_controller`, which fails with
"cannot import name ... from partially initialized module". The cycle is **order-dependent**
— it only fails with the import at the top of the file, where PEP 8 puts it — which is why
it was fixed rather than worked around.

## Data model

See `docs/PROJECT_SPEC.md` § Data model. One denormalised document per user in `users`.
Unique index on `username`. `job_cache` with a TTL index on `created_at`, expiry driven by
`config.JOB_CACHE_TTL_MINUTES` (60, the spec value) rather than a hardcoded number.

Both indexes are created by `DatabaseManager.ensure_indexes()`, which is safe to re-run.
The unique index is what enforces TC-002: duplicate registration is rejected by the server,
not by a read-then-write check in Python, which a concurrent signup could slip between.

`rejected_jobs` holds `job_id` values, not titles — Deviation 5, see `docs/PROJECT_SPEC.md`.

## External services

| Service | Used for | Env var | Limit |
|---|---|---|---|
| Adzuna | Live job listings | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | 250 requests/day |
| Remotive | Remote job listings | none — no auth | none |
| Groq | LLM inference — `groq/compound-mini` (Llama 3 was decommissioned by Groq; see `docs/PROJECT_SPEC.md` § Deviations) | `GROQ_API_KEY` | free-tier rate limits |
| MongoDB Atlas | User profiles | `MONGODB_URI` | 512 MB |
| HuggingFace | One-time model download | none | — |

## Decisions and trade-offs

| Decision | Why | Rejected alternative |
|---|---|---|
| Live retrieval, no vector DB | Corpus is external and changes constantly; an index would serve stale postings | Pre-indexed corpus in a vector store |
| Monolithic Flask | Single developer, single runtime, no ops overhead | Microservices, separate model server |
| Local MiniLM embeddings | Free — a hard project constraint; ~200 ms for 42 jobs | Cloud embedding API (costs money) |
| MongoDB over SQL | `category_scores` grows new keys without migrations | PostgreSQL |
| Denormalised single user document | One read gets the entire context needed per search | Normalised collections with joins |
| Groq free tier | Free Llama 3 inference, no credit card | OpenAI / Anthropic APIs (paid) |
| Bootstrap, no JS framework | Keeps complexity manageable for one developer | React / Vue |
| LLM intent parsing | Keyword if-statements don't meet the SRS's own definition of an Agent | `if 'remote' in query` (kept as fallback) |
| Query expansion (2–3 variants) | Widens the candidate pool the semantic layer can rank | Single keyword query |
| Dedupe on title+company hash | Adzuna and Remotive syndicate overlapping listings | No dedupe (duplicates in results) |

## Known limitation of this architecture

Recall is bounded by keyword search. Embeddings re-rank the pool the APIs return; they cannot
surface a job keyword search never fetched. Query expansion widens the pool but does not
remove the ceiling. See `docs/PROJECT_SPEC.md` § Known limitations for the full list.
