# Evaluation Plan

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

Twenty queries judged by the developer is not a rigorous IR evaluation. Say so. The right
framing is: *a small-scale relevance assessment indicating the direction of the effect, limited
by a single non-blind-to-the-project judge and a 20-query sample.* Naming the weakness is what
makes it credible.

## Optional extension if time allows

Measure the RAG stage: are the LLM's three picks more relevant than the top three by cosine
similarity alone? Same protocol, same fixtures. Currently untested, and an examiner may ask.
