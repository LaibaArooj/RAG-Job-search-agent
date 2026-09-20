# Project Status — RAG-Based Intelligent Job Search Agent

> Read this first at the start of every session. Claude updates it at the end of each session.

Last updated: 2026-09-20 (M2 route move **verified**, 191/191 + a live end-to-end run;
**Remotive has stopped honouring search — read the finding below**)

## 🚨 Read this first — Remotive is no longer a searchable source

Found on 2026-09-20 during the first live end-to-end run. **Remotive's API ignores the `search`
parameter completely and returns the same fixed 17-job list for every query.** Verified by
calling it with `search=nurse`, `search=accountant`, `search=qwertyuiop`, and with **no
parameters at all** — identical results every time, always led by "Senior .NET Full-stack
Developer". It ignores `limit` too: the code asks for 15 and gets 17.

Adzuna is fine and behaves correctly; it returned 0 for gibberish, as it should.

What this actually means:

- One of the project's two job sources contributes a **constant, query-independent 17 jobs to
  every search**. Search "nurse" and the candidate pool contains no nursing jobs from Remotive.
- **`MSG_NO_RESULTS` ("No jobs matched that search.") is unreachable in production** while
  Remotive is up, because the pool is never empty. TC-018's no-results branch passes in
  `verify_agent.py` against a double and cannot fire against the live API.
- **This is the biggest demo risk in the project.** A gibberish query renders 17 irrelevant
  senior-developer cards, and because `normalized_score` is relative to the best match *in that
  result set*, the top one still shows a high match percentage. "You searched nonsense and it
  says 94% match" is exactly the question that damages a viva.
- **It contaminates the M4 evaluation.** Precision@5 over 20 queries would be measured on
  candidate pools that each contain the same 17 fixed jobs. See `docs/EVALUATION.md`.

Not fixed, deliberately — the SRS names Remotive as a source and the options are design
decisions that need a call (and possibly supervisor sign-off):

1. **Drop Remotive, run on Adzuna alone.** Honest and simple; costs the "two sources" claim and
   the genuinely-global remote listings, and puts the whole demo on a 250/day quota.
2. **Keep Remotive but filter it locally** — fetch its list once and keyword-filter client side.
   Preserves two sources, but it is no longer an API search and the write-up must say so.
3. **Add a minimum-similarity floor** so irrelevant jobs are dropped rather than ranked. This
   fixes the demo risk for *both* sources but is a new ranking parameter that has to be
   justified and tuned during evaluation — it cannot be a hand-picked number like the existing
   `CATEGORY_BOOST`.

Whichever is chosen, the SRS claim of two live searchable sources needs a line in the report.

## Deadline

Under one month to submission. The SRS assumed an 8-week timeline; the milestone plan in
`docs/PROJECT_SPEC.md` has been compressed to four weeks accordingly.

## Milestones

| # | Milestone | Status | Done when |
|---|---|---|---|
| M1 | Auth, profile, database | **Done (2026-09-19)** — TC-001 to TC-005 pass, `verify_auth.py` 31/31 | TC-001 to TC-005 pass |
| M2 | Search pipeline: LLM intent, query expansion, dedupe, semantic ranking | **Done (2026-09-20)** — intent parsing, `JobSearchAgent` and the route move all built and verified. 191/191 across the four verify scripts, plus a live end-to-end run through the browser stack | TC-006, TC-016 to TC-022 pass |
| M3 | RAG, save/reject learning, For You feed | Not started | TC-008 to TC-014 pass |
| M4 | **Evaluation (precision@5)**, filters, autocomplete, full test pass, demo | Not started | Demo runs end to end + P@5 measured |

## Completed

- SRS v1.0 and SDD v1.0 written and submitted
- Adzuna API key obtained and stored in `.env`
- Remotive confirmed (no key required)
- Groq API key obtained and stored in `.env`
- PSB project scaffold in place
- **Module layout restructured to SDD Appendix B (2026-09-13)** — `controllers/`, `core/`,
  `adapters/`, `models/` created, working modules moved in with `git mv`, every remaining
  Appendix B file present as a stub. Demo verified unchanged after the move: 24 deduplicated
  jobs on the baseline query. `models.py` deleted (name collision with the `models/` package).

## In progress

- **Currently working on:** M2 is closed. Next decision is the Remotive finding above, then M3.
- **Branch:** `feat/search-pipeline`
- **Related issue:** none yet

## Environment — rebuilt 2026-09-20

The project was copied from another machine (user `BEST BUY COMPUTERS`, drive `L:`) and arrived
with a dead venv and no interpreter. Now working:

- **Python 3.12.10** at `C:\Users\laiba\AppData\Local\Programs\Python\Python312`, venv rebuilt.
  Note this is **neither** the SRS's 3.11 nor the old 3.14.6 — still a deviation to record.
- `python` on PATH is only the Microsoft Store stub; an App Execution Alias shadows the real
  one. Use `venv\Scripts\python.exe` explicitly.
- **`git` is not on PATH** — it lives at `C:\Program Files\Git\cmd\git.exe`. The repo also
  needed `git config --global --add safe.directory E:/RAG-Job-search-agent`, because the working
  tree is still owned by the old machine's SID.
- **torch is installed CPU-only** (`torch-2.14.0+cpu`) from `download.pytorch.org/whl/cpu`.
  PyPI's default Windows wheel bundles CUDA and is ~2.5 GB, which failed twice on this
  connection. CPU-only is ~200 MB and is the right build regardless: `all-MiniLM-L6-v2` runs on
  CPU here and no part of the project uses a GPU. `requirements.txt` is unchanged, since torch
  is a transitive dependency of sentence-transformers and was never pinned — but the CPU index
  URL is a setup step that belongs in the README and in the report's reproducibility section.

## Where we left off — 2026-09-20

**The app now runs the agent, and it is verified.** `ui_controller.search` serves `/`, calls
`JobSearchAgent.run(username, query)` and renders the dict. `app.py` is wiring only. The legacy
`fetch_all_jobs` / `fetch_adzuna_jobs` / `fetch_remotive_jobs` trio is deleted, so there is one
fetch path. This closes the inline-route deferral in `docs/ARCHITECTURE.md`.

Until this commit, TC-021 (query expansion) and TC-018 (the partial-source banner) passed in
`verify_agent.py` and **did not happen in the running app**. The tests and the demo now agree.

**Verified two ways.** All four verify scripts: `verify_db.py` 27, `verify_auth.py` 31,
`verify_intent.py` 76 (live Groq call), `verify_agent.py` 57 — **191/191**. Then a live run
against the running server with real Adzuna, Remotive, Groq and Atlas: a real search rendered
32 ranked cards with match badges and a populated AI Recommendations panel, `GET /` opened with
no error banner, an empty submit produced TC-017's message and no job cards, and no raw Python
dict leaked into the page.

**Query expansion is provably live, not just wired.** After the run, `job_cache` held multiple
documents per search, keyed per *variant*. That is the evidence to show in the viva: one search,
several cache entries, one per LLM-generated phrasing.

The live run is also what surfaced the Remotive finding at the top of this file. That is the
value of it — `verify_agent.py` is offline by design and could never have found it.

**Four things to be able to defend:**

1. **`GET /` deliberately does not call `agent.run()`.** With an empty query the agent returns
   TC-017's "Please enter a search term", so calling it on arrival would greet every visitor
   with an error banner. TC-017 is about an empty *submit*.
2. **The route stayed on `/` instead of moving to `/search`.** `verify_auth.py` measures TC-003
   and TC-005 on that URL — 200 logged in, 302 anonymous. A `/search` route with `/` redirecting
   would turn those 200s into 302s and break a green M1 suite to satisfy a URL preference.
3. **Renaming the endpoint to `ui.search` moved six `url_for("home")` call sites** — four in
   `auth_controller.py`, plus the nav bars in `feed.html` and `profile.html`. A missed one is a
   `BuildError`, which reaches the user as a 500 on a page that works today. This is the cost
   of endpoint renames and it is worth being able to state.
4. **`error` and `warning` are template variables, not flashed messages.** `flash()` carries a
   message across a redirect; this renders in the same request. It also avoids a real bug — the
   flash block maps any category that is not `error` to `alert-success`, so a flashed warning
   would have rendered green.

**Still deferred:** the `create_app()` factory from SDD Appendix B. `app` is a module-level
object that `verify_auth.py` imports directly. The agent reaches the blueprint through
`app.config["AGENT"]`, so no controller imports `app` and the layering holds; the factory is a
refactor with nothing in M2 depending on it.

## Where we left off — 2026-09-19

**The M2 pipeline is assembled.** `core/agent.py` (`JobSearchAgent`) and `models/job_card.py`
are built and `verify_agent.py` passes **57/57** — entirely offline, no live Groq, no Adzuna
quota, no Atlas. `verify_intent.py` (76), `verify_auth.py` (31) and `verify_db.py` (27) all
still pass: **191 checks green**.

TC-006, TC-016, TC-017, TC-018, TC-021 and TC-022 are now covered. TC-021 in particular was
untestable before this: `parse_intent` had been returning query variants since the previous
session and **nothing consumed them**, so query expansion was not actually happening in the
running app. It is now.

**The search route in `app.py` is untouched and still serves.** That was deliberate — the
agent was built and proven beside the working route rather than in place of it, so there was
never a point where the app was broken. Swapping the route over is the next task and is the
only build work left in M2. *(Superseded 2026-09-20: the route was moved into
`ui_controller.search` and the inline one deleted. See the 2026-09-20 section above.)*

**Four design points to be able to defend:**

1. **`JobSearchAgent.__init__` takes `db`, `semantic_engine` and `rag_pipeline` as arguments.**
   That single choice is why `verify_agent.py` runs offline in about a second. The sharp
   follow-up to have ready: *which assertions could not be written without doubles?* The TC-017
   ones — proving a call did **not** happen needs a call counter, not a return value.
2. **Dedupe keeps the FIRST occurrence, not the last.** `parse_intent` guarantees the user's own
   phrasing is `variants[0]`, so expansion can only ever widen the pool and can never reorder
   what the user would have seen without it. Last-wins would have inverted what TC-021 measures.
3. **A rate-limited source and an empty result set are different events.** Every existing fetch
   function returned `[]` for both, so TC-018's banner was unimplementable until
   `fetch_variant` started reporting `failed_sources` separately from what it returned.
4. **The parallel fork in the SDD is not built.** Fetching is sequential: three variants across
   two APIs is six sequential HTTP calls and the demo is correspondingly slow. Recorded as a
   deferral in `docs/ARCHITECTURE.md` § Search request flow with the trade written down — a
   threading bug that intermittently drops one variant's results is harder to notice and harder
   to defend than a slow search. Do not claim the fork works in the viva.

**The Adzuna quota risk is now mitigated, not eliminated.** The 60-minute `job_cache` was dead
code and is now wired in, keyed on a SHA-256 of the **variant** string rather than the user's
query, so overlapping searches share a fetch. A partial fetch is never cached. A *cold* search
still costs up to three Adzuna calls, so watch it during demo rehearsal.

---

**M1 is done.** As of 2026-09-19 a user can register, log in, edit their profile, log out and
log back in against live Atlas. `verify_auth.py` passes 31/31 including TC-001 to TC-005, and
`verify_db.py` still passes 27/27.

The Atlas blocker cleared on its own. The 2026-09-13 diagnosis stands as the method — DNS, TCP,
TLS and auth were probed layer by layer and the fault isolated to TLS on port 27017, which ruled
the credential out — and the network path to that port now works. Nothing in the code was
changed to fix it. **Worth being ready to say in the viva:** if it breaks again on campus, the
symptom is a TLS timeout on 27017 only, and a phone hotspot is the test.

Routes now live in blueprints: `controllers/auth_controller.py` (`auth`) and
`controllers/ui_controller.py` (`ui`). The search route is still inline in `app.py` — moving it
is M2 work, recorded as a deliberate deferral in `docs/ARCHITECTURE.md`.

**Four defects in the old `5519a22` auth code were found and not repeated.** All four are good
viva material because each has a one-sentence reason:

1. It rendered `templates/login.html`, **a file that had never existed**. TC-003 and TC-004 would
   both have 500'd. Written now.
2. `os.getenv("SECRET_KEY", "fallback_secret_key")` — a known signing key means anyone can forge
   a session cookie for any username. A missing key is now fatal at startup.
3. It read `SECRET_KEY`; `config.py` defines `FLASK_SECRET_KEY`. The former was never set
   anywhere, so the fallback was always the one in use.
4. It passed the **plain password** to `create_user`. Hashing is the controller's job now.

Two things carried in with it: `index.html` credited "Gemini AI" for the recommendations (it is
Groq), and the search route had dropped the profile enrichment that TC-016 depends on. Both fixed.

CSRF is hand-rolled — a per-session random token, injected into every form by a Jinja context
processor, compared with `hmac.compare_digest`. Chosen over Flask-WTF to avoid a dependency and
because the mechanism has to be explainable in the viva.

Also still open: the venv is **Python 3.14.6**, but the SRS and `CLAUDE.md` specify 3.11. Either
rebuild the venv on 3.11 or record the version as a deviation — an examiner may ask.

## Next up

1. **Decide what to do about Remotive** — see the finding at the top. This blocks honest M4
   evaluation and it is the demo's weakest point. Take it to the supervisor.
2. **Click through the app yourself in a real browser.** The 2026-09-20 live run drove the
   running server over HTTP and asserted on the returned HTML, which proves the routes, the
   pipeline, the real API shapes and the template output — but **not** the visual layout, the
   Bootstrap rendering or the form controls. That is demo rehearsal and it is still outstanding,
   along with TC-001 to TC-005 through the rendered forms rather than the test client.
5. The save/reject buttons in `feed.html` post to `/save_job` and `/reject_job`, which do not
   exist as routes yet. They are unreachable today because the feed renders no jobs, but they
   must be wired in M3 or removed.
6. `JobCard.category` is left as `""` deliberately — deriving it from the two taxonomies is the
   open question below, and guessing would poison the M3 scoring loop. The category boost in
   `rank()` is therefore **inert until that is settled**: every job scores 0 on it today. The
   verify script proves the mechanism works by passing categories in directly. Say this plainly
   if asked; do not demo it as if it were live.

Then, when M4 arrives: write the 20 evaluation queries **before** looking at any results.

## Design changes agreed since the SRS

Three deviations from SRS v1.0, all documented in `docs/PROJECT_SPEC.md` § Deviations, all
needing a line in the final report:

1. `parse_intent` now calls Groq for structured intent + query variants, with keyword matching
   as the fallback. The SRS defines an Agent as autonomous; if-statements aren't.
2. Query expansion — 2–3 variants per search, results unioned and deduped. Softens the recall
   ceiling that is the project's main weakness.
3. Evaluation added — precision@5 over 20 queries, semantic vs raw API order. See
   `docs/EVALUATION.md`. Highest-value single day of work in the project.

Still undecided: whether to swap `all-MiniLM-L6-v2` for `msmarco-MiniLM-L6-v3`, which is
trained for short-query-to-long-document matching rather than sentence-to-sentence. One-string
change, but it deviates from the model named in the SRS, so it needs supervisor sign-off.

## Understanding track

Separate from the build. See `docs/LEARNING_LOG.md` for the concept inventory and current
self-ratings, and `docs/VIVA_PREP.md` for the question bank.

Target: 🟢 on all Tier 1 concepts, ⭐ on the six starred ones, before submission.
Weekly self-check every Friday — three random rows, explained out loud, file closed.

| Week | Concepts moved to 🟢+ | Still weak |
|---|---|---|
| 1 | | |
| 2 | | |
| 3 | | |
| 4 | | |

## Blockers / open questions

- How is a job's `category` derived? Adzuna and Remotive use different taxonomies and the
  whole save/reject scoring loop depends on a single consistent category per job.
  **Must be decided before M3.**
- Does the For You feed hit the live APIs on every visit? At 250 Adzuna requests/day that
  quota disappears fast during testing.
- Autocomplete source: hardcoded category list, or built from `search_history`?
- Ask the supervisor about the embedding model swap (see design changes above).
- The 0.02 category-boost coefficient is a hand-picked number with no justification.
  Either tune it during evaluation or state it plainly as a heuristic.
- **Tell the supervisor Groq retired Llama 3.** The SRS names it; the model is gone. The
  substitution is recorded in `docs/PROJECT_SPEC.md` § Deviations and needs sign-off.
- Python version: the venv was built on 3.14.6, SRS says 3.11. This is no longer just a
  paperwork question — the venv is unusable and has to be rebuilt anyway, so rebuilding on 3.11
  closes the deviation at no extra cost beyond the download. See the note at the top.
- The template renders `ai_recommendations` as one preformatted block. If the report wants
  three discrete cards, `RAGPipeline` has to return structured data, not prose.
