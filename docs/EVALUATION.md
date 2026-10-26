# Evaluation Plan

> **Run and scored 2026-09-30. Result: a null.** Semantic re-ranking scored Adzuna-only
> precision@5 0.32 against the keyword baseline's 0.31. Numbers are in `evaluation/results.md`.
> The protocol as actually run, including three systems rather than two, is
> `evaluation/queries.md`; its § 7 records every ruling made during judging. This file is the
> original plan, kept as written.

The project claims that semantic ranking produces better job results than keyword ranking.
This document is how that claim gets evidence. Budget one day in M4.

Report the numbers whatever they are. A measured null result written up honestly scores
better than an unmeasured claim.

## ⚠ Read before writing the queries — what the baseline now means

Remotive ignores its `search` parameter and returns the same fixed list for every query (found
2026-09-20). Since 2026-09-20 it is **fetched then filtered locally** — see
`docs/PROJECT_STATUS.md`. That changes what the "raw API order" baseline below actually is, and
the distinction has to be stated when the numbers are reported:

- **Adzuna's** contribution to the baseline is a genuine keyword-search ranking.
- **Remotive's** is not. Its order is query-independent; only *which* of its jobs appear is
  ours, via the local title filter. So the baseline is a real keyword baseline for one source
  and a filtered constant list for the other.

The safest reading, and the one to write up: report **precision@5 over Adzuna-only** as the
headline comparison, since that is the only honest keyword-vs-semantic contrast available, and
report the two-source numbers separately with this caveat attached. Do not present a single
blended number as "keyword baseline vs semantic ranking" without saying which source is which.

One thing that improved for the evaluation: pools are no longer padded with the same ~20 jobs
on every query, so the 20 test queries are genuinely more independent than they would have been.

## What is being measured

**precision@5** — of the top 5 results, how many are relevant?

Two systems compared on the same queries:

- **Baseline:** the raw order Adzuna and Remotive return, unmodified
- **System:** the semantically re-ranked order, `similarity + category_boost`

Optionally a third: semantic ranking with the category boost switched off, which isolates how
much the personalisation heuristic actually contributes and gives you a defensible answer on
the 0.02 coefficient.

## Method

1. **Write 20 test queries** before looking at any results. Mix the styles the SRS describes:
   - Casual and vague: "something creative I can do from home"
   - Specific: "junior python developer remote"
   - Constraint-heavy: "entry level marketing no degree required"
   - Awkward phrasing the system is meant to handle: "job where I write stuff but not journalism"

2. **Freeze the data.** Run each query once, save the raw API responses as JSON fixtures in
   `evaluation/fixtures/`. Both systems then rank the *same* pool, and you avoid burning
   Adzuna's 250/day quota on re-runs.

3. **Define relevance before judging.** Write the rule down and follow it mechanically —
   e.g. *relevant = a real job a person making this query would plausibly click, matching the
   stated work type and experience level*. Ambiguity in the rule is where bias creeps in.

4. **Judge blind.** Export the top 5 from each system into one shuffled list per query with the
   source system hidden. Mark each relevant or not. Unblind afterwards.

5. **Compute.** precision@5 per query, then the mean across all 20 for each system.

6. **Report.** A table of per-query scores, the two means, and the difference. Include the
   queries where the baseline beat the system — those are the interesting ones.

## Output

A short section in the final report:

- Table: query, baseline P@5, system P@5
- Mean P@5 for each, and the delta
- 3–4 sentences on what the numbers show, including where the system underperformed and why
  you think that is

## Honest framing

This is not a rigorous IR evaluation. Say so. **Corrected 2026-10-13:** the verdicts were
not judged by the developer. They were proposed by Claude (Claude Sonnet 5.5, claude.ai) and
adopted by the developer. See `evaluation/queries.md` § 10 and `evaluation/provenance/`.

The right framing is: *a small-scale relevance assessment indicating the direction of the
effect, using AI-proposed relevance verdicts from a single model, blind to the system, with no
human validation yet, over a 20-query sample.* For the RAG stage, add that an LLM judging an
LLM's picks may be circular. Naming the weakness is what makes it credible.

## The RAG stage — pre-registered 2026-10-01

Measures whether the LLM's three picks are more relevant than the first three of the
same five candidates it is handed. The ranking is held fixed, so this isolates the LLM.

- **Protocol:** `evaluation/queries.md` § 8, committed before any pick was generated.
- **Metric:** precision@3, three frozen runs per query, with the model pinned.
- **Fixtures:** the same ones as precision@5.
- **Verdicts:** reused from the earlier sheets, plus one new blind sheet
  (`judging/SUPPLEMENT-rag.md`) for candidates no earlier sheet showed.
- **Result (scored 2026-10-11, `evaluation/rag_results.md`):**

  | | K (first three) | L (LLM picks) | Wins / ties / losses | Sign test p |
  |---|---|---|---|---|
  | Adzuna-only, the headline | 0.37 | 0.43 | 3 / 16 / 0 | 0.25 |
  | All-sources, secondary | 0.23 | 0.36 | 7 / 13 / 0 | 0.016 |

  - The LLM's picks lost to the first three on no query in either pool.
  - The headline is not significant. The secondary result is, at p = 0.016, but it is one of
    two pools.
  - eligible@3 *fell*, from 2.20 to 1.75. That is the opposite of the confound § 8.5
    predicted.
  - 9 of 117 runs (7.7%) failed and scored as K.
  - The § 8.6 sensitivity readings move no mean by more than 0.02.
  - **Measured with the pre-10-11 prompt**, which forced three picks. The prompt changed
    the same day (deviation 9). It is deliberately not re-measured on these 20 queries:
    they have been seen, so re-scoring them would be tuning to the test set.

One limitation must be stated beside the number. This was originally framed as "the LLM vs
the top three by cosine similarity". That comparison was rejected before any pick was
generated. `rag_candidates` lifts applicable jobs from lower ranks, so the comparison would
have measured that re-partition and the LLM together.

## Fresh experiment, N01–N15 — does the LLM pick better from 10 candidates than 5?

Protocol `evaluation/fresh/queries.md` (F0–F7). Pakistan profile. Status 2026-10-27: queries
pre-registered, pools frozen, picks generated by `fresh/picks_fresh.py`. **Next: the developer
judges `fresh/judging/SHEET.md` by hand, with no AI, then runs `fresh/score_fresh.py`.**

- The raw fetch (F2) left 7 of 15 pools with 0 or 1 jobs, because Himalayas matches the whole
  sentence as keywords. Amendment F7, written after seeing counts only: fetch as production
  does, with Groq's job-title expansion frozen per query (`fixtures_expanded/`, 20-49 jobs).
  The raw pools stay committed.
- Also from F7: the ranking handles exclusions, and the match percentage is absolute.
- Disclosed in F0: the developer ran all 15 queries in the live app before freezing them.
  F0's wording was drafted by Claude and filled in by the developer.

## Second judge — pre-registered 2026-10-11, scored 2026-10-27

**Result (`evaluation/agreement_results.md`):** kappa 0.26 (fair), raw agreement 0.64,
positive agreement 0.49. Judge 2 marked 28 of 58 cards relevant, judge 1 13, and 18 of the 21
disagreements are judge 2 accepting a card judge 1 rejected. Over the 6 queries, B − A on
Adzuna-only keeps its direction (+0.03 under both judges), but **L − K on all-sources goes
from +0.13 to 0.00**. So the absolute precision numbers depend on the judge, and so does the
LLM stage's small lead. Six queries cannot show significance either way. The second judge
used no AI by their own statement, which cannot be checked.

The original protocol, as pre-registered:

Both results rest on AI-proposed verdicts from a single model (§ 10). This is now **the human
validation of those verdicts**: an independent person, using no AI, judges a random sample
blind, and kappa measures how far a human agrees with the AI-proposed verdicts.

- **Protocol:** `evaluation/queries.md` § 9. The seed was committed before the draw.
- **Sample:** 6 random queries (Q16, Q12, Q20, Q11, Q09, Q01), 58 cards, each identical to
  the card judge 1 saw.
- **Measures:** Cohen's kappa, reported with raw and positive agreement. Then whether
  B − A and L − K keep their direction under judge 2's verdicts.
- **To do:** send `evaluation/second_judge/` (RULES.md and SHEET.md, nothing else) to an
  independent judge.
  - The judge must not see `queries.md`, the earlier sheets or any results.
  - Run `python evaluation/score_agreement.py` once the sheet comes back marked. It writes
    `evaluation/agreement_results.md`.
