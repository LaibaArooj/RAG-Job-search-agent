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

---

## 7. Post-hoc clarifications — made blind, 2026-09-30

**Everything above this line is unchanged.** These clarifications were written *after* the 20
sheets were marked but *before* `key.json` was opened, so none of them could have been chosen
to favour a system — the judge did not know which system ranked which listing. They are
recorded here, not folded into § 3, so the report can say exactly what was pre-registered and
what was decided later.

### C1 — Stated qualification requirements are read under R3

R3 as written covers seniority only. Three queries state a qualification the seeker lacks:
Q04 and Q11 ("no degree"), Q13 ("no prior experience"). They are judged by the same logic R3
and R4 already use: a listing that **explicitly states** a requirement contradicting the
query's claim fails; a listing that is **silent** passes. "No prior experience" is close to a
seniority claim; "no degree" is an extension by analogy, and the report should say so. This
affected the verdict on 3 of the 20 sheets. It is a clarification of R3, deliberately not a
new R6.

### C2 — Silence is not a contradiction under R5 either (Q20)

R5 excludes, for Q20, "roles *demanding* a portfolio". A listing that does not state a
portfolio requirement does not demand one, so it passes R5 — even where the judge believes the
industry usually expects one. Background knowledge about what a role "normally" needs is not
applied, because it cannot be applied consistently across listings and would let the judge's
priors stand in for the advert's text. The § 3 ambiguity clause is for a rule that is unclear
for a listing, not for a rule the judge disagrees with. Q20 is reported under both readings as
a sensitivity check.

### C3 — R1 duplicates are applied by the scorer, not the judge

R1 disqualifies a duplicate "of an already-counted listing in the same top 5". A blind judge
cannot apply that, because they do not know which listings share a top 5. Each candidate is
judged on its merits; the scorer then counts only the higher-ranked copy when both copies of
a duplicate fall in one system's top 5.

A **duplicate** is the same vacancy: the same employer (or a sister company), the same title
after normalising punctuation, and the same location. Shared template text is not enough —
one employer advertising different posts at different sites with one template has posted
separate vacancies. On that definition, three pairs survived the fixture dedup (which matches
on `job_id` only, and Adzuna gave each copy its own id): **Q05 #1/#4, Q08 #4/#5, Q10 #1/#4.**
Q07 #1/#4, Q12 #2/#5 and Q17 #4/#1 and #5/#2 are templated but distinct vacancies.

**Extended 2026-09-30, still blind** (after a mechanical scan of every sheet, before
`score.py` was run): the same vacancy **advertised through an agency** is also a duplicate,
even though the advertiser's name and wording differ. The test is the same title, the same
town, the same salary and matching role details. Three pairs meet it: **Q01 #3/#4** (Creative
Lead, Meta ads, Magherafelt, £35k), **Q11 #5/#7** (Head of Marketing, group-wide, Omagh,
£55k), **Q15 #1/#5** (Copywriter, heritage architecture, London, £37k). That makes six
declared pairs in all.

### C4 — Queries with no relevant candidate stay in the mean as 0

Q14, Q17 and Q18 had no relevant candidate among those judged — the union of the three
systems' top 5s, **not** the whole pool (Q14's pool has 60 unique jobs). They stay in every
mean as 0, because they were pre-registered and dropping queries after judging is exactly
the selection § 1 warns against. It lowers every system equally and leaves the deltas
unchanged. A secondary mean over the queries where at least one system found a relevant
result is reported beside it and labelled as such.

### C5 — precision@5 always divides by 5

Where a pool, or a system's list, has fewer than five results (Q03's pool has one job),
precision@5 is still relevant ÷ 5. Dividing by the number returned would inflate small pools.

### C6 — The Adzuna-only headline needed a supplementary sheet

The main sheets hold the three **all-sources** top 5s. Ranked over the Adzuna jobs alone, the
systems' top 5s include 13 listings that appear on no main sheet (Q02 1, Q06 7, Q10 1, Q14 1,
Q19 3). They are judged blind on `judging/SUPPLEMENT-adzuna.md`, under the same rules and
these clarifications, before unblinding.

The Adzuna-only comparison is structurally weaker than planned: Q04 has no Adzuna jobs, and
Q01, Q03, Q09, Q12, Q17 and Q20 have five or fewer, so all three systems return the same set
and tie by construction. The headline therefore discriminates on at most 13 queries. State
that beside the number.

---

## 8. RAG-stage evaluation — pre-registered 2026-10-01, before any pick was generated

**Everything above this line is unchanged, and so are the 20 queries and the frozen pools.**
This section asks a second question of the same data: given the five jobs the AI panel is
handed, are the LLM's three picks more relevant than simply taking the first three? It was
written and committed before `generate_rag_picks.py` made a single Groq call.

### 8.1 Systems

Both systems start from the same five **candidates**: `JobSearchAgent.rag_candidates` applied
to system B's ranking (§ 4, the synthetic profile and the 0.02 boost). These are exactly the
five jobs production hands the LLM.

| System | Definition |
|---|---|
| **K — first three** | The first three candidates, in order |
| **L — LLM picks** | The jobs `RAGPipeline.run` picks from the same five, mapped from index to `job_id` |

Both systems have the same inputs, so any difference comes from the LLM alone. The ranking is
not under test here; § 4 already measured it. The LLM gets the raw query string, as it does
in production (`JobSearchAgent.run`).

### 8.2 Metric

**precision@3**: relevant listings in the list ÷ 3. The divisor is **always 3**, the same
logic as C5. If the LLM returns fewer than three valid picks, the missing ones score 0, and
if the pool has fewer than three jobs, both systems are divided by 3 all the same.

R1–R5 apply as written, read with C1–C4. Each job keeps the verdict it was given on the main
sheet or the Adzuna supplement, because a job's relevance to a query does not depend on which
system surfaced it. C3's six duplicate pairs apply. If a candidate judged for the first time
on the RAG sheet (§ 8.4) is a copy of another candidate in the same query under C3's
definition, the pair is declared in this section before `score_rag.py` is first run.

### 8.3 Runs, failures and model

- **The model is pinned** to `openai/gpt-oss-120b` via `RAGPipeline(model=...)`, so the fallback
  chain cannot switch models silently mid-experiment. The script probes the model once before
  it starts. If the model has been retired, it stops, and the stop is recorded here.
- **Three runs per query and pool.** The model is sampled at temperature 0.3 with no seed, so
  one run is one sample of a stochastic system. A query's L score is the mean over its three
  runs. The report gives the per-run spread and how many runs picked exactly K's set.
- **A failed run** (`run` returns `None`) is scored as K, because K is what the product shows
  when Groq fails (FR-018), so a failure always scores as a tie. Failed runs are **not retried**,
  because retrying only the failures would change that rule. The count of failed runs is reported.
- Calls are spaced 20 s apart to stay inside the free tier's per-minute token limit, so rate
  limiting does not create artificial failures.

### 8.4 Pools

- **Headline: Adzuna-only**, Q04 excluded. Every Adzuna listing is `local`, so
  `rag_candidates` reduces to B's Adzuna-only top 5, and every candidate already has a verdict
  in `key_adzuna.json`. No new judging is needed. A pool of three or fewer Adzuna jobs gives K
  and L the same set, so they tie by construction; such queries are marked † and also
  reported separately.
- **Secondary: all-sources.** `rag_candidates` lifts applicable jobs from anywhere in B's
  ranking, so some candidates rank 6th or lower and were never judged. They are judged blind on
  `judging/SUPPLEMENT-rag.md`, built by `build_rag_supplement.py`. The sheet lists candidates
  only. Which ones were picks is not on it and cannot be: the candidates do not depend on
  the LLM.

### 8.5 Reported alongside

- **eligible@3**, computed from the data, all-sources only. **This is a known confound.** The
  prompt tells the LLM to prefer roles the seeker can apply for, but relevance excludes
  eligibility (settled 2026-09-26). An LLM that follows its prompt can therefore lower
  precision@3 while raising eligible@3. Report both, side by side.
- Wins, ties and losses, plus the two-sided exact sign test over non-tied queries. Every query
  where K beats L is named.
- **The result is reported whatever it is.**

### 8.6 Clarifications made after judging, before `score_rag.py` first ran — 2026-10-11

**Everything above in § 8 is unchanged.** No pick had been opened when these were written.

- **One evidence base: the card.** Every verdict on the earlier sheets was made on the card
  (title, company, location, the first 240 characters). The RAG sheet's first pass judged
  Q11.2 against the live posting on external job boards. That posting may not match the frozen
  advert, and no other verdict used it. Q11.2 was therefore re-judged on its card alone:
  **relevant** (R2 plausible, silent on seniority and degree under C1). The external reading,
  not relevant, is reported as a sensitivity check. The Welocalize cards (Q15.1–4 and
  Q16.1–4) were also read externally, but they are not relevant on either reading, so nothing
  changes.
- **Q10.1 on `SUPPLEMENT-adzuna.md` keeps its blind 09-30 verdict (relevant).** On
  2026-10-11 the judge re-read it as not relevant: R2 is ambiguous, because the card describes
  a graduate pathway into primary teaching and never states "teaching assistant". That
  re-reading came **after** `results.md` was published. Applying it would change a verdict
  after unblinding, which is what pre-registration exists to prevent. So, as with Q20 under
  C2, the headline uses the blind verdict, and the re-reading is scored beside it for both
  precision@5 (Adzuna-only) and precision@3.
- **Duplicates:** the judge found no C3 pairs among the RAG-sheet candidates, so
  `RAG_DUPLICATES` stays empty.
