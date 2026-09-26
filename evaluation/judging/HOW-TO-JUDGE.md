# How to mark these sheets

20 sheets, **139 candidates** in total. Budget an hour or two, and do it in one sitting if you
can — a relevance rule applied on Tuesday and again on Friday is two rules.

## The rule

Open `evaluation/queries.md` § 3 and keep it beside you. A candidate is **relevant** only if
all five hold:

| | |
|---|---|
| **R1** | a real, specific advert — not a category page or a "register your CV" placeholder |
| **R2** | the role type is one a person making this query would plausibly click |
| **R3** | it does not contradict a seniority the query stated |
| **R4** | it does not contradict a work type the query stated |
| **R5** | it is not in a set the query excluded (Q16 excludes journalism, Q17 sales, Q18 recruitment, Q19 web development, Q20 portfolio-required roles) |

**Silence is not a contradiction.** An advert that simply does not mention remote working does
not fail R4. Judging silence as failure would punish Adzuna's terser adverts and bias the
baseline.

**Eligibility is NOT part of relevance** — settled 2026-09-26. Judge the role, not whether the
employer would hire someone in your country. That is measured separately as eligible@5, from
data, without your judgement.

When a rule is genuinely ambiguous, **leave it unmarked and write why** next to it. An
ambiguous case recorded is evidence; an ambiguous case silently resolved is bias.

## Marking

Change `- [ ] relevant` to `- [x] relevant`. Leave the rest alone.

## What not to do

- **Do not open `key.json`.** It says which system ranked what. Opening it before you finish
  turns a blind assessment into an unblind one, and there is no way to undo that.
- **Do not reorder or delete candidates.** The scorer matches on position.
- **Do not go back and "fix" earlier sheets** once you see how the numbers are trending.

## When every sheet is marked

The scorer reads the sheets and `key.json`, unblinds, and computes precision@5 per system plus
eligible@5. Then the honest framing from `docs/EVALUATION.md` applies: twenty queries judged by
the developer is a small-scale relevance assessment indicating the direction of an effect,
limited by a single non-blind-to-the-project judge and a 20-query sample. **Say that in the
report.** Naming the weakness is what makes the number credible.
