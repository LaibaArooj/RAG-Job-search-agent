# Evaluation Plan

The project claims that semantic ranking produces better job results than keyword ranking.
This document is how that claim gets evidence. Budget one day in M4.

Report the numbers whatever they are. A measured null result written up honestly scores
better than an unmeasured claim.

## ⚠ Read before writing the queries — the baseline is compromised

Found 2026-09-20: **Remotive ignores the `search` parameter and returns the same fixed 17-job
list for every query.** See the finding at the top of `docs/PROJECT_STATUS.md`. This hits the
evaluation harder than it hits the app:

- The **baseline** below is "the raw order Adzuna and Remotive return". For Remotive that order
  is now query-independent, so the baseline is partly a constant list. Comparing against it
  flatters the system for the wrong reason — re-ranking a fixed list will beat it on nearly any
  query, and that says nothing about semantic vs keyword ranking.
- Every candidate pool contains the same 17 jobs, so the 20 queries are far less independent
  than they look.

**Decide the Remotive question before running the evaluation, not after.** Whatever is decided,
the honest options for this document are to measure Adzuna-only (a real keyword baseline), or to
report Adzuna-only and both-sources separately and explain the difference. Measuring the
polluted pool and reporting one number would be the indefensible choice.

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
