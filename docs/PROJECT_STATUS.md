# Project Status — RAG-Based Intelligent Job Search Agent

> Read this first at the start of every session. Claude updates it at the end of each session.

Last updated: 2026-09-19 (M1 complete — auth, session and profile)

## Deadline

Under one month to submission. The SRS assumed an 8-week timeline; the milestone plan in
`docs/PROJECT_SPEC.md` has been compressed to four weeks accordingly.

## Milestones

| # | Milestone | Status | Done when |
|---|---|---|---|
| M1 | Auth, profile, database | **Done (2026-09-19)** — TC-001 to TC-005 pass, `verify_auth.py` 31/31 | TC-001 to TC-005 pass |
| M2 | Search pipeline: LLM intent, query expansion, dedupe, semantic ranking | **Next** | TC-006, TC-016 to TC-022 pass |
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

- **Currently working on:** M2 — search pipeline (intent parsing, query expansion, ranking)
- **Branch:** `feat/auth` (M1 work; branch `feat/search-pipeline` for M2)
- **Related issue:** none yet

## Where we left off

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

1. **Add `FLASK_SECRET_KEY` to your live `.env`.** It is missing, and the app now refuses to
   start without it. Claude does not edit `.env`. Generate one with:
   `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   (`verify_auth.py` supplies a throwaway key to its own process, which is why it runs today.)
2. Drive TC-001 to TC-005 once in a real browser as well. `verify_auth.py` exercises the routes
   and the session cookie, not the rendered forms.
3. Start M2 on a `feat/search-pipeline` branch: `core/intent_parser.py`, then `core/agent.py`,
   then move the search route out of `app.py` into `ui_controller.search`.
4. The save/reject buttons in `feed.html` post to `/save_job` and `/reject_job`, which do not
   exist as routes yet. They are unreachable today because the feed renders no jobs, but they
   must be wired in M3 or removed.

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
