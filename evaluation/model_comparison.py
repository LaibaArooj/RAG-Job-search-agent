"""Compare all-MiniLM-L6-v2 against msmarco-MiniLM-L6-v3 on this project's actual task.

Run with:  venv\\Scripts\\python.exe evaluation/model_comparison.py

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
This is NOT the precision@5 evaluation in docs/EVALUATION.md. It does not use the twenty
pre-registered queries, it does not touch a live API, and it is not blind. It is a
discrimination probe on hand-written pairs, which is weaker evidence -- but it is aimed
directly at the one claim the model swap rests on, and it can be run in a minute.

THE CLAIM UNDER TEST
--------------------
docs/PROJECT_SPEC.md § Deviations records that `all-MiniLM-L6-v2` is trained for SYMMETRIC
sentence similarity -- two texts of similar length -- while this system matches a short query
against a long job advert, which is an ASYMMETRIC task. `msmarco-MiniLM-L6-v3` is trained on
exactly that: short search queries against long passages.

Deviating from the model the SRS names needs supervisor sign-off, so this script produces
evidence for that conversation. IT CHANGES NOTHING. core/semantic_engine.py is untouched.

THE METHOD
----------
Each case is a query plus a job that clearly fits and a job that clearly does not. A model
gets the case right if it scores the fitting job higher. Two numbers are reported:

  accuracy - how many of the cases the model ranks correctly
  margin   - the mean gap between the right job and the wrong one, which matters because
             core/agent.py adds a category boost of 0.02 on top. A model whose margins are
             narrower than that boost is one where a learned preference can overturn meaning.

The cases deliberately include the seniority pair that docs/ARCHITECTURE.md already records
as a weakness: all-MiniLM-L6-v2 rates "junior developer" against "senior developer" at 0.806,
near-synonyms, which is why _wrong_level exists as a keyword filter in api_client.
"""

import sys

from sentence_transformers import SentenceTransformer, util

BASELINE = "sentence-transformers/all-MiniLM-L6-v2"
CANDIDATE = "sentence-transformers/msmarco-MiniLM-L6-v3"

# A long advert body, reused so that every case exercises the short-query-to-long-document
# shape the swap is supposed to help with, rather than comparing two short strings.
PADDING = (
    " We are a fast growing company with a collaborative culture and a strong commitment to "
    "learning and development. You will join a supportive team, take part in code review and "
    "planning, and have the opportunity to grow into wider responsibilities over time. We "
    "offer flexible hours, a generous holiday allowance and a budget for training. "
)

# (query, the job that fits, the job that does not, what the case is probing)
CASES = [
    ("junior software developer, no experience",
     "Junior Software Developer. Graduate role, we will train you." + PADDING,
     "Senior Software Developer. Eight years of experience required, you will lead the team." + PADDING,
     "seniority: the pair ARCHITECTURE.md records as near-synonyms"),
    ("entry level marketing role",
     "Marketing Assistant. Entry level, no degree required." + PADDING,
     "Head of Marketing. Fifteen years experience, board level." + PADDING,
     "seniority, other direction"),
    ("remote writing job",
     "Content Writer. Write blog posts and articles, fully remote." + PADDING,
     "Warehouse Operative. On site in Leeds, manual handling." + PADDING,
     "category: writing vs unrelated"),
    ("something creative I can do from home",
     "Graphic Designer. Branding and illustration, work from anywhere." + PADDING,
     "Financial Controller. Statutory accounts and audit." + PADDING,
     "vague casual phrasing, the SRS's own example style"),
    ("nursing job in a hospital",
     "Registered Nurse. Ward based, ICU experience welcome." + PADDING,
     "Software Engineer. Python and Kubernetes." + PADDING,
     "category: healthcare vs technology"),
    ("python developer",
     "Backend Developer. Python, Django and PostgreSQL." + PADDING,
     "Java Developer. Spring Boot and Oracle." + PADDING,
     "fine-grained: one technology against another"),
    ("job where I write stuff but not journalism",
     "Copywriter. Marketing copy for web and email campaigns." + PADDING,
     "News Reporter. Court reporting and local news desk." + PADDING,
     "NEGATION, which embeddings handle poorly -- the hard case"),
    ("part time customer support",
     "Customer Support Agent. Part time, 20 hours a week, help desk." + PADDING,
     "Full Time Sales Executive. Cold calling and field visits." + PADDING,
     "work type plus category"),
    ("teaching assistant in a primary school",
     "Primary School Teaching Assistant. Supporting KS1 pupils." + PADDING,
     "University Lecturer in Astrophysics. Research and PhD supervision." + PADDING,
     "same field, wrong level and setting"),
    ("data analyst with excel",
     "Data Analyst. Excel, SQL and Power BI reporting." + PADDING,
     "Delivery Driver. Van licence required, local routes." + PADDING,
     "category: data vs unrelated"),
]


def score_model(name):
    """Return (accuracy, mean margin, per-case results) for one model over every case."""
    model = SentenceTransformer(name)
    correct = 0
    margins = []
    rows = []
    for query, good, bad, probe in CASES:
        q = model.encode(query, convert_to_tensor=True)
        g = float(util.cos_sim(q, model.encode(good, convert_to_tensor=True))[0][0])
        b = float(util.cos_sim(q, model.encode(bad, convert_to_tensor=True))[0][0])
        ok = g > b
        correct += ok
        margins.append(g - b)
        rows.append((probe, g, b, g - b, ok))
    return correct / len(CASES), sum(margins) / len(margins), rows


def main():
    """Score both models, print the per-case table and the summary, and compare."""
    results = {}
    for label, name in (("baseline", BASELINE), ("candidate", CANDIDATE)):
        print(f"\nLoading {name} ...")
        results[label] = score_model(name)

    base_acc, base_margin, base_rows = results["baseline"]
    cand_acc, cand_margin, cand_rows = results["candidate"]

    print("\n" + "=" * 92)
    print(f"{'case':<58}{'MiniLM':>10}{'msmarco':>10}{'winner':>12}")
    print("=" * 92)
    for (probe, bg, bb, bm, bok), (_, cg, cb, cm, cok) in zip(base_rows, cand_rows):
        if bok and not cok:
            winner = "MiniLM"
        elif cok and not bok:
            winner = "msmarco"
        elif not bok and not cok:
            winner = "both wrong"
        else:
            winner = "msmarco" if cm > bm else "MiniLM"
        print(f"{probe[:56]:<58}{bm:>+10.3f}{cm:>+10.3f}{winner:>12}")

    print("=" * 92)
    print(f"{'accuracy (cases ranked correctly)':<58}"
          f"{base_acc:>10.0%}{cand_acc:>10.0%}")
    print(f"{'mean margin (right job minus wrong job)':<58}"
          f"{base_margin:>+10.3f}{cand_margin:>+10.3f}")
    print("=" * 92)

    # The margin matters against a specific number, not in the abstract: core/agent.py adds
    # category_score x 0.02 on top of similarity. A margin near that size is one a learned
    # preference can overturn, which is the thing the report has to be able to say.
    boost = 0.02 * 5
    print(f"\nFor scale: a category scored 5 contributes {boost:+.2f} via CATEGORY_BOOST.")
    for label, margin in (("all-MiniLM-L6-v2", base_margin), ("msmarco-MiniLM-L6-v3", cand_margin)):
        verdict = "CAN be overturned by the boost" if margin < boost else "survives the boost"
        print(f"  {label:<24} mean margin {margin:+.3f} -- {verdict}")

    print("\nReminder: this is a discrimination probe on ten hand-written pairs, not the "
          "precision@5 evaluation. It is evidence for the supervisor conversation about the "
          "model swap, not a substitute for docs/EVALUATION.md. Nothing was changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
