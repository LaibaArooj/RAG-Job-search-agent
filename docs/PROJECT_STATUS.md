# Project Status — RAG-Based Intelligent Job Search Agent

> Read this first at the start of every session. Claude updates it at the end of each session.

Last updated: 2026-09-11

## Deadline

Under one month to submission. The SRS assumed an 8-week timeline; the milestone plan in
`docs/PROJECT_SPEC.md` has been compressed to four weeks accordingly.

## Milestones

| # | Milestone | Status | Done when |
|---|---|---|---|
| M1 | Auth, profile, database | **In progress** | TC-001 to TC-005 pass |
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

- **Currently working on:** M1 — MongoDB Atlas setup
- **Branch:** none yet
- **Related issue:** none yet

## Where we left off

Attempting to set up the database and got stuck. Clarified: MongoDB Atlas stores **user profiles
only** — no vectors, no job listings. The design uses live retrieval with in-memory embeddings,
so no vector database is required. What's needed is one free-tier Atlas cluster, one `users`
collection, and a unique index on `username`.

Everything built so far has been assembled by following AI instructions step by step rather than
from a working understanding of the design. Going forward, each component should be explained
as it is built, since the design must be defended in a viva.

## Next up

1. Create the MongoDB Atlas free cluster; add `MONGODB_URI` to `.env`
2. Create the unique index on `users.username`
3. Build `config.py` and `adapters/db_manager.py` (the only PyMongo consumer)
4. Build `controllers/auth_controller.py` — register, login, logout, require_auth
5. Build the base Jinja template, navbar, login and profile-setup pages
6. Verify TC-001 to TC-005 by hand

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
