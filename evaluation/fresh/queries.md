# Fresh-query experiment — does the LLM pick better from 10 candidates than from 5?

**Pre-registered. The 15 queries below are written, and this file committed, before any pool
is fetched.** Nothing below may be edited once `fresh/fixtures/` exists. A badly worded query
is reported as a limitation, never replaced.

Why fresh queries: the 20 queries in `evaluation/queries.md` have been fetched, judged and
scored, and their results have been read. A design change scored on them would be partly fitted
to them, which is tuning to the test set. These 15 have never been fetched.

---

## F0. Contamination disclosure — **to be written by the developer before committing**

Before freezing these queries, I ran all 15 one by one in the live app, signed in as a pakistan account, and looked at the results. So these queries are not unseen by me. I have seen some of the jobs they return, and I am the person who will judge the picks. I will judge from the card alone, using R1–R5, but I may recognise cards I saw while testing.

I did not change any query after seeing its results. 

While testing I noticed three things:

N12 returned jobs that contain “phone” and “visa” rather than jobs that exclude them.
The match percentage stayed at 100% for results that break a stated constraint, even when the “no strong match” banner showed.
The same job showed a different match percentage in the ranked list and in the AI panel.

No code was changed because of these observations before the pools were frozen. They are recorded as findings and will be fixed afterwards.

---

## F1. The 15 queries — **to be written by the developer**

Same four styles as the original 20, spread across job categories, not concentrated in
technology. Write them the way a real job seeker would type them. Replace every
`_write your query here_`. The fixture script refuses to run while any placeholder remains.

### Casual and vague

| # | Query |
|---|---|
| N01 | i used to be a waiter but want an office job now |
| N02 | jobs for introverts who are good at math |
| N03 | remote work that lets you travel the world |
| N04 | lowkey looking for a side hustle in tech that pays quick |

### Specific

| # | Query |
|---|---|
| N05 | Senior DevOps Engineer AWS Terraform Kubernetes CI/CD |
| N06 | Staff Software Engineer distributed systems remote |
| N07 | Figma design systems UI prototyping |
| N08 | Quantitative Developer Python C++ high frequency trading |

### Stated constraint (seniority, work type or qualification)

| # | Query |
|---|---|
| N09 | No experience entry level junior data analyst |
| N10 | remote senior product manager minimum 150k USD |
| N11 | software engineer visa sponsorship provided H1B |
| N12 | night shift customer support immediate start no phone calls |

### Negation

| # | Query |
|---|---|
| N13 | technical product manager role with no coding |
| N14 | remote digital marketing specialist jobs except crypto and web3 |
| N15 | customer support position without phone calls or voice chats |

---

## F2. Systems

Each query is fetched once into a frozen pool (`fresh/fixtures/`). The profile is
**`country=pk`** (a seeker in Pakistan), with no skills, no level and no expansion. This was
decided on 2026-10-27, before any pool was fetched. The country differs from
`evaluation/generate_fixtures.py`, which used `country=gb`. The pool is ranked by system B exactly as in `evaluation/queries.md` § 4: the synthetic scores,
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

**For a Pakistan user, all-sources means Himalayas only.** Adzuna has no Pakistan market, so
it is not queried (deviation 8). Every pool therefore holds only remote jobs that are open
worldwide or to Pakistan. Consequences, stated before fetching:

- These results are **not comparable** with the original 20, which used a UK profile and
  different sources (Adzuna, Remotive, Jobicy).
- Queries whose natural answers are on-site may get thin or off-target pools, for example
  N01 (waiter to office) and N12 (night shift). A small pool is reported as found and is
  never re-fetched.
- N10 (USD salary) and N11 (H1B sponsorship) are US-specific, and a Pakistan seeker cannot
  use H1B sponsorship from a remote role. Eligibility is not part of relevance (F3), so they
  are judged on the role as written. The mismatch is a limitation of the query wording.

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

## F7. Amendment, 2026-10-27, after the raw fetch and before any pick

Written after `fetch_fresh.py` froze the raw pools, which were seen as **counts only**. No job
in any pool and no pick had been seen.

- **What happened:** 7 of the 15 raw pools held 0 or 1 jobs (N01, N02, N03, N04, N10: 0;
  N09, N13: 1). The raw fetch sends the whole query as keywords, and Himalayas matches none
  of "jobs for introverts who are good at math". Production never searches that way.
- **Change 1, retrieval:** the experiment now fetches as production does
  (`fresh/fetch_fresh_expanded.py`). `parse_intent` asks Groq for 2-3 job titles; the query
  and each title are fetched as a Pakistan user and unioned. The intent (titles and
  exclusions) is frozen in each pool. Pools go to `fresh/fixtures_expanded/`. The raw pools
  in `fresh/fixtures/` stay committed, unchanged, as what F2 first produced.
- **Change 2, ranking:** the ranking now handles exclusions, as production does since the
  same day. `parse_intent` returns an `exclude` list ("no phone calls" gives `phone`). Negated
  phrases are removed from the embedded text, and a job naming an excluded term loses 0.25
  (in the title) or 0.10 (in the description only). This fixes the N12 behaviour in F0.
  The synthetic category scores and the 0.02 boost are unchanged.
- **Unchanged:** the 15 queries, the arms K, L5 and L10, the prompt, the model, the metric,
  three runs, and judging by the developer by hand with no AI.
- **Empty pools:** a query whose expanded pool is still empty makes no LLM call (state
  `empty`) and scores 0 for every system, which counts as a tie.
- **Consequence:** this result measures the LLM stage over pools as production builds them,
  with Groq choosing the search titles. Retrieval now involves an LLM call, frozen once. The
  displayed match percentage was also made absolute on this date; it does not affect
  ranking or picks.
- **N06 fetched twice.** On the first expanded fetch its intent call was cut off and fell back
  to keywords (9 jobs). The new `exclude` key had pushed replies to 305-553 of the 600-token
  budget. The budget was raised to 1000 and only N06 was fetched again (38 jobs). As before,
  only counts were seen.
