# Frozen pools — state of the fixtures

Regenerated **2026-09-26** by `evaluation/generate_fixtures.py`, after the Adzuna keyword
narrowing shipped. Each `QNN.json` holds one query's job pool in **fetch order**, which is the
baseline system — sorting or deduplicating it would destroy the thing being measured.

| | |
|---|---|
| Queries | 20 |
| **Usable for the Adzuna-only headline** (≥5 Adzuna results) | **17** |
| Below 5 Adzuna results | Q03 (1), Q04 (0), Q09 (1) |
| Empty pools | **none** |
| Total jobs frozen | 517 (mean 25.9 per query) |

Profile for every fetch: `country=gb`, no skills, no level, no category scores. Expansion off.
Both decisions are argued in `generate_fixtures.py` and they bound what the result can claim —
this measures the **ranking**, not the deployed system.

## Why these were regenerated, and what it cost

The first freeze (commit `8f90eb0`) was taken before the Adzuna keyword fix. Under that
behaviour Adzuna answered **3 of 20** queries and **16 pools contained no Adzuna jobs at all**,
because `what=` is an AND match and natural-language queries match no advert. The Adzuna-only
headline was not computable, and three pools were completely empty.

Regenerating was therefore not optional: the baseline system had changed, so the old pools
measured a retrieval layer that no longer exists.

**The old pools are preserved in git at `8f90eb0`.** They are worth keeping as evidence for
the report — *"the keyword baseline could not retrieve for 17 of 20 natural-language queries"*
is a finding in its own right, and arguably a stronger one than the precision comparison,
because it says keyword search does not reach the starting line for the queries the SRS
describes.

## The three queries the headline cannot use

Report them, do not quietly drop them.

- **Q03** *"work with numbers but not boring"* — 1 Adzuna result. Needs interpretation:
  "numbers" means finance, which the query never says. `finance` returns plenty. Only the
  LLM's query expansion could make that leap, and expansion is deliberately off here.
- **Q04** *"I want to get into tech but I have no degree"* — 0 Adzuna. No word in it names a
  field: "tech" is not in `CATEGORY_HINTS`, and "degree" is not a job.
- **Q09** *"financial analyst excel modelling"* — 1 Adzuna. A specific, well-formed query that
  the UK market simply has little of right now.

Q03 and Q04 are the same class: the query describes a *situation* rather than a *field*, which
is precisely the kind of query this project claims to serve and the keyword layer cannot.

## Re-running

`generate_fixtures.py` refuses to overwrite an existing fixture — once a pool is frozen it is
the pool the numbers were computed against. To regenerate deliberately, delete the files first
and commit the replacement, so the change is visible in history rather than silent.
