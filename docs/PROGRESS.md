# Project Progress — RAG-Based Intelligent Job Search Agent

**Laiba Arooj** · Dept. of Computer Science · Supervisor: Dr Ali Sammad
Final Year Project · Progress consolidated **2026-09-22**

> A single-file record of everything built so far, what is verified, what is deliberately not
> built, and what remains. This is a *derived* document — the sources of truth stay where they
> are: `PROJECT_SPEC.md` (requirements), `ARCHITECTURE.md` (design), `PROJECT_STATUS.md`
> (session notes), `CHANGELOG.md` (dated history), `EVALUATION.md` (the measurement plan).
> When this file disagrees with one of those, they win.

---

## 1. Where the project stands

| | |
|---|---|
| Current milestone | **M4 — evaluation (precision@5), filters, autocomplete, demo** |
| Milestones complete | M1, M2, M3 |
| Branch | `feat/search-pipeline` |
| Last commit | `e69bcd6 add verify_live.py and verify_all.py` |
| Automated checks | **348 assertions** across six scripts — 320 offline, 28 live |
| Time remaining | under one month to submission |

Three of four build milestones are closed. The remaining work is **measurement and polish**,
not construction: the one claim the project makes that has no evidence behind it yet is that
semantic ranking beats keyword ranking.

---

## 2. What the system does, stated accurately

1. The plain-English query goes to a Groq-hosted LLM, which returns **structured intent**
   (work type, experience level, category) plus 2–3 alternative phrasings.
2. Each phrasing is sent to **Adzuna** and **Remotive**. Results are unioned and deduplicated
   on `job_id`, first occurrence winning.
3. A locally-run sentence-transformer (`all-MiniLM-L6-v2`, 384-dim) embeds the query and every
   job and **re-ranks** them by cosine similarity, plus a category boost.
4. The top 5 go back to the LLM, which returns three explained picks.
5. Save / reject moves a per-category integer score, which feeds both later rankings and the
   For You feed.

**The honest framing, used everywhere in the code and required in the report:** this is semantic
**re-ranking** of the pool keyword search returns. It cannot retrieve a job the APIs never
fetched. Query expansion widens the pool; it does not remove the ceiling.

---

## 3. Milestone record

| # | Milestone | Status | Evidence |
|---|---|---|---|
| M1 | Auth, profile, database | **Done 2026-09-19** | `verify_auth.py` 31/31, `verify_db.py` 27/27; TC-001–TC-005 |
| M2 | Search pipeline: LLM intent, query expansion, dedupe, semantic ranking | **Done 2026-09-20** | 221 assertions across four scripts + a live end-to-end run against the running server |
| M3 | RAG, save/reject learning, For You feed | **Done 2026-09-21** | `verify_agent.py` 129/129, `verify_routes.py` 57/57; 320 offline green |
| M4 | Evaluation (precision@5), filters, autocomplete, full test pass, demo | **In progress** | — |

### M1 — foundation (2026-09-13 → 2026-09-19)

- `DatabaseManager` built against live MongoDB Atlas; single denormalised user document.
- Registration, login, logout, profile edit as Flask blueprints (`auth`, `ui`).
- Werkzeug password hashing; no plain-text password anywhere.
- CSRF hand-rolled — a per-session random token, injected by a Jinja context processor,
  compared with `hmac.compare_digest`. Chosen over Flask-WTF to avoid a dependency and because
  the mechanism has to be explainable in a viva.
- Module layout restructured to SDD Appendix B (`controllers/`, `core/`, `adapters/`,
  `models/`) with `git mv`; demo verified unchanged after the move.
- Four defects in the inherited `5519a22` auth code were found and fixed: a template that had
  never existed, a hardcoded `SECRET_KEY` fallback (session forgery), a wrong env var name, and
  a plain password passed to `create_user`.

### M2 — search pipeline (2026-09-19 → 2026-09-20)

- `parse_intent` calls Groq for structured intent + query variants, with keyword matching as
  the fallback path (TC-019, TC-020).
- `JobSearchAgent.run()` orchestrates: intent → fetch per variant → dedupe → embed → re-rank →
  RAG. `JobCard` normalises the two APIs' disagreeing shapes.
- The search route moved out of `app.py` into `ui_controller.search`; the legacy
  `fetch_all_jobs` / `fetch_adzuna_jobs` / `fetch_remotive_jobs` trio was deleted, leaving one
  fetch path. Until this commit TC-021 and TC-018 passed in tests and **did not happen in the
  running app**.
- The 60-minute `job_cache` was dead code and is now wired in, keyed on a SHA-256 of the
  *variant* string, so overlapping searches share a fetch. A partial fetch is never cached.
- A rate-limited source and an empty result set are now different events — `fetch_variant`
  reports `failed_sources` separately, which is what makes TC-018's banner implementable.

### M3 — learning loop and feed (2026-09-21)

- **Categorisation:** every job is classified locally from its own title and first 500
  characters against `config.CATEGORY_HINTS`, by `core.intent_parser.classify_category` — the
  same table and matcher the `parse_intent` keyword fallback uses. Neither API's taxonomy is
  used. First matching key wins, so the **order of `CATEGORY_HINTS` is the tie-break rule**.
- **Save / reject:** both routes exist, answer with JSON rather than a redirect, and
  `static/js/decisions.js` flips the button without a reload. The posted body is form-encoded
  so the existing `check_csrf()` (which reads `request.form`) keeps working.
- **For You feed:** `build_feed` is the agent's second entry point; `/feed` renders real cards
  with a match badge. Jobs outside the user's top categories are **dropped, not ranked lower** —
  TC-012 requires rejected categories to be *absent*, and "ranked last on one page" is still
  present.
- Two latent defects were found by wiring it up rather than by testing: the category boost was
  contributing exactly 0 in production because `JobCard.category` was `""` on every job, and
  `feed.html` posted `category="{{ job.source | lower }}"` (i.e. `adzuna`), which would have
  raised `ValueError` out of `_score_path` and reached the user as a 500.

### M4 — remaining (not started)

1. **precision@5 evaluation** — write the 20 queries *before* looking at any results, freeze the
   API responses as JSON fixtures, define relevance in writing, judge blind. See
   `docs/EVALUATION.md`. Budget one day.
2. **Filters** (TC-015, remote filter) and **autocomplete** (TC-007).
3. **Demo rehearsal in a real browser** while logged in — still outstanding.
4. Justify or tune the hand-picked constants: `CATEGORY_BOOST = 0.02`, `FEED_CATEGORIES = 3`,
   `FEED_LIMIT = 12`, and the 85 / 65 match-band thresholds.

---

## 4. Test case coverage

SRS test cases TC-001 to TC-018, plus TC-019 to TC-022 added for the deviations.

| TC | What it checks | Covered by | Status |
|---|---|---|---|
| TC-001 | Registration — valid | `verify_db.py`, `verify_auth.py` | ✅ |
| TC-002 | Registration — duplicate username | `verify_db.py`, `verify_auth.py` | ✅ |
| TC-003 | Login — correct credentials | `verify_auth.py` | ✅ |
| TC-004 | Login — incorrect password | `verify_auth.py` | ✅ |
| TC-005 | Unauthenticated access redirects | `verify_auth.py`, `verify_routes.py` | ✅ |
| TC-006 | Semantic search — intent match | `verify_agent.py`, `verify_live.py` | ✅ |
| TC-007 | Autocomplete — partial match | — | ❌ **M4, not built** |
| TC-008 | RAG LLM response | `verify_live.py` | ✅ (live only) |
| TC-009 | LLM unavailable — section hidden, no crash | — | ⚠️ **implemented, not asserted** |
| TC-010 | Save job — score +1 | `verify_db.py`, `verify_routes.py` | ✅ |
| TC-011 | Reject job — score −1 | `verify_db.py`, `verify_routes.py`, `verify_agent.py` | ✅ |
| TC-012 | For You feed — personalised, rejected absent | `verify_db.py`, `verify_routes.py`, `verify_agent.py` | ✅ |
| TC-013 | Same job saved twice — no double increment | `verify_db.py`, `verify_routes.py` | ✅ |
| TC-014 | Two users — different feeds | `verify_agent.py` | ✅ |
| TC-015 | Filter by remote | — | ❌ **M4, not built** |
| TC-016 | Profile context injection | `verify_intent.py`, `verify_agent.py` | ✅ |
| TC-017 | Empty search — no API call | `verify_intent.py`, `verify_agent.py`, `verify_live.py` | ✅ |
| TC-018 | API rate limit — friendly banner | `verify_agent.py`, `verify_live.py` | ✅ |
| TC-019 | LLM intent parsing | `verify_intent.py` | ✅ |
| TC-020 | Intent parsing fallback | `verify_intent.py` | ✅ |
| TC-021 | Query expansion | `verify_agent.py`, `verify_routes.py`, `verify_live.py` | ✅ |
| TC-022 | Cross-source deduplication | `verify_agent.py` | ✅ |

**19 of 22 asserted.** Three gaps, all known: TC-007 and TC-015 are unbuilt M4 features, and
**TC-009's fallback is implemented but has no assertion naming it** — worth closing in M4,
because it is the test case that backs FR-018's "never crashes when the LLM is unavailable".

---

## 5. Verification suite

`verify_*.py` are standalone pass/fail scripts, not pytest — pytest is not a dependency.

| Script | Asserts | Touches | Purpose |
|---|---|---|---|
| `verify_db.py` | 27 | Atlas | the data layer |
| `verify_auth.py` | 31 | Atlas | auth routes, TC-001–TC-005 |
| `verify_routes.py` | 57 | Atlas | save/reject, categorisation, `/feed` |
| `verify_intent.py` | 76 | Groq | intent parsing, TC-019/TC-020 |
| `verify_agent.py` | 129 | nothing | the pipeline and the feed — fully offline |
| `verify_live.py` | 28 | Adzuna, Remotive, Groq | real end-to-end + rendered pages |
| **`verify_all.py`** | **348** | all | the pre-demo check, ~150s. `--offline` skips the quota-spending one |

`verify_agent.py` runs offline in about a second because `JobSearchAgent.__init__` takes `db`,
`semantic_engine` and `rag_pipeline` as arguments. The sharp follow-up to have ready: *which
assertions could not be written without doubles?* The TC-017 ones — proving a call did **not**
happen needs a call counter, not a return value.

Everything except `verify_agent.py` touches a live service, so a failure can mean an outage
rather than a regression. Read which check failed before assuming the code broke.

---

## 6. Architecture as built

Strict layering, enforced. Each of these is the **only** class allowed to touch its dependency:

| Facade | Sole owner of |
|---|---|
| `DatabaseManager` (`adapters/db_manager.py`) | PyMongo |
| `APIClient` (`adapters/api_client.py`) | `requests` |
| `SemanticEngine` (`core/semantic_engine.py`) | sentence-transformers |

```
app.py                     wiring only; agent reaches blueprints via app.config["AGENT"]
controllers/  auth_controller.py   register, login, logout, profile
              ui_controller.py     search (/), feed, save, reject
core/         agent.py             JobSearchAgent — run() and build_feed()
              intent_parser.py     parse_intent, classify_category
              semantic_engine.py   embed + cosine re-rank
              rag_pipeline.py      Groq call for the three explained picks; GROQ_MODEL lives here
adapters/     api_client.py        Adzuna + Remotive
              db_manager.py        Atlas
models/       job_card.py          normalises the two API shapes; holds no policy
              user.py
templates/    index.html  feed.html  login.html  register.html  profile.html
static/       css/style.css   js/decisions.js
```

### Stack

Python 3.11 (see environment note) · Flask 3.0+ · Jinja2 + Bootstrap 5.3, no JS framework ·
MongoDB Atlas 7.0+ via PyMongo 4.6+ · sentence-transformers `all-MiniLM-L6-v2` (local, 384-dim) ·
Groq `groq/compound-mini` · Werkzeug hashing · Adzuna (250/day) + Remotive.

Hard SRS constraint, honoured throughout: **every tool, API and service is free with no credit
card.** No vector database — embeddings are computed per request and discarded by design.

---

## 7. Design decisions worth defending

Collected from the session notes, because each is a plausible viva question.

**Pipeline**

1. **Dedupe keeps the FIRST occurrence.** `parse_intent` guarantees the user's own phrasing is
   `variants[0]`, so expansion can only widen the pool, never reorder what the user would have
   seen without it. Last-wins would have inverted what TC-021 measures.
2. **A rate-limited source ≠ an empty result set.** Separate reporting is what makes TC-018's
   banner possible.
3. **Fetching is sequential, not forked.** The SDD's parallel fork is *not built*, and the demo
   is correspondingly slow. Recorded as a deferral with the trade written down: a threading bug
   that intermittently drops one variant's results is harder to notice and harder to defend
   than a slow search. **Do not claim the fork works.**
4. **`GET /` deliberately does not call `agent.run()`.** With an empty query the agent returns
   TC-017's error, so calling it on arrival would greet every visitor with an error banner.
5. **The route stayed on `/` instead of moving to `/search`.** `verify_auth.py` measures TC-003
   and TC-005 on that URL — 200 logged in, 302 anonymous. A `/search` route with `/` redirecting
   would turn those 200s into 302s and break a green M1 suite to satisfy a URL preference.

**Categorisation and the learning loop**

6. **Classification happens in the agent, not in `JobCard.from_adzuna`.** `JobCard` normalises
   shape; category is *policy* — it decides what save/reject increments and what the boost
   reads. Doing it in the agent also covers jobs read back out of the cache, so there is exactly
   one place a category is ever assigned.
7. **The job's own text beats the query's category.** TC-011 is the reason: rejecting a tech job
   must lower the *tech* score, even during a writing search.
8. **The save/reject routes answer with JSON, not a redirect.** The ranked list exists only in
   the response that rendered it, so POST-redirect-GET would either lose the results or re-run
   the whole pipeline — a second Groq call included — on every click.
9. **A bad category is a 400, not a 500.** `_score_path` raises `ValueError` because the
   category reaches a MongoDB field path; the route check is what makes the status code tell the
   truth. Both checks stay.
10. **`already: true` is a success, not an error.** A second save matches no document, so nothing
    is pushed and nothing incremented — TC-013 enforced by the filter, not by a prior read.

**The feed**

11. **`classify(jobs, None)` in the feed, not `classify(jobs, intent_category)`.** The feed has
    no single query, so a job that names no category has nothing to borrow; it lands in `"other"`
    and the filter drops it. A job earns its place by its own text.
12. **No Groq call on the feed.** It is a browse surface, not a question. Deliberate omission;
    FR-016's AI Recommendations are specified against a search.
13. **A context-read failure is fatal to the feed, unlike in `run()`.** Search degrades to
    unpersonalised because it still has a query; the feed has nothing else — the scores *are*
    the input.
14. **A preference-less user gets the empty state, not a profile-based fallback.** A fallback
    would give "why do two users see different feeds?" two possible answers instead of one,
    which is the exact ambiguity TC-014 exists to rule out.
15. **TC-014 is asserted as disjointness, not difference.** Two users with opposite scores must
    share *no* job. Asserting only that the lists differ would pass on a one-job overlap.
16. **`normalized_score` is relative to the best match in the feed**, so the top card is a
    "Top Match" **by construction**. Say this before an examiner finds it.

**Quota**

17. **Feed traffic is cheap and the number is known.** The feed's fetch variant is a *category
    name*, and `CATEGORIES` is a closed set of 13 strings, so every user and every visit shares
    the same 60-minute cache keys: at most ~13 Adzuna calls per hour against 250/day. A user
    with no positive scores returns before any fetch at all.

---

## 8. Deviations from SRS v1.0 — five, all to be declared

| Change | SRS said | Now | Why |
|---|---|---|---|
| Intent parsing | keyword if-statements (SDD §5.1) | Groq structured JSON, keywords as fallback | the SRS defines an Agent as autonomous; if-statements aren't |
| Query strategy | one API call per search | 2–3 LLM variants, unioned and deduped | addresses the recall ceiling |
| Evaluation | not specified | precision@5 over 20 queries | the project's central claim needs evidence |
| **LLM model** | **Llama 3 8B via Groq** | **`groq/compound-mini`** | **forced — Groq decommissioned it mid-implementation** |
| `rejected_jobs` | array of job **titles** | array of **`job_id`** | titles aren't unique across employers; TC-012 needs absence, and title-keyed rejection would hide every "Software Engineer" everywhere |

The model substitution is **forced, not chosen** — verified against the live model list on
2026-09-13: `llama3-8b-8192` returns *decommissioned*, `llama-3.1-8b-instant` returns *404*, and
no Llama chat model remains on the account. `GROQ_MODEL` is a single constant in
`rag_pipeline.py`, so a revert is one line. **Never claim the system runs Llama 3.**

**Needs supervisor sign-off:** the model retirement, and the still-undecided swap of
`all-MiniLM-L6-v2` for `msmarco-MiniLM-L6-v3` (trained for short-query-to-long-document matching
rather than sentence-to-sentence — a one-string change that deviates from the SRS).

---

## 9. Known limitations — to be written up, not hidden

1. **Recall is bounded by keyword search.** Semantic *re-ranking*, not semantic *retrieval*.
2. **No persistent vector index** — justified (the corpus is external and volatile), but
   embedding cost is paid per request and no cross-session retrieval is possible.
3. **Truncation** — MiniLM's 256-token limit means roughly only the first paragraph of each
   description is embedded.
4. **The 0.02 boost coefficient is unjustified** — hand-picked, not tuned. Cosine similarities
   cluster narrowly, so a category score of 5 shifts ranking materially.
5. **LLM explanations are unverifiable** — fluent whether or not the match is real. The UI
   labels the section AI-generated; a mitigation, not a fix.
6. **Preference learning is shallow** — one integer per category, ±1, no decay, no notion of
   *why* a job was rejected.
7. **Cold start** — personalisation contributes nothing until several interactions.
8. **No evaluation of the LLM stage** — precision@5 measures the ranking only.
9. **Categories are assigned by substring keyword matching**, first match winning. Not
   classification by meaning; the report must not describe it as such.
10. **Remotive is fetched then filtered locally** — see below.

### The Remotive finding (2026-09-20) — must be stated in the report

Remotive's API ignores `search` and `limit` entirely and returns the same fixed ~20-job list for
every request, verified with no parameters at all. It is now fetched once and **filtered locally**
in `adapters/api_client.py`: a job is kept only if a meaningful query word appears in its
**title** (word match tolerating an inflected ending, so "engineer" matches "Engineering" but
"car" does not match "Cardiac"), and titles contradicting a parsed experience level are dropped.

Adzuna is untouched by the level filter on purpose: it ran a real keyword search, so its results
are earned and overruling them would be second-guessing a genuine match.

What this bought, measured: `MSG_NO_RESULTS` is **reachable again** — it had been dead code in
production because the pool was never empty, and a gibberish query previously rendered 17 senior
jobs. An entry-level query now keeps **0 of the 11 senior-titled** jobs in the live feed.

**This changes what the evaluation baseline means.** Adzuna's contribution is a genuine keyword
ranking; Remotive's order is query-independent. Report **precision@5 over Adzuna-only** as the
headline contrast and the two-source numbers separately, with the caveat attached. Do not present
a single blended number as "keyword baseline vs semantic ranking".

---

## 10. Environment

Rebuilt 2026-09-20 after the project was copied from another machine and arrived with a dead venv
and no interpreter.

- **Python 3.12.10** — neither the SRS's 3.11 nor the old 3.14.6. **Still a deviation to record
  or close.**
- `python` on PATH is only the Microsoft Store stub; use `venv\Scripts\python.exe` explicitly.
- **`git` is not on PATH** — it lives at `C:\Program Files\Git\cmd\git.exe`. The repo also needed
  `git config --global --add safe.directory E:/RAG-Job-search-agent`, because the working tree is
  still owned by the old machine's SID.
- **torch is CPU-only** (`torch-2.14.0+cpu`) from `download.pytorch.org/whl/cpu`. PyPI's default
  Windows wheel bundles CUDA at ~2.5 GB and failed twice on this connection; CPU-only is ~200 MB
  and is the right build anyway — nothing here uses a GPU. `requirements.txt` is unchanged (torch
  is transitive), so **the CPU index URL is a setup step that belongs in the README and in the
  report's reproducibility section**.
- Atlas: a 2026-09-13 outage was isolated layer by layer (DNS → TCP → TLS → auth) to TLS on port
  27017, which ruled the credential out. It cleared on its own; no code changed. If it recurs on
  campus, the symptom is a TLS timeout on 27017 only, and a phone hotspot is the test.

```bash
python verify_all.py --offline
```

Full command set is in `CLAUDE.md` and the README.

---

## 11. Open questions and next actions

**Blocking M4**

1. Write the **20 evaluation queries before looking at any results**, freeze fixtures, define
   relevance in writing, judge blind.
2. **Take Remotive to the supervisor** — it is the demo's weakest point and it shapes how the
   baseline can honestly be reported.
3. **Click through the app in a real browser while logged in.** The live run drove the server
   over HTTP and asserted on returned HTML — that proves routes, pipeline, real API shapes and
   template output, but **not** visual layout, Bootstrap rendering or form controls. A populated
   `/feed` for a real logged-in user with saved jobs is still unverified, as are TC-001 to TC-005
   through the rendered forms rather than the test client.

**Decisions outstanding**

- Autocomplete source: hardcoded category list, or built from `search_history`?
- The embedding model swap — needs sign-off.
- The 0.02 coefficient: tune during evaluation, or state plainly as a heuristic.
- Python version: record 3.12.10 as a deviation, or rebuild on 3.11.
- `ai_recommendations` renders as one preformatted block. If the report wants three discrete
  cards, `RAGPipeline` has to return structured data, not prose.

**Deferred, with reasons**

- The `create_app()` factory from SDD Appendix B. `app` is a module-level object that
  `verify_auth.py` imports directly; the agent reaches the blueprint through
  `app.config["AGENT"]`, so no controller imports `app` and the layering holds. Nothing depends
  on the refactor.
- The parallel fetch fork (see decision 3 above).

---

## 12. Understanding track

Graded partly on whether the design can be explained, so shipping a component is not finishing
it. See `docs/LEARNING_LOG.md` for the concept inventory and self-ratings, and
`docs/VIVA_PREP.md` for the question bank.

Target: 🟢 on all Tier 1 concepts and ⭐ on the six starred ones before submission. Weekly
self-check every Friday — three random rows, explained out loud, file closed.
