# Fresh-query experiment — does the LLM pick better from 10 candidates than from 5?

**Pre-registered. The 15 queries below are written, and this file committed, before any pool
is fetched.** Nothing below may be edited once `fresh/fixtures/` exists. A badly worded query
is reported as a limitation, never replaced.

Why fresh queries: the 20 queries in `evaluation/queries.md` have been fetched, judged and
scored, and their results have been read. A design change scored on them would be partly fitted
to them, which is tuning to the test set. These 15 have never been fetched.

---

## F0. Contamination disclosure — **to be written by the developer before committing**

_Replace this paragraph. Say plainly what you have seen: the results of the original 20
queries, including which kinds of query the LLM did well and badly on, and that the same person
is writing these queries and will judge the results. State that the earlier verdicts were
AI-proposed (`evaluation/queries.md` § 10) and that these will be judged by hand. Confirm that none of the 15 below is one of
the original 20 or one of the strings in `evaluation/queries.md` § 1, and that none was chosen
because you expect the LLM to do well or badly on it._

---

## F1. The 15 queries — **to be written by the developer**

Same four styles as the original 20, spread across job categories, not concentrated in
technology. Write them the way a real job seeker would type them. Replace every
`_write your query here_`. The fixture script refuses to run while any placeholder remains.

### Casual and vague

| # | Query |
|---|---|
| N01 | _write your query here_ |
| N02 | _write your query here_ |
| N03 | _write your query here_ |
| N04 | _write your query here_ |

### Specific

| # | Query |
|---|---|
| N05 | _write your query here_ |
| N06 | _write your query here_ |
| N07 | _write your query here_ |
| N08 | _write your query here_ |

### Stated constraint (seniority, work type or qualification)

| # | Query |
|---|---|
| N09 | _write your query here_ |
| N10 | _write your query here_ |
| N11 | _write your query here_ |
| N12 | _write your query here_ |

### Negation

| # | Query |
|---|---|
| N13 | _write your query here_ |
| N14 | _write your query here_ |
| N15 | _write your query here_ |

---

## F2. Systems

Each query is fetched once into a frozen pool (`fresh/fixtures/`). The neutral profile is the
same as `evaluation/generate_fixtures.py`: `country=gb`, no skills, no level, no expansion. The
pool is ranked by system B exactly as in `evaluation/queries.md` § 4: the synthetic scores,
with the boost at 0.02. Then:

| System | Definition |
|---|---|
| **K** | The first 3 of `rag_candidates(B, top_k=5)` |
| **L5** | The LLM's picks from `rag_candidates(B, top_k=5)`, the current production behaviour |
| **L10** | The LLM's picks from `rag_candidates(B, top_k=10)` |

The first 5 of the 10 candidates are exactly the 5 candidates, so L10 sees a strict superset.
That is asserted in code. **The only thing that differs between L5 and L10 is how many
candidates the LLM is shown.** The prompt is the one shipped on 2026-10-11 (up to three
picks, or decline), and the model is pinned to `openai/gpt-oss-120b`.

**Pool: all-sources only.** The original Adzuna-only headline existed to give the *ranker* a
genuine keyword baseline. This experiment holds the ranking fixed and measures the LLM, and
all-sources is the pool production hands it.

## F3. Metric

- **precision@3**: relevant picks ÷ 3, **always 3**, as in § 8.2 of the original protocol.
- **A decline** (`{"picks": []}`) scores 0, because the user is shown no picks. Declines are
  counted and reported per system.
- **A failure** (no usable reply) scores as K, because that is what the product shows when
  the panel is hidden (FR-018). Failures are not retried, and they are counted per system.
- Relevance is R1–R5 from `evaluation/queries.md` § 3, read with C1–C4 of § 7, judged on the
  **card only** (§ 8.6). Genuinely ambiguous means not relevant. Eligibility is not part of
  relevance.
- **Judged by the developer, by hand, with no AI assistance.** Added 2026-10-13, before any
  fresh query or pool existed, after it was disclosed that every earlier verdict was
  AI-proposed (`evaluation/queries.md` § 10). This is the one evaluation in the project that
  can be fully human and fully blind.

## F4. Runs and budget

- **Three runs per system per query**, calls spaced 20 s apart, model pinned. A query's L
  score is the mean of its three runs.
- **Truncation probe, before any fresh call:** one call at k = 10 on an *original* query
  (Q07, already seen), checking `finish_reason`. If it is `"length"` at `max_tokens=1200`,
  **both** L5 and L10 run at the same raised budget, and that is recorded here. A budget raised
  for one arm only would be a second variable.

## F5. Comparisons

- **Primary: L10 vs L5.** Mean precision@3, wins, ties and losses, and the two-sided exact
  sign test over non-tied queries.
- **Secondary:** L5 vs K, which replicates the 2026-10-11 result on unseen queries and is the
  first measurement of the decline-capable prompt. Also L10 vs K.
- **Also reported:** eligible@3 per system, declines and failures per system, and how often
  the three runs agree.
- Every query where the simpler system wins is named. **The result is reported whatever it
  is.**

## F6. Judging

- **Pooled, as with precision@5.** Per query, only the union of K's three and every L5 and L10
  pick across all runs is judged. Precision needs verdicts only on what the systems returned.
- The picks therefore exist before the sheet. The sheet is still blind: it is shuffled per
  query, and it never says which system or run chose a card. Which system picked what is
  recorded only in `fresh/judging/key.json` and `fresh/picks/`, and neither is opened before
  marking.
- Duplicates (C3's definition) are noted by the judge and declared in `fresh/score.py` before
  it first runs.
