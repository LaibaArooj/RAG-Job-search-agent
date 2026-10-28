# Embedding model comparison — results

Run 2026-09-25 with `evaluation/model_comparison.py`. **Nothing was changed** —
`core/semantic_engine.py` still loads `all-MiniLM-L6-v2`, the model the SRS names.

## What this is

A discrimination probe on ten hand-written cases. Each is a query, a job that clearly fits,
and a job that clearly does not; a model gets it right if it scores the fitting job higher.

**It is not the precision@5 evaluation.** It uses none of the twenty pre-registered queries,
touches no live API, and is not blind. It is evidence for the supervisor conversation about
the model swap, produced in a minute, not a substitute for `docs/EVALUATION.md`.

## Results

| Case | MiniLM | msmarco | Winner |
|---|---|---|---|
| seniority: "junior" vs "senior" (the pair ARCHITECTURE.md flags) | +0.098 | +0.041 | MiniLM |
| seniority, other direction: "entry level" vs "Head of" | **−0.031** | +0.115 | msmarco |
| category: writing vs unrelated | +0.495 | +0.378 | MiniLM |
| vague casual phrasing (the SRS's own example style) | +0.267 | +0.296 | msmarco |
| category: healthcare vs technology | +0.378 | +0.428 | msmarco |
| fine-grained: Python vs Java | +0.373 | **+0.095** | MiniLM |
| **negation: "write stuff but not journalism"** | **−0.135** | +0.005 | msmarco |
| work type plus category | +0.361 | +0.161 | MiniLM |
| same field, wrong level and setting | +0.477 | +0.692 | msmarco |
| category: data vs unrelated | +0.619 | +0.755 | msmarco |
| **Accuracy** | **80%** | **100%** | |
| **Mean margin** | +0.290 | +0.296 | |

## What it shows

**msmarco is more reliable, not more confident.** Accuracy goes 80% → 100%, but the mean
margin is effectively unchanged (+0.290 → +0.296). The gain is in the two cases MiniLM gets
*backwards*, not in a general sharpening.

**MiniLM's two failures are both already-documented weaknesses, now measured:**

1. **Negation, −0.135.** For *"job where I write stuff but not journalism"*, MiniLM ranks the
   **news reporter above the copywriter** — it reads "not journalism" as "journalism". This is
   direct, quantified support for the prediction written into `evaluation/queries.md`, where
   Q16–Q20 were deliberately chosen as negation queries expected to expose this.
2. **Seniority, −0.031.** For *"entry level marketing role"* it ranks **Head of Marketing above
   Marketing Assistant**. This is the weakness `_wrong_level` in `adapters/api_client.py`
   exists to paper over with keyword matching, and it is why that filter is not optional.

**But msmarco is not a clean win, and the report must not claim it is.**

- Its negation margin is **+0.005** — a coin flip. msmarco does not *solve* negation; on this
  one case it lands the right side of a near-tie. Ten more negation cases could easily split
  differently.
- It is clearly **worse at fine-grained discrimination within a field**: Python vs Java
  collapses from +0.373 to +0.095. For a job search where most queries are within one field,
  that is the wrong direction.
- It is also weaker on the "junior vs senior" pair (+0.041 vs +0.098), even while being better
  on the other seniority case — so its seniority handling is inconsistent, not better.

**Both survive the category boost.** `core/agent.py` adds `category_score × 0.02`, so a
category scored 5 contributes +0.10. Both models' mean margins (~+0.29) are comfortably above
that, which is the first real evidence that `CATEGORY_BOOST` nudges rather than overrules —
something `PROJECT_SPEC.md` currently lists as an unjustified heuristic. **Note the caveat:**
a *mean* of +0.29 says nothing about the narrow cases, and MiniLM's junior/senior margin of
+0.098 is *below* +0.10 — so on exactly the comparison the system is weakest at, a strongly
learned preference **can** overturn meaning.

One incidental finding: msmarco's `max_seq_length` is **512** against MiniLM's **256**, so it
reads roughly twice as much of each advert. That bears on limitation 3 (truncation) and was
not part of the original argument for the swap.

## Recommendation

**Do not swap on this evidence alone.** It is ten hand-written pairs judged by the developer,
and it shows a trade — better on negation and one seniority case, worse on within-field
discrimination — not an improvement.

The defensible path: run both models as an extra column in the precision@5 evaluation, where
twenty pre-registered queries and a written relevance rule do the judging. That turns the
swap from an argument into a measurement, and it costs one extra ranking pass over fixtures
that have to be generated anyway.

If the swap is made, it still needs supervisor sign-off, because the SRS names the model.

## Reproducing

```bash
venv\Scripts\python.exe evaluation/model_comparison.py
```

Downloads `msmarco-MiniLM-L6-v3` (~90 MB) on first run and caches it. Reads nothing from the
database and calls no external API beyond the model download.
