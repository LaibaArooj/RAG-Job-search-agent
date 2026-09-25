Last updated: 2026-09-23 (**M4 in progress.** Four defects found by using the app as a real
user are fixed; Jobicy added as a third source and per-user source selection shipped, so a
user in Pakistan now sees 31 applicable jobs where they saw 6. **400/400 offline checks
green** across five scripts. Deadline revised: at least two more months, not one.)

## Where we left off — 2026-09-23 (first real browser session)

**The first click-through of the app as a logged-in user found five problems, four of which
were real defects.** That is the headline for the report: the 320 green assertions could not
see any of them, because every one lived in the gap between "the code does what the test
says" and "the product does what a user needs".

| # | Symptom | Verdict | Status |
|---|---|---|---|
| 1 | "My user isn't in MongoDB" | Not a bug — login only reads; was looking at the wrong DB name | Closed |
| 2 | AI picks have no Save/Reject buttons | Design gap — `RAGPipeline` returned prose | Fixed 2026-09-25 |
| 3 | Feed ≠ saved jobs | Working as designed, plus two design gaps | **Open** |
| 4 | Searched software, got a `design` score | **Bug** — `"ui"` matched inside "suited" | Fixed 2026-09-22 |
| 5 | Profile "View" reloads the page | **Bug** — template read `job.url`, DB stores `source_url` | Fixed 2026-09-22 |

Then two more, found while fixing those:

- **Groq had silently killed the AI panel.** `groq/compound-mini` was returning 404 and had
  been since ~2026-09-21. Now `openai/gpt-oss-120b`. See the CHANGELOG for the reasoning-token
  trap this introduced — it is the best "why tests pass while the product is broken" story in
  the project.
- **Every job shown was one the user could not apply for.** Adzuna is UK-only and has no
  concept of hiring a remote candidate from abroad; Remotive is capped at 18. Jobicy added.

### The three test users were deleted by the user on 2026-09-23

Their `category_scores` were corrupt from the old classifier and no migration was written.
**The database is now empty — you must register a fresh account before demoing**, and the
feed and profile will be empty until you save a few jobs.

### Read this before touching the evaluation

`docs/EVALUATION.md` assumes Adzuna is the only genuine keyword search and therefore the whole
baseline. That is still true, but Adzuna's results are now a minority of what the user sees
and are badged as inapplicable for a non-UK seeker. **Decide what the baseline means before
writing the 20 queries**, not after.

### Next actions

1. **Write the 20 precision@5 queries** — before looking at any results. Settle the Adzuna
   baseline question first.
2. **Tell the supervisor**: the second forced model substitution, Jobicy as a new source, and
   per-user source selection (which adds a `country` field to the user document). All recorded
   in `docs/PROJECT_SPEC.md` § Deviations, which now lists **eight**.
3. **Run `verify_live.py`** — nothing has exercised Jobicy under the live suite. ~12 Adzuna calls.
4. Items 2 and 3 from the table above are still open and still unscoped.

---

## Where we left off — 2026-09-21 (M3 complete)

Last updated: 2026-09-21 (**M3 done** — the For You feed is built, so categorisation, the
save/reject loop and the feed are all shipped. 320/320 offline checks green across five
scripts.)

## Remotive — resolved 2026-09-20, and it must be stated in the report

Remotive's API ignores `search` and `limit` entirely and returns the same fixed ~20-job list for
every request, verified with no parameters at all. It is now **fetched once and filtered locally**
in `adapters/api_client.py`:

- a job is kept only if a meaningful word from the query appears in its **title** (word match
  tolerating an inflected ending, so "engineer" matches "Engineering" but "car" does not match
  "Cardiac");
- and, when `parse_intent` found a level in the query, jobs whose title contradicts it are
  dropped — an entry-level search never keeps a "Senior …" title, and vice versa.

**Say this plainly in the write-up and in the viva: Remotive is fetched then filtered locally. It
is no longer an API keyword search.** That is the honest cost of keeping a second source, and it
is a smaller cost than a source that returns the same 20 jobs for "nurse" and "qwertyuiop".

Adzuna is untouched by the level filter on purpose: it ran a real keyword search, so its results
are earned and overruling them would be second-guessing a genuine match.

What this bought, measured:

- `MSG_NO_RESULTS` ("No jobs matched that search.") is **reachable again**. It had been dead code
  in production since Remotive broke, because the pool was never empty. A gibberish query now
  renders zero cards and the message, where it previously rendered 17 senior jobs.
- An entry-level query keeps **0 of the 11 senior-titled** jobs in the live feed.

## Deadline

**Revised 2026-09-23: at least two more months available**, not the one month this file
previously recorded. The four-week compression of the milestone plan in
`docs/PROJECT_SPEC.md` was made under the old assumption and no longer binds. Work that was
cut for time — the AI picks as real job cards, TC-007 autocomplete, TC-015 filters, TC-009's
missing assertion, the msmarco embedding-model comparison and tuning CATEGORY_BOOST — is all
back on the table.

## Milestones

| # | Milestone | Status | Done when |
|---|---|---|---|
| M1 | Auth, profile, database | **Done (2026-09-19)** — TC-001 to TC-005 pass, `verify_auth.py` 31/31 | TC-001 to TC-005 pass |
| M2 | Search pipeline: LLM intent, query expansion, dedupe, semantic ranking | **Done (2026-09-20)** — intent parsing, `JobSearchAgent` and the route move all built and verified. 221/221 across the four verify scripts, plus a live end-to-end run against the running server | TC-006, TC-016 to TC-022 pass |
| M3 | RAG, save/reject learning, For You feed | **Done (2026-09-21)** — RAG panel shipped in M2; categorisation, save/reject and the For You feed all built. `verify_agent.py` 129/129, `verify_routes.py` 57/57 | TC-008 to TC-014 pass |
| M4 | **Evaluation (precision@5)**, filters, autocomplete, full test pass, demo | **In progress** — first browser session done, four defects fixed, geographic eligibility and per-user source selection shipped. The 20 queries are pre-registered in `evaluation/queries.md`; fixtures NOT yet generated. `verify_all.py --offline` 362/362 | Demo runs end to end + P@5 measured |

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

- **Currently working on:** M4. The 2026-09-23 browser session took priority over the
  evaluation: four defects and two silent failures were found and fixed, and geographic
  eligibility shipped. The precision@5 evaluation is STILL NOT STARTED and is now the
  critical path — write the 20 queries BEFORE looking at any results, and settle the Adzuna
  baseline question first (see the 2026-09-23 note at the top).
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

## Where we left off — 2026-09-21 (feed)

**M3 is done.** The For You feed is built and `/feed` no longer renders a placeholder. A user
with saved jobs now gets a feed assembled from their own highest-scoring categories, with a
match badge per card and working Save/Reject buttons. `verify_agent.py` went 97 → **129**,
`verify_routes.py` 46 → **57**. **320 offline checks green.**

**Two open questions are now closed.**

1. **Does the feed hit the live APIs on every visit?** Yes — and the quota fear it was based on
   does not survive inspection. The fetch variant is a **category name**, and `CATEGORIES` is a
   closed set of 13 strings, so every user and every visit shares the same 60-minute cache keys.
   All feed traffic in the whole app costs at most ~13 Adzuna calls per hour against 250/day.
   A user with no positive scores returns before any fetch at all. Have that number ready.
2. **What does a preference-less user see?** The empty state, not a profile-based fallback. A
   fallback would keep the feed populated but would give "why do two users see different feeds?"
   two possible answers instead of one, which is the exact ambiguity TC-014 exists to rule out.

**The one design point that is genuinely load-bearing:** jobs outside the user's top categories
are **dropped**, not ranked lower. TC-012 says rejected categories are *absent*, and "ranked
last of twelve on one page" is still present. A keyword fetch for `writing` routinely returns
jobs that classify as `technology` — without `_filter_feed`, a user with `technology = -2` still
sees tech jobs on a feed that otherwise looks entirely correct. This is the kind of defect a
screenshot would never show.

**Three more to be able to defend:**

1. **`classify(jobs, None)` in the feed, not `classify(jobs, intent_category)`.** In a search, a
   job whose text names no category borrows the one the user searched for. The feed has no
   single query, so there is nothing to borrow — such a job lands in `"other"` and the filter
   then drops it. A job earns its place in the feed by its own text.
2. **No Groq call on the feed.** It is a browse surface, not a question; a second LLM call per
   page load would explain a query the user never typed. Deliberate omission, and FR-016's AI
   Recommendations are specified against a search.
3. **A context-read failure is fatal to the feed, unlike in `run()`.** The search degrades to
   unpersonalised because it still has a query; the feed has nothing else — the scores *are*
   the input. Returning an unpersonalised feed would be a different feature wearing this
   one's name.

**TC-014 is asserted as disjointness, not difference.** Two users with opposite scores must
share *no* job at all. Asserting only that the two lists differ would pass on a one-job overlap,
which is not "completely different feeds".

**Still hand-picked, TODO(M4):** `FEED_CATEGORIES = 3`, `FEED_LIMIT = 12` and the 85 / 65
match-band thresholds, on the same footing as `CATEGORY_BOOST`. Note that `normalized_score` is
relative to the best match in the feed, so **the top card is a "Top Match" by construction** —
say that before an examiner finds it.

**What was verified, and what was not.** 320 offline assertions, including the feed's TC-012 and
TC-014 cases against doubles and `/feed` driven over HTTP for the empty state. **Not** verified:
a populated `/feed` in a real browser with a real logged-in user who has saved jobs. That is the
same outstanding demo-rehearsal item as before and it now covers one more page.

## Where we left off — 2026-09-21

**The preference loop runs end to end.** A user can click Save or Reject on a job card, the
score moves in Atlas, and the button flips without reloading the page. `verify_routes.py` is new
and passes 46/46; `verify_agent.py` went from 57 to 97. **277 offline checks green.**

**The category question is settled** — it was the item both this file and `config.py` flagged as
*must be decided before M3*. Neither API taxonomy is mapped. Every job is classified locally from
its **own** title and description against `config.CATEGORY_HINTS`, by
`core.intent_parser.classify_category`, which is the same table and matcher the `parse_intent`
keyword fallback runs on a query. One rule for both sources.

**Say this plainly in the report and the viva: categories are assigned by substring keyword
matching over job text.** First matching key wins, so the ORDER of `CATEGORY_HINTS` is the
tie-break rule. A job whose title and opening paragraph name no category word falls back to the
parsed intent's category, then to `"other"`. It is not classification by meaning. It is recorded
as limitation 9 in `docs/PROJECT_SPEC.md`.

**Two things that were broken and are not any more:**

1. **The category boost was dead code in production.** `JobCard.category` was `""` on every job,
   so `similarity + (category_score × 0.02)` contributed exactly 0 to every listing — while
   `verify_agent.py` passed, because that test supplied categories directly. This is the same
   shape of gap as the TC-021 one found on 2026-09-20: a test that provides its own inputs
   cannot tell you the production path ever produces them. `verify_agent.py` now asserts the
   reorder through the full `run()`.
2. **`feed.html` posted `category="{{ job.source | lower }}"`** — i.e. `adzuna`, which is not in
   `CATEGORIES`. Every click would have raised `ValueError` out of `_score_path` and reached the
   user as a 500. It was unreachable only because the feed renders no jobs yet. Worth having
   ready as an example of a latent defect found by wiring the thing up rather than by testing.

**Four design points to be able to defend:**

1. **Classification happens in the agent, not in `JobCard.from_adzuna` / `from_remotive`.**
   `JobCard` normalises the *shape* two APIs disagree about and holds no policy. Which category
   a job belongs to is policy — it decides what save/reject increments and what the boost reads.
   Doing it in the agent also covers jobs read back out of the 60-minute cache, so there is
   exactly one place a category is ever assigned.
2. **The job's own text beats the query's category.** The parsed intent is only the fallback for
   a job that matches nothing. TC-011 is the reason: rejecting a *tech* job must lower the
   *tech* score, and if the query's category won, a tech job found during a writing search would
   move the writing score instead.
3. **The routes answer with JSON, not a redirect.** The ranked list only exists in the response
   that rendered it — nothing persists it — so a POST-redirect-GET would either lose the results
   the user is looking at or re-run the entire pipeline, a second Groq call included, on every
   click. The `fetch` body is form-encoded rather than JSON specifically so the existing
   `check_csrf()` keeps working: it reads `request.form`, which a JSON body leaves empty.
4. **A bad category is a 400, not a 500.** `_score_path` already raises `ValueError` because the
   category reaches a MongoDB field path, but an unhandled `ValueError` reaches the user as a
   server error. The route check is what makes the status code tell the truth. Both checks stay.

**`already: true` is a success, not an error.** A second save matches no document, so nothing is
pushed and nothing is incremented (TC-013, enforced by the filter, not by a prior read). The
route reports it and the button settles the same way, so a double-click looks like one click.

**What was verified, and what was not.** 277 assertions across the five offline scripts, plus the
button behaviour driven in a real browser against the running server with `fetch` stubbed: a
success flips the label to "Saved", disables both buttons and posts the right form-encoded body;
a 400 re-enables them and shows the server's own message; no console errors. **Not** verified: a
real click-through while logged in, which is still the outstanding demo-rehearsal item below.

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
5. ~~The save/reject buttons post to routes that do not exist.~~ **Done 2026-09-21** — both
   routes exist, both templates share one markup block, and the category they post is the one
   the agent assigned, not the source name.
6. ~~`JobCard.category` is `""`, so the category boost is inert.~~ **Done 2026-09-21** — every
   job now leaves `run()` with a category and the boost is live. The 0.02 coefficient itself is
   still a hand-picked number with no justification; that remains open below and is TODO(M4).

7. ~~Build the For You feed (TC-012, TC-014).~~ **Done 2026-09-21** — `build_feed` is the
   agent's second entry point, `/feed` renders it, and both test cases are asserted offline.

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

- ~~How is a job's `category` derived?~~ **Settled 2026-09-21** — classified locally from the
  job's own text against `config.CATEGORY_HINTS`, neither API taxonomy used. See the 2026-09-21
  section above and limitation 9 in `docs/PROJECT_SPEC.md`.
- ~~Does the For You feed hit the live APIs on every visit?~~ **Settled 2026-09-21** — yes,
  through the existing 60-minute cache keyed on the category NAME. A closed set of 13 category
  strings means all feed traffic costs at most ~13 Adzuna calls per hour, and a user with no
  positive scores costs none.
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
