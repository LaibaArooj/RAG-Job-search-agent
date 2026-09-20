# Changelog — RAG-Based Intelligent Job Search Agent

All notable changes, newest first. Claude appends an entry after each shipped feature.

## [Unreleased]

### Added
### Changed
### Fixed
### Removed

---

## 2026-09-20 — M2 route move: the app finally runs the agent

`JobSearchAgent` was proven on 2026-09-19 but nothing called it — the live route still ran the
old inline pipeline, so query expansion (TC-021) and the partial-source banner (TC-018) passed
in `verify_agent.py` and did not happen in the running app. `ui_controller.search` now serves
`/` and calls `agent.run()`. This closes the inline-route deferral recorded in
`docs/ARCHITECTURE.md` § Module layout and is the last build work in M2.

**Verified.** All four verify scripts pass — `verify_db.py` 27, `verify_auth.py` 31,
`verify_intent.py` 76 (live Groq call), `verify_agent.py` 57 — **191/191**. Then a live run
against the running dev server with real Adzuna, Remotive, Groq and Atlas: 32 ranked cards with
match badges and a populated AI panel, `GET /` with no error banner, TC-017 on an empty submit,
no raw dicts in the page, and `job_cache` holding one document per query *variant*, which is the
first direct evidence that query expansion runs in the live app.

### Added
- `controllers/ui_controller.search` — serves `/` for GET and POST. Thin by construction: check
  CSRF, call `_agent().run(current_username(), query)`, render the dict. It does not read the
  profile, strip the query or decide what an empty result means — the agent owns all three.
- `_agent()` beside the existing `_db()`, reading `current_app.config["AGENT"]`. Same
  indirection, same reason: a controller importing `app` is a circular import.
- `_blank_page()` — returns the identical key set `JobSearchAgent.run()` returns, so a GET and
  a CSRF-rejected POST hand the template exactly the variables a completed search does.
- `app.config["AGENT"] = JobSearchAgent(db, engine, rag)` in `app.py`. The one place the three
  collaborators are assembled, which is the point of taking them as constructor arguments.
- `index.html` renders `error` and `warning`. The agent has returned both on every exit path
  since 2026-09-19 and the template rendered neither. `warning` sits **above the result list,
  not instead of it** — that is the TC-018 distinction between "come back later" and "search
  for something else". They are template variables rather than flashed messages because
  `flash()` exists to carry a message across a redirect and this renders in the same request;
  it also avoids the flash block's category mapping, which renders anything that is not
  `error` as `alert-success` and would have shown a warning in green.

### Changed
- `GET /` deliberately does **not** call `agent.run()`. With an empty query the agent returns
  TC-017's "Please enter a search term", so calling it on arrival would open the search page
  with an error banner on every visit. That message belongs to an empty *submit*.
- The search route stays on `/` rather than moving to `/search`. `verify_auth.py` measures
  TC-003 and TC-005 on that URL — 200 logged in, 302 anonymous — and a redirect hop would turn
  those 200s into 302s.
- The endpoint is now `ui.search`, so the six `url_for("home")` call sites moved with it:
  `controllers/auth_controller.py` (register x2, login x2) and the nav bars in `feed.html` and
  `profile.html`. Missing one would be a `BuildError`, i.e. a 500 on a page that renders today.
- `app.py` is wiring only — no routes, and the unused `flash`, `render_template`, `request`,
  `require_auth`, `current_username` and `fetch_all_jobs` imports are gone.
- `requirements.txt` — the `requests` comment named `job_fetcher`, a module renamed to
  `adapters/api_client.py` on 2026-09-13.

### Removed
- `fetch_all_jobs`, `fetch_adzuna_jobs` and `fetch_remotive_jobs` from
  `adapters/api_client.py`. The inline route was their only caller. All three returned `[]` for
  a rate limit and `[]` for a genuine zero-result search alike, which is exactly the ambiguity
  `fetch_variant`'s `failed_sources` was added to resolve, and they still carried the
  pre-`JobCard` inline normalising — the code that once rendered Python dicts into the page.
  Preserved in git history.
- The inline `home()` route from `app.py`.

### Known gaps
- **Remotive has stopped honouring `search`.** Found by the live run, which is exactly what an
  offline verify script cannot find. The endpoint returns the same fixed 17-job list for every
  query — confirmed with `nurse`, `accountant`, `qwertyuiop` and with no parameters at all — and
  ignores `limit` too. Consequences: one of the two sources contributes a constant,
  query-independent 17 jobs to every search; `MSG_NO_RESULTS` is unreachable in production
  because the pool is never empty; a gibberish query renders 17 irrelevant cards with high match
  badges; and M4's precision@5 would be measured over polluted candidate pools. Not fixed — the
  SRS names Remotive as a source and the options are design decisions. Written up with three
  options in `docs/PROJECT_STATUS.md`.
- The old route flashed *"Could not load your profile; showing unpersonalised results."* when
  `get_user_context` failed. `JobSearchAgent.run` catches that, prints, and continues
  unpersonalised — correct, but now silent to the user. Surfacing it means adding a key to the
  agent's return dict, which breaks the "same keys on every exit path" invariant
  `verify_agent.py` asserts. Left as a gap rather than widening M2.
- The agent logs with `print`, not `current_app.logger`, because `core/` must not import Flask.
  That is a layering consequence, not an oversight — be ready to say so.

---

## 2026-09-19 — M2 search pipeline (`JobSearchAgent` + `JobCard`)

The pipeline is assembled. `core/agent.py` and `models/job_card.py` are implemented and
`verify_agent.py` passes 57/57 with no live calls at all. TC-021 is now genuinely covered:
`parse_intent` has been producing query variants since the previous entry, and as of this one
something finally consumes them. `verify_intent.py` (76), `verify_auth.py` (31) and
`verify_db.py` (27) all still pass — 191 checks green in total.

The search route in `app.py` is deliberately untouched and still serves. Moving it into
`ui_controller.search` is the next task.

### Added
- `core/agent.py` — `JobSearchAgent`, the orchestrator. Reads the profile, parses intent,
  enriches and encodes the query, fetches once per variant, unions and deduplicates, re-ranks,
  and hands the top 5 to `RAGPipeline`. Returns one dict with the same keys on every exit
  path, so the route never has to work out which branch produced its result.
- `models/job_card.py` — one place where an Adzuna/Remotive field-shape difference is resolved.
  `make_job_id` is a SHA-256 of lowercased, stripped `title|company`, truncated to 16 hex
  characters. Lowercasing is what makes TC-022 work: a syndicated listing arrives at the two
  APIs with different casing, and a byte-exact comparison would call the copies different jobs.
  The `|` separator stops `("Data", "Xco")` and `("DataX", "co")` hashing alike.
- `adapters/api_client.fetch_variant` — returns `{"jobs": [...], "failed_sources": [...]}`.
  This is the signal TC-018 needed and did not have: every existing fetch function returns
  `[]` for a 429 and `[]` for a genuine zero-result search, so the caller could not tell
  "come back later" from "search for something else". The two now give different messages.
- The 60-minute job cache is in use for the first time. `cache_get`/`cache_put` existed and
  were dead code. Keyed on a SHA-256 of the **variant** string rather than the user's query,
  so two searches that expand onto a shared phrasing reuse one fetch. Three variants against a
  250/day Adzuna budget is the quota risk `PROJECT_STATUS.md` has been flagging. A *partial*
  fetch is never cached, or an outage would outlive the API's recovery by an hour.
- `verify_agent.py` — 57 checks, entirely offline. Every collaborator is a double, which is
  the whole reason `JobSearchAgent.__init__` takes them as arguments. Covers TC-006, TC-016,
  TC-017, TC-018, TC-021, TC-022, the RAG fallback, both cache paths, and JobCard against
  missing nested objects. Three of the cases are only provable with doubles: TC-017 asserts
  that **no** call happened, which needs a counter rather than a return value; TC-018 needs
  Adzuna to fail on demand; TC-006 needs similarity scores fixed in advance so the expected
  order is known.

### Changed
- Deduplication now keys on `job_id` instead of a concatenated `title + company` string, and
  keeps the **first** occurrence. That is a decision, not an accident: `parse_intent`
  guarantees the user's own phrasing is `variants[0]`, so query expansion can only ever add to
  the candidate pool and never reorder what the user would have seen without it.
- Ranking sorts on a new `final_score` (similarity + category boost) rather than on
  `similarity_score`, which is retained for display and for the M4 evaluation. `normalized_score`
  is unchanged in meaning — a percentage relative to the best match in that result set, not an
  absolute quality score.
- `docs/ARCHITECTURE.md` step 5 rewritten. The SDD's parallel fork is **not built**; fetching
  is sequential. Recorded as a deliberate deferral with its reasoning rather than left as a
  spec the code silently contradicts. The `Parallel fetch` row in `docs/LEARNING_LOG.md` now
  says the same thing — claiming it works in a viva when the code loops is the worst answer.
- `docs/LEARNING_LOG.md` — two rows added: **dependency injection / test doubles**, and
  **hashing as an identity, not as a secret** (SHA-256 does two unrelated jobs in this project
  and neither is security, which is the contrast with the password-hashing row).

### Fixed
- `JobCard.from_adzuna` tolerates a missing `company` or `location` object. The old inline
  normalising chained `.get` on the nested object and would raise when Adzuna omitted it —
  this is the descendant of the bug that once rendered Python dicts into the page.

---

## 2026-09-19 — M2 intent parsing (first M2 component)

`core/intent_parser.py` implemented. TC-019 and TC-020 pass; `verify_intent.py` runs 76 checks
with 0 failures, including a live Groq call. TC-021 (query expansion) is **not** covered yet —
`parse_intent` produces the variants but nothing consumes them until `JobSearchAgent` lands.

### Added
- `core/intent_parser.py` — `parse_intent` asks Groq for work type, experience, category and
  2–3 query variants as JSON; `_parse_intent_keywords` is the FR-018 fallback. Both paths
  return the identical dict shape, so `JobSearchAgent` never branches on which one ran; the
  `source` field records it for the report only.
- Validation separated from parsing. Groq's reply is treated as untrusted input: every field is
  checked for membership in a closed set on the way out, unrecognised values become `None` and
  an unrecognised category becomes `"other"`. The prompt steers the model; the membership test
  is what actually guarantees the closed set.
- `enrich_query` relocated from the inline search route in `app.py`, wording unchanged — that
  route is the code path already demonstrated to satisfy TC-016, so a rewrite would have
  invalidated the evidence.
- `verify_intent.py` — 76 standalone checks: canonical shape on both paths, TC-020 with the
  Groq client stubbed to raise, non-JSON and markdown-fenced replies, four hostile categories
  (`technology.$ne`, `$where`, `technology.admin`, `a.b.c`) all collapsing to `"other"`,
  variant capping and deduplication, TC-017's no-call-on-empty-query, and a live TC-019 call.
- `config.WORK_TYPES` and `config.EXPERIENCE_LEVELS`.

### Changed
- `WORK_TYPES` and `EXPERIENCE_LEVELS` moved from `controllers/ui_controller.py` to `config.py`;
  the controller now imports them. `intent_parser` must validate against the same sets, and an
  AI-layer module importing from a controller both inverts the SDD layering and deadlocks:
  `ui_controller` → `core.agent` → `core.intent_parser` → `ui_controller` fails with
  "partially initialized module". Reproduced before fixing. **The cycle was order-dependent** —
  it passed with the import at the bottom of the file and failed at the top, where PEP 8 puts
  it, which is why it needed fixing rather than avoiding. No behaviour change; `verify_auth.py`
  still passes 31/31.
- `docs/LEARNING_LOG.md` — two rows added: circular imports / partially initialized modules,
  and validating LLM output against a closed set.

### Known gaps
- TC-019's expected category is "creative", which is not in `CATEGORIES`. The prompt asks for
  the single closest member instead, and the check accepts `writing` or `design`; the live run
  returned `design`. Recorded here rather than widening the vocabulary, which is shared with
  the M3 scoring loop.
- The keyword fallback's synonym lists are hand-written and English-only. They are the crude
  path by design, but the coverage is not measured.

---

## 2026-09-19 — M1 auth, session and profile

The Atlas blocker cleared: `verify_db.py` now reaches the cluster and passes 27/27, so the
routes above the data layer could finally be built. TC-001 to TC-005 pass.

### Added
- `controllers/auth_controller.py` — `auth` blueprint: `/register`, `/login`, `/logout`,
  the `require_auth` decorator, and hand-rolled CSRF (`csrf_token`, `check_csrf`). The only
  module importing `werkzeug.security`. Passwords are hashed here; the database layer only
  ever receives a hash.
- `controllers/ui_controller.py` — `ui` blueprint with `/profile` (view **and** edit) and
  `/feed`. The feed is registered and protected now so TC-005 is testable; its ranking is
  still M3 and says so on the page rather than rendering a plausible-looking empty feed.
- `templates/login.html` — **it never existed.** The version at `5519a22` rendered it, so
  TC-003 and TC-004 would both have raised `TemplateNotFound`.
- `verify_auth.py` — 31 pass/fail checks over the real routes, real session cookie and real
  Atlas, via Flask's test client. No new dependency; mirrors `verify_db.py`.
- Profile edit form, and a nav bar plus flash-message block on `index.html`, which the other
  templates already assumed existed.
- `models/user.py` — `from_document` / `to_document` implemented.

### Changed
- CSRF is a per-session random token compared with `hmac.compare_digest`, not Flask-WTF.
  No new dependency, and the mechanism is explainable line by line.
- Login reports one message for an unknown username and for a wrong password, so the form is
  not a username oracle. `session.clear()` precedes granting a session, against fixation.
- The search route is now `@require_auth` and re-injects the user's skills and experience
  into the query text before encoding — restoring the TC-016 behaviour the simplified demo
  `app.py` had dropped.
- Minimum password length set at 8, enforced server-side and hinted in the form. The SRS says
  "strong password" without quantifying it; this is the quantification.
- `/profile` whitelists submitted **values** (experience level, work type) as well as the
  fields `update_profile` already whitelisted.

### Fixed
- **No fallback secret key.** `5519a22` used `os.getenv("SECRET_KEY", "fallback_secret_key")`;
  a known signing key lets anyone forge a session cookie for any username. A missing
  `FLASK_SECRET_KEY` is now fatal at startup.
- The env var name is `FLASK_SECRET_KEY`, matching `config.py` and `.env.example`. The old
  code read `SECRET_KEY`, which was never defined anywhere.
- `index.html` credited "Gemini AI" for the recommendations. It is Groq.
- Template `url_for` targets now name blueprint endpoints (`auth.login`, `ui.profile`, …).

---

## 2026-09-13 — M1 database layer built

### Added
- `adapters/db_manager.py` — `DatabaseManager`, the only PyMongo consumer in the project.
  Lazy connection (an Atlas outage no longer crashes startup), unique `username` index,
  `job_cache` TTL index, save/reject scoring, search history, top-category feed input.
- `verify_db.py` — standalone pass/fail check of every method against a throwaway user,
  asserting TC-001, TC-002, TC-010, TC-011, TC-012 and TC-013. Cleans up after itself.
  Includes `diagnose_connection()`, which reports which layer a failed connection stops at
  (DNS / TCP / TLS / auth) instead of blaming the credential by default.
- `config.CATEGORIES` — one closed category vocabulary, shared by intent parsing and the
  scoring loop, and the whitelist that makes the field-path injection impossible.
- `config.JOB_CACHE_TTL_MINUTES = 60` — spec value, configurable without a code edit.
- `docs/PROJECT_SPEC.md` now records TC-001 to TC-018 verbatim, extracted from
  `SRS_FORMATTED.docx`. They were previously only in the Word document.

### Changed
- **Deviation 5** — `rejected_jobs` stores `job_id` rather than job titles. Titles are not
  unique across employers, so title-keyed rejection would hide every job sharing a title.
  Field type is unchanged (still `Array<String>`). **Needs supervisor sign-off.**
- `save_job` / `reject_job` are a single atomic conditional update rather than read-then-write.
  The filter requires the job not already be in the list, so a repeat click matches no
  document and the score cannot move twice — TC-013 holds by construction, with no race.
- `core/intent_parser.py` imports `CATEGORIES` from config instead of defining an empty tuple.

### Fixed
- **Test-case ids in the stubs were wrong.** They were written from memory last session rather
  than from the SRS: save/reject were labelled TC-009/TC-011 when the real ids are TC-010/TC-011,
  duplicate-save is TC-013, dedupe is TC-022 not TC-017, and TC-008 is the RAG response, not the
  profile page. Corrected across `controllers/`, `core/agent.py` and `models/job_card.py`.
- **The recorded M1 blocker was misdiagnosed.** `PROJECT_STATUS` said the Atlas password needed
  resetting. A layer-by-layer probe shows DNS resolves, TCP connects in 0.1 s, but the TLS
  handshake on port 27017 times out and resets on all three shards, while TLS on :443 completes
  normally. Authentication happens after the handshake, so the credential was never reached.

### Known blocker
- No connection to Atlas from this machine on port 27017. The data layer is complete and every
  offline check passes; nothing past the ping can be verified until the port is reachable.

---


## 2026-09-13 — Restructured into the SDD Appendix B module layout

### Added
- `controllers/`, `core/`, `adapters/`, `models/`, `static/`, `tests/` packages. Every file
  named in SDD Appendix B now exists. Unimplemented ones are stubs that
  `raise NotImplementedError("M1"/"M2"/"M3")` with the covering TC ids in the docstring —
  not `pass`, which returns `None` silently and is how a stub reaches a demo unnoticed.
- `config.py` — all secrets read from `.env`, plus `validate()` which raises `ConfigError`
  naming every missing required variable at startup. A missing key now fails with its own
  name rather than as an opaque 401 from a provider later.
- `README.md` — setup, run, layout, and an honest statement of what the system does
  (re-ranks the keyword-search pool; does not retrieve past it).
- `adapters/db_manager.py` stub records the three defects in the deleted `models.py` that
  must not be reintroduced, and notes `datetime.utcnow()` is deprecated from Python 3.12.

### Changed
- `semantic_engine.py` → `core/semantic_engine.py`, `rag_pipeline.py` → `core/rag_pipeline.py`,
  `job_fetcher.py` → `adapters/api_client.py`, all via `git mv` so `git log --follow` keeps
  the debugging history these files carry. Contents unchanged.
- `app.py` — import paths only. The search route stays inline rather than moving to
  `controllers/ui_controller.py`; it is the one working code path, and the restructure was
  done as a pure move so identical behaviour could be verified. Deferred to M2 and recorded
  in `docs/ARCHITECTURE.md` § Module layout (as built).
- `MONGODB_URI` settled as the single spelling across code and docs; `MONGO_URI` retired.

### Removed
- `models.py`. It could not coexist with the `models/` package — Python resolves the name to
  one and the other silently vanishes — and was already dead code, imported by nothing. Its
  functions are carried forward as named stubs in `adapters/db_manager.py`. Preserved in git
  history at `5519a22` together with the auth routes M1 restores.
- Stale `__pycache__/`, compiled by Python 3.14.6 for modules that have since moved.

### Verified
- Baseline query "remote python developer" returns **24 deduplicated jobs from both Adzuna
  and Remotive**, ranks them (top: Python Developer / IB Talent Search, 0.674), and Groq
  returns a populated recommendation panel — identical to the 2026-09-13 pre-move baseline.

---

## 2026-09-13 — Search demo runs end to end

### Added
- `RAGPipeline` rebuilt against Groq, with `fallback()` satisfying FR-018: a Groq failure is
  caught and logged, the AI Recommendations panel hides, and the ranked results still render.
- `requirements.txt` — curated direct dependencies with pinned versions.

### Changed
- LLM model is now `groq/compound-mini`. Groq decommissioned Llama 3 mid-project; this is a
  forced substitution recorded in `docs/PROJECT_SPEC.md` § Deviations and **needs supervisor
  sign-off**. The model id is isolated in one constant, so a revert is one line.
- `app.py` calls `fetch_all_jobs()` instead of hitting Adzuna inline. This restores Remotive
  as a source, restores title+company deduplication, and keeps `requests` out of the route
  layer as the SDD requires.

### Fixed
- `rag_pipeline.py` had been overwritten with a byte-identical copy of `app.py`, so it imported
  `RAGPipeline` from itself and the app could not start at all.
- Adzuna returns `company` and `location` as nested objects. The inline fetch passed them to
  the template raw, which rendered them as Python dicts and left job links empty.
- Normalised-score divide is guarded — a zero or negative top similarity raised
  `ZeroDivisionError`, which would have shown a stack trace.
- `.gitignore` listed `models/`, which would have silently ignored the SDD's `models/` package.
- MongoDB URI username contained a Cyrillic `а` (U+0430) instead of Latin `a`, causing Atlas
  `bad auth`. Fixed; the DB user password is still outstanding.

### Removed
- Stale prototype scripts: the Gemini `rag_pipeline.py`, `test_groq.py`, `test_semantic.py`.

---

## 2026-09-11 — Project initialised

### Added
- PSB scaffold: project spec, CLAUDE.md, docs, commands and subagents.
