# Project Status — RAG-Based Intelligent Job Search Agent

> Read this first at the start of every session. Claude updates it at the end of each session.

Last updated: 2026-09-13

## Deadline

Under one month to submission. The SRS assumed an 8-week timeline; the milestone plan in
`docs/PROJECT_SPEC.md` has been compressed to four weeks accordingly.

## Milestones

| # | Milestone | Status | Done when |
|---|---|---|---|
| M1 | Auth, profile, database | **Blocked** — Atlas credential | TC-001 to TC-005 pass |
| M2 | Search pipeline: LLM intent, query expansion, dedupe, semantic ranking | Not started | TC-006, TC-016 to TC-022 pass |
| M3 | RAG, save/reject learning, For You feed | Not started | TC-008 to TC-014 pass |
| M4 | **Evaluation (precision@5)**, filters, autocomplete, full test pass, demo | Not started | Demo runs end to end + P@5 measured |

## Completed

- SRS v1.0 and SDD v1.0 written and submitted
- Adzuna API key obtained and stored in `.env`
- Remotive confirmed (no key required)
- Groq API key obtained and stored in `.env`
- PSB project scaffold in place

## In progress

- **Currently working on:** M1 — blocked on the Atlas database user credential
- **Branch:** `feat/auth`
- **Related issue:** none yet

## Where we left off

**The search demo now runs end to end without a database.** Verified 2026-09-13: a query for
"remote python developer" returns 24 deduplicated jobs from Adzuna *and* Remotive, ranks them
semantically, and Groq returns three explained picks. FR-018 verified by pointing the client at
a non-existent model: the error is caught, the AI panel hides, ranked results still render.

`app.py` was deliberately kept in its simplified form — no auth, no session, no MongoDB. The
full version with `/register`, `/login`, `/logout`, `/save_job`, `/reject_job`, `/feed` and
`/profile` is preserved in commit `5519a22` and is the starting point when M1 resumes.

**Two blockers found while debugging Atlas, one fixed:**

1. *Fixed.* The username in `MONGO_URI` contained a Cyrillic `а` (U+0430) instead of Latin `a`.
   It is visually identical in every editor, and Atlas answered `bad auth`. Worth remembering:
   an Atlas error response rather than a timeout proves the cluster, DNS, TLS and IP allowlist
   are all fine, and isolates the fault to the credential.
2. *Outstanding.* Auth still fails after that fix. The database user's password must be reset
   from the Atlas UI (Database Access → Edit → Autogenerate Secure Password) and pasted into
   `.env`. Claude does not handle database credentials.

Also noted: the venv is **Python 3.14.6**, but the SRS and `CLAUDE.md` specify 3.11. Either
rebuild the venv on 3.11 or record the version as a deviation — an examiner may ask, and
`datetime.utcnow()` (used in the old `models.py`) is deprecated from 3.12 onward.

## Next up

1. **Reset the Atlas database user password** and confirm with a ping — everything else is blocked on this
2. Decide `MONGO_URI` vs `MONGODB_URI` and use one name in code, `.env` and the docs
3. Build `config.py` and `adapters/db_manager.py` (the only PyMongo consumer), replacing
   `models.py` — it has a NoSQL field-path injection in `update_category_score`, connects at
   import with no try/except, and reports "Username already taken" for any exception
4. Restore the auth routes from `5519a22` on top of that
5. Verify TC-001 to TC-005 by hand

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
