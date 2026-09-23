# Architecture — RAG-Based Intelligent Job Search Agent

Derived from SDD v1.0 §3–§5. Claude keeps this current as the code evolves.

Last updated: 2026-09-20 (search route moved into the ui blueprint; per-source fetch
compensation added to api_client after Remotive stopped honouring its search parameter)

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
5. Query encoding, then Adzuna + Remotive + **Jobicy** fetched once per query variant. Each
   source is compensated for inside `api_client`: work-type words are stripped from Adzuna's
   keyword query (its `what=` is an AND match, so one such word returns nothing) and passed as
   Adzuna's own parameters, while Remotive — which ignores its search parameter and returns a
   fixed list — is filtered locally on the job title, and on the requested level when one was
   parsed.
   **Jobicy, added 2026-09-23**, is queried with `geo=anywhere` so that candidate eligibility
   is filtered server-side. Its `tag=` is an AND match that collapses the same way Adzuna's
   does, so the same stopword and work-type stripping is applied first, with one retry on the
   longest token — two HTTP calls per variant, capped, because Jobicy publishes no rate limit.
   Source ORDER is load-bearing: Jobicy is fetched last, so that a listing syndicated to both
   it and Adzuna keeps Adzuna's copy and its eligibility stays honestly `local` rather than
   being relabelled `open` by fetch order.
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
6b. `JobSearchAgent.classify` — every surviving job is assigned exactly one
   `config.CATEGORIES` value by `core.intent_parser.classify_category`, matched against
   `CATEGORY_HINTS` using the job's **own** title and description. Neither API's taxonomy is
   consulted (settled 2026-09-21). The parsed intent's category is the fallback for a job whose
   text matches nothing, and `"other"` is the last resort. It runs here rather than in
   `JobCard.from_adzuna` / `from_remotive` because `JobCard` normalises *shape* and carries no
   policy, and because running it in the agent covers jobs read back out of the cache too.
   Honest description: keyword matching over job text, not classification by meaning.
   **Rewritten 2026-09-22** after four of five jobs real users had saved were misfiled as
   `design`: the title now decides (description only as fallback), hints of three characters
   or fewer must match whole words, and the category with the most hint matches wins with
   table order as the tie-break only.
7. `batch_encode` all job descriptions → cosine similarity vs query vector
8. Score = similarity + (`category_scores[job.category]` × 0.02); sort descending.
   Live as of 2026-09-21 — until step 6b existed `job.category` was `""` on every listing, so
   this term contributed 0 to every score however strong the learned preference was.
9. `JobSearchAgent.rag_candidates(jobs)` → `RAGPipeline.run()`. Wrapped in try/except:
   Groq failure → `fallback()`, AI section hidden, raw results still rendered.
   **Changed 2026-09-23:** the panel is handed the best five the seeker can *apply for*, not
   the top five by score — applicable jobs (`open` and `unknown`) first, then the rest, topped
   up to five. Measured cause: for a non-UK user all five top-ranked jobs were UK-local, so
   every AI pick was unreachable. **Nothing is re-scored** — this re-partitions the top of the
   list only, and the ranked list rendered below the panel is still ordered purely by
   similarity plus the category boost. The prompt also states each job's eligibility and is
   told to name any restriction plainly.
10. Render: AI Recommendations band, then the full ranked list. Every card carries an
    eligibility badge — open worldwide / region-restricted / local role / terms unclear.

Five decision points the code must handle: empty query, unauthenticated, intent-parse
failure (fall back to keywords), no jobs returned, RAG failure (hide the AI panel).

**Groq is now called twice per search** — once for intent parsing, once for RAG generation.
Both sit behind try/except with a working fallback, so FR-018 still holds. Watch the free-tier
rate limit: two calls per search halves the number of searches you can demo per minute.

## Save / reject request flow (M3, 2026-09-21)

`POST /save_job` and `POST /reject_job` in `controllers/ui_controller.py`.

1. `@require_auth` — anonymous requests redirect to `/login` (TC-005 applies here too)
2. `check_csrf()` — the posted token compared with the session's using `hmac.compare_digest`
3. The job dict is rebuilt field by field from a fixed key list, never from `request.form`
   wholesale, so a crafted POST cannot add keys to a stored `saved_jobs` entry
4. `job_id` must be present, or the entry could never be deduplicated on a second save (TC-013)
5. `category` must be a member of `config.CATEGORIES` → otherwise **400**, not 500.
   `DatabaseManager._score_path` raises `ValueError` on the same condition because the category
   reaches a MongoDB field path; the route check is what makes the status code tell the truth
6. `DatabaseManager.save_job` / `reject_job` — one atomic `$push` + `$inc` (TC-010, TC-011)
7. Response is **JSON**: `{ok, already, category}`

**Why JSON and not a redirect.** The ranked list exists only in the response that rendered it —
nothing persists it. A POST-redirect-GET would either lose the results the user is looking at or
re-run the whole pipeline, including a second Groq call, on every click. `static/js/decisions.js`
posts with `fetch` and flips the button in place instead.

**Why the body is form-encoded, not JSON.** `check_csrf()` reads `request.form`. A JSON request
body leaves `request.form` empty, so every token check would fail.

`already: true` means the job was already recorded by an earlier click. That is TC-013's case
and it is a **success** — the score moved exactly once — so the button settles identically.

Degradation with JavaScript disabled: the buttons do nothing. The search itself is a plain form
POST and is unaffected.

## For You feed request flow (M3, 2026-09-21)

`GET /feed` in `controllers/ui_controller.py` → `JobSearchAgent.build_feed(username)`.

The feed shares the search pipeline's steps except intent parsing and the RAG call. The user's
top-scoring categories stand in for the query, so **the learned preference is the entire
input** — this is the only screen where that is true.

1. `@require_auth` — anonymous requests redirect to `/login` (TC-005)
2. `get_user_context` — profile, `category_scores` and `rejected_jobs` in one read
3. `get_top_categories(n=3)` — **positive scores only**. A category the user has rejected more
   than saved is not in this list, which is TC-012's "tech jobs absent" enforced at the source
4. **No categories → return immediately.** No fetch, no embedding, no LLM call
5. Fetch once per category, through the same 60-minute cache `run()` uses. The variant string
   is the category name with `_` → space; the profile's `experience` and first `preferred_work`
   become the fetch parameters
6. `deduplicate` → `classify(jobs, None)` — the intent fallback is deliberately `None`, so a job
   whose text names no category lands in `"other"` and is filtered out at step 7. A job earns
   its place in the feed by its own text
7. `_filter_feed` — keep only jobs whose **self-assigned** category is in the top categories,
   and drop any `job_id` in `rejected_jobs`
8. `encode(enrich_query(" ".join(categories), context))` — the preferences are the query vector
9. `rank()` → `CATEGORY_BOOST` applies, so within the feed a category scored 5 outranks one
   scored 1 at equal similarity → truncate to 12
10. `match_band(normalized_score)` → the FR-019 badge string, set here and not in Jinja

**Honest description, and it must stay in these words.** The feed runs a keyword search for
each of the user's top category *names* and re-ranks what comes back against their profile. It
does not discover jobs matching their taste, and it can return only what those three keyword
searches happened to fetch. Same recall ceiling as the search path.

**Why live fetching is affordable.** The variant strings are category names — a closed set of
13 — so every user and every visit shares the same cache keys. All feed traffic across the whole
app costs at most ~13 Adzuna calls per hour against a 250/day budget. This is the answer to the
quota question `docs/PROJECT_STATUS.md` carried as an open blocker.

**Why jobs outside the top categories are dropped, not just ranked lower.** TC-012 says rejected
categories are *absent*. "Ranked last of twelve on one page" is still present. A keyword fetch
for `writing` routinely returns jobs that classify as `technology`, so without this filter a
user with `technology = -2` still sees tech jobs on a feed that otherwise looks correct.

**Why an empty feed stays empty.** Falling back to the profile's skills would mean the feed is
never blank, but it would give "why do two users see different feeds?" two possible answers
instead of one — exactly the ambiguity TC-014 exists to rule out.

**Why there is no Groq call.** The feed is a browse surface, not a question. A second LLM call
per page load would buy an explanation of a query the user never typed, and FR-016's AI
Recommendations are specified against a search. Deliberate omission, not an oversight.

**Hand-picked numbers, same standing as `CATEGORY_BOOST`:** `FEED_CATEGORIES = 3`,
`FEED_LIMIT = 12`, and the `MATCH_BANDS` thresholds (85 / 65). `normalized_score` is relative to
the best match in the feed, so the top card is a "Top Match" by construction. TODO(M4).

Save and reject work on feed cards with no JavaScript change — `feed.html` and `index.html`
share one decision-group markup block and one `static/js/decisions.js`.

## Module layout (as built)

Matches SDD Appendix B. Every file named there exists; the ones not yet implemented are
stubs that `raise NotImplementedError` with the milestone that fills them in, rather than
`pass` — a stub that silently returns `None` is how an unimplemented function gets shipped.

```
app.py                          Flask app wiring only — no routes. Constructs
                                DatabaseManager, SemanticEngine and RAGPipeline, assembles
                                JobSearchAgent from them, and publishes the agent and the
                                database on app.config for the blueprints
config.py                       env-driven config, validate() fails loudly on a missing
                                key; also the closed vocabularies — CATEGORIES, WORK_TYPES,
                                EXPERIENCE_LEVELS — plus WORK_TYPE_HINTS and
                                QUERY_STOPWORDS, shared by intent_parser and api_client
controllers/
    auth_controller.py          BUILT — auth blueprint: register, login, logout,
                                require_auth, csrf_token/check_csrf
    ui_controller.py            PART BUILT — ui blueprint: search on "/" (M2), profile (M1),
                                feed (placeholder until M3); save_job/reject_job still stubs
core/
    semantic_engine.py          BUILT — SemanticEngine
    rag_pipeline.py             BUILT — RAGPipeline
    agent.py                    BUILT — JobSearchAgent; the pipeline orchestrator.
                                TC-006, TC-016 to TC-018, TC-021, TC-022
    intent_parser.py            BUILT — parse_intent (Groq + keyword fallback),
                                enrich_query; TC-019, TC-020
adapters/
    api_client.py               BUILT — Adzuna + Remotive fetch, one path only.
                                fetch_variant() returns jobs, failed_sources and
                                empty_sources separately; normalising is delegated to
                                JobCard. Also carries the per-source compensation, because
                                nothing above should know how either API misbehaves:
                                work-type words are stripped from Adzuna's keyword query
                                and passed as its own parameters instead, and Remotive --
                                which ignores its search parameter entirely -- is fetched
                                then FILTERED LOCALLY on the job title
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

**Deferral closed, 2026-09-20.** Appendix B describes `app.py` as an app factory whose search
route lives in `controllers/ui_controller.py` as a blueprint. The route was inline in `app.py`
from the 2026-09-13 restructure until now, because it was the one fully working code path and
the restructure was carried out as a pure move so identical behaviour could be verified before
and after.

`ui_controller.search` now serves `/` and calls `JobSearchAgent.run()`. The agent was built and
verified *beside* the working route rather than in place of it, so there was never a point
where the app was broken; this commit is the swap. The legacy `fetch_all_jobs` path went with
it — two fetch paths left standing is how the two drift apart.

The route stays on `/` rather than moving to `/search`: `verify_auth.py` measures TC-003 and
TC-005 on that URL, asserting 200 to a logged-in user and 302 to an anonymous one, and a
redirect hop would turn those 200s into 302s.

**Still deferred:** the `create_app()` factory itself. `app` is still a module-level object,
which `verify_auth.py` imports directly. The agent reaches the blueprint through
`app.config["AGENT"]`, the same indirection `app.config["DB"]` already used, so no controller
imports `app`. Converting to a factory is a refactor with nothing in M2 depending on it.

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
| Adzuna | Live job listings, **UK market only** — country is hardcoded in `api_client`, and `config.ADZUNA_COUNTRY` is currently dead config | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | 250 requests/day |
| Remotive | Remote job listings. Ignores `search`, `category` and `limit` alike — fetched once and filtered locally, capped at 18 jobs | none — no auth | none |
| Jobicy | Remote job listings **filtered by candidate eligibility** (`geo=anywhere`). Added 2026-09-23; the only free source that both searches and filters eligibility server-side | none — no auth | none published — treat as unknown |
| Groq | LLM inference — `openai/gpt-oss-120b`. **A reasoning model**: hidden reasoning tokens count against `max_tokens`, so both call-site budgets were raised. Llama 3 and then `groq/compound-mini` were each decommissioned by Groq; see `docs/PROJECT_SPEC.md` § Deviations | `GROQ_API_KEY` | free-tier rate limits |
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
