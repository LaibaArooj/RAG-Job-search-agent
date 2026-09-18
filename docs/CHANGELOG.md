# Changelog — RAG-Based Intelligent Job Search Agent

All notable changes, newest first. Claude appends an entry after each shipped feature.

## [Unreleased]

### Added
### Changed
### Fixed
### Removed

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
