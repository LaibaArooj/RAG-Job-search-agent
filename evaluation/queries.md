# Evaluation queries and relevance rule — pre-registered

**Written 2026-09-23, before any result set was generated or inspected.** That ordering is the
whole point: choosing queries after seeing what the system does well is how an evaluation
quietly becomes a demonstration. Nothing below may be edited once fixtures are frozen — if a
query turns out to be badly worded, report it as a limitation rather than replacing it.

Protocol: `docs/EVALUATION.md`.

---

## 1. Contamination disclosure

Full honesty about what has already been seen, because it bounds what this evaluation can claim.

During development on 2026-09-22 and 2026-09-23 the following strings were sent to the live
APIs while diagnosing bugs and evaluating Jobicy:

`junior software engineer`, `software engineer`, `engineer`, `remote writing job no experience`,
`writing`, `entry level marketing no degree`, `marketing`, `designer`, `python`, `nurse`,
`nurse practitioner remote`, `something creative I can do from home`, `qwertyuiop`, `design`,
`frontend for begginers`, `junior software enginner`

**None of the 20 queries below is one of those strings.** For most of the above only *result
counts* were seen, not ranked lists — the exception is `junior software engineer`, where a full
ranked list and the AI panel were inspected several times. It is deliberately excluded.

This is a real but limited contamination: the same *person* who debugged the ranker is choosing
the queries and will judge the results. State that in the report alongside the numbers.

---

## 2. The 20 queries

Five in each of the four styles `docs/EVALUATION.md` names. Spread deliberately across
categories, not concentrated in technology — a tech-only sample would flatter a system whose
hint table is richest there.

### Casual and vague

| # | Query |
|---|---|
| Q01 | something creative I can do from my bedroom |
| Q02 | a job where I help people all day |
| Q03 | work with numbers but not boring |
| Q04 | I want to get into tech but I have no degree |
| Q05 | somewhere I can use my writing and actually get paid |

### Specific

| # | Query |
|---|---|
| Q06 | junior frontend developer react remote |
| Q07 | registered nurse night shift |
| Q08 | graphic designer figma branding |
| Q09 | financial analyst excel modelling |
| Q10 | primary school teaching assistant |

### Constraint-heavy

| # | Query |
|---|---|
| Q11 | entry level marketing role no degree required |
| Q12 | part time customer support work from home |
| Q13 | paralegal position no prior experience |
| Q14 | remote data entry job that hires worldwide |
| Q15 | freelance copywriting contract short term |

### Awkward phrasing the system is meant to handle

| # | Query |
|---|---|
| Q16 | job where I write stuff but not journalism |
| Q17 | not sales but still talking to customers |
| Q18 | something in HR that isn't recruitment |
| Q19 | coding job that isn't web development |
| Q20 | design work that doesn't need a portfolio |

**Q16–Q20 all contain a negation, and that is on purpose.** Sentence embeddings handle negation
poorly — "not journalism" and "journalism" sit close together in the vector space — so this
block is the one most likely to make the system look *worse* than the baseline. Including
queries chosen to expose a known weakness is what separates an evaluation from a demo, and the
result is worth reporting either way.

---

## 3. Relevance rule — fixed before judging

A result is **relevant** if and only if **all five** hold. Applied mechanically; when a rule is
genuinely ambiguous for a listing, mark it not relevant and log why.

| | Rule |
|---|---|
| **R1** | It is a real, specific job advert — not a category page, not an agency "register your CV with us" placeholder, not a duplicate of an already-counted listing in the same top 5. |
| **R2** | The **role type** is one a person making this query would plausibly click. |
| **R3** | If the query states a **seniority**, the listing does not contradict it. "entry level" vs a listing titled Senior/Lead/Principal → not relevant. |
| **R4** | If the query states a **work type** (remote, part-time, freelance), the listing does not contradict it. |
| **R5** | If the query states an **exclusion**, the listing is not in the excluded set. Q16 excludes journalism, Q17 excludes sales roles, Q18 excludes recruitment, Q19 excludes web development, Q20 excludes roles demanding a portfolio. |

**Silence is not a contradiction.** A listing that simply doesn't mention remote working does
not fail R4; only one that states an incompatible requirement does. Judging silence as failure
would punish Adzuna's terser adverts and bias the baseline.

### Eligibility is deliberately NOT part of relevance

Whether the employer will hire from the user's country is a property of the **job**, not of the
**ranking** — and both systems draw from the identical frozen pool, so folding it into relevance
would measure the sources, not the re-ranker. precision@5 exists to test one claim: *does
semantic re-ranking order the pool better than the raw API order?*

Eligibility is instead recorded as a **separate secondary metric, eligible@5** — how many of
each system's top 5 the seeker could actually apply for. That reports the benefit of the
2026-09-23 work without contaminating the primary number.

> **SETTLED 2026-09-26, before any fixture was generated: eligibility does NOT count toward
> relevance.** It is reported separately as eligible@5. This section is now frozen.

---

## 4. Systems compared

Ranked over the same frozen pool per query, so any difference is ranking, not retrieval.

| System | Definition |
|---|---|
| **A — Baseline** | Raw source order, unmodified, as the APIs returned it |
| **B — System** | `similarity + (category_score × CATEGORY_BOOST)`, i.e. `JobSearchAgent.rank` |
| **C — Ablation** | Semantic similarity with `CATEGORY_BOOST = 0` |

C isolates how much the hand-picked 0.02 coefficient actually contributes. It is the only
evidence available for a constant `docs/PROJECT_SPEC.md` lists as an unjustified limitation, so
it is worth the extra column.

**All three run with the same user profile and the same `category_scores`.** Record which
profile was used in the results file — B is personalised by definition, and a run against an
empty score set would make B and C identical and the comparison meaningless.

---

## 5. The Adzuna question — settle before generating fixtures

Unresolved, and it changes what the headline number means.

Adzuna is the only source doing a genuine keyword search, so it is the only honest keyword
baseline. But since 2026-09-23 it is a minority of what the user sees and its listings are
badged inapplicable for a non-UK seeker. Remotive's order is query-independent, and Jobicy's
`geo=anywhere` ordering is not a keyword ranking either.

**SETTLED 2026-09-26, before any fixture was generated:**

- **Headline: Adzuna-only precision@5**, A vs B vs C. The only genuine keyword-vs-semantic contrast.
- **Secondary: all-sources precision@5**, with the caveat stated in the same sentence as the number.
- **Never** present a single blended figure as "keyword baseline vs semantic ranking".

---

## 6. Procedure

1. Run each query once. Save raw API responses to `evaluation/fixtures/QNN.json`. **Do not read them.**
2. Rank each frozen pool under A, B and C.
3. Export the top 5 from each into one shuffled list per query, system hidden.
4. Judge against R1–R5. Record eligible@5 separately.
5. Unblind. Compute per-query P@5 and the mean for each system.
6. Report the table, the means, the deltas, and **every query where the baseline beat the system** — those are the informative ones.

Fixtures cost roughly 20 Adzuna calls out of 250/day. Run them in one sitting so the pools are
contemporaneous; a pool fetched a day later is a different pool.
