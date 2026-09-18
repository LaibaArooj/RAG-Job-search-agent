# Project Status — RAG-Based Intelligent Job Search Agent

> Read this first at the start of every session. Claude updates it at the end of each session.

Last updated: 2026-09-19 (M2 started — intent parsing built and verified)

## Deadline

Under one month to submission. The SRS assumed an 8-week timeline; the milestone plan in
`docs/PROJECT_SPEC.md` has been compressed to four weeks accordingly.

## Milestones

| # | Milestone | Status | Done when |
|---|---|---|---|
| M1 | Auth, profile, database | **Done (2026-09-19)** — TC-001 to TC-005 pass, `verify_auth.py` 31/31 | TC-001 to TC-005 pass |
| M2 | Search pipeline: LLM intent, query expansion, dedupe, semantic ranking | **In progress** — intent parsing done (TC-019, TC-020); agent and route outstanding | TC-006, TC-016 to TC-022 pass |
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

- **Currently working on:** M2 — `core/agent.py` next, then moving the search route
- **Branch:** `feat/search-pipeline`
- **Related issue:** none yet

## Where we left off

**M1 is done and M2 has started.** `core/intent_parser.py` is built and verified:
`verify_intent.py` passes 76/76, including a **live** Groq call for TC-019 and a stubbed
failure for TC-020. `verify_auth.py` (31/31) and `verify_db.py` (27/27) still pass after
the change.

The live TC-019 run on the SRS query — *"something creative I can do from home, I'm just
starting out"* — returned `work_type=remote`, `experience=entry level`, `category=design`,
three variants. TC-019's expected category is "creative", which is deliberately **not** in
`CATEGORIES`; the prompt asks for the single closest member instead, because that tuple is
shared with the M3 scoring loop and widening it there would be the wrong lever.

**Design point to be able to defend:** parsing and validation are separate steps in
`parse_intent`. The allowed values are listed in the prompt *and* re-checked for membership
on the way out. A prompt is a request; a membership test is a guarantee. Four hostile
categories are in the verify script and all collapse to `"other"`.

**`WORK_TYPES` and `EXPERIENCE_LEVELS` moved to `config.py`** from `ui_controller.py`. This
was tested, not assumed: `ui_controller` → `core.agent` → `core.intent_parser` →
`ui_controller` raises "cannot import name ... from partially initialized module". The
sharp detail worth having ready — the cycle **passed** with the import at the bottom of the
file and **failed** at the top, where PEP 8 puts it. An order-dependent cycle is worse than
one that always fails, because it survives until someone runs `isort`.

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

1. **`core/agent.py`** — `JobSearchAgent`, the next M2 component. It is what makes TC-021
   testable: `parse_intent` already returns 2–3 variants, but **nothing consumes them yet**,
   so query expansion is not actually happening in the running app.
2. Then move the search route out of `app.py` into `ui_controller.search`, which closes the
   deferral recorded in `docs/ARCHITECTURE.md`.
3. Drive TC-001 to TC-005 once in a real browser as well. `verify_auth.py` exercises the routes
   and the session cookie, not the rendered forms. Still outstanding from M1.
4. The save/reject buttons in `feed.html` post to `/save_job` and `/reject_job`, which do not
   exist as routes yet. They are unreachable today because the feed renders no jobs, but they
   must be wired in M3 or removed.
5. Watch the Adzuna quota once expansion lands. Three variants means **three** Adzuna calls per
   search against a 250/day budget, and Groq is called twice per search on top of that. This is
   the practical cost of Deviations 1 and 2 and it will bite during demo rehearsal.

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
- Python version: venv is 3.14.6, SRS says 3.11. Rebuild or record as a deviation.
- The template renders `ai_recommendations` as one preformatted block. If the report wants
  three discrete cards, `RAGPipeline` has to return structured data, not prose.
