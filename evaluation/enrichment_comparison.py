"""Measure how much of the query survives enrich_query, across candidate formats.

Run with:  venv\\Scripts\\python.exe evaluation/enrichment_comparison.py

WHY THIS EXISTS
---------------
core/intent_parser.enrich_query folds the user's profile into the query text before it is
embedded. Until 2026-09-26 it produced

    "job search: {query}. Skills: {skills}. Level: {level}."

and for a short query the LABELS were most of that string, so the vector described the
scaffolding rather than the search. Reported from real use as results that were "related to
the field but completely unrelated to what I would apply for".

This script is the evidence for the replacement, and it exists so the numbers in
docs/CHANGELOG.md can be regenerated rather than taken on trust. It changes nothing.

WHAT IT MEASURES
----------------
Two properties that pull against each other, because a format that wins one by losing the
other is not an improvement:

  discrimination - does the query still separate a relevant job from an irrelevant one?
                   Scored over the ten cases in model_comparison.py, with and without a
                   profile, plus a targeted "customer support" probe.
  TC-016 lift    - does the profile still pull results toward the user's skills? That is a
                   required behaviour, not an optional one, so a format that maximises
                   discrimination by discarding the profile fails.

verify_agent.py cannot assert any of this: it is offline by design and loads no model. So the
similarity evidence lives here, and the offline suite asserts the STRUCTURAL property instead
(the query is present and repeated, no labels, no empty segments).
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sentence_transformers import SentenceTransformer, util  # noqa: E402

from evaluation.model_comparison import CASES  # noqa: E402

MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _join(parts):
    """Join non-empty parts, the way the shipped enrich_query does."""
    kept = [p for p in parts if p]
    return ". ".join(kept) + "." if kept else ""


FORMATS = {
    "A  old (labels)": lambda q, s, l: f"job search: {q}. Skills: {s}. Level: {l}.",
    "B  bare":         lambda q, s, l: _join([q, s, l]),
    "C  query x2":     lambda q, s, l: _join([q, q, s, l]),   # <-- shipped
    "D  query x3":     lambda q, s, l: _join([q, q, q, s, l]),
    "E  query only":   lambda q, s, l: q,
}

# A support job against a QA job: the exact pair that exposed the problem on a real search.
PROBE_QUERY = "customer support"
PROBE_GOOD = "Cloud Support Engineer. Help customers resolve technical issues, respond to tickets."
PROBE_BAD = "QA Tester (Future Roles). Write and run test plans for software releases."

# TC-016's own claim: a user whose profile lists Python should see Python roles ranked higher.
LIFT_QUERY = "developer job"
LIFT_GOOD = "Python Developer. Build Django services and REST APIs."
LIFT_BAD = "Java Developer. Spring Boot microservices and Oracle."


def main():
    """Score every candidate format and print the comparison table."""
    model = SentenceTransformer(MODEL)
    embed = {}

    def sim(a, b):
        """Cosine similarity between two strings, caching the encodings."""
        for text in (a, b):
            if text not in embed:
                embed[text] = model.encode(text, convert_to_tensor=True)
        return float(util.cos_sim(embed[a], embed[b])[0][0])

    profiles = [("neutral (no skills, no level)", "", ""),
                ("python / entry level", "python", "entry level")]

    print(f"\n{'format':18}", end="")
    for label, _, _ in profiles:
        print(f"{label[:22]:>26}", end="")
    print(f"{'probe':>10}{'TC-016 lift':>14}")
    print("-" * 96)

    for name, fmt in FORMATS.items():
        print(f"{name:18}", end="")
        for _, skills, level in profiles:
            correct = 0
            margins = []
            for query, good, bad, _probe in CASES:
                text = fmt(query, skills, level)
                gap = sim(text, good) - sim(text, bad)
                correct += gap > 0
                margins.append(gap)
            acc = correct / len(CASES)
            print(f"{acc:>13.0%}{sum(margins) / len(margins):>+13.3f}", end="")

        probe_text = fmt(PROBE_QUERY, "python", "entry level")
        probe = sim(probe_text, PROBE_GOOD) - sim(probe_text, PROBE_BAD)
        lift_text = fmt(LIFT_QUERY, "Python", "entry level")
        lift = sim(lift_text, LIFT_GOOD) - sim(lift_text, LIFT_BAD)
        print(f"{probe:>+10.3f}{lift:>+14.3f}")

    print("-" * 96)
    print("Each profile column is: accuracy over the 10 cases, then mean margin.")
    print("probe       = 'customer support' separating a support job from a QA job.")
    print("TC-016 lift = a Python profile separating a Python job from a Java job.")
    print("\nC is shipped. It matches or beats A on every column, so there was no trade to")
    print("make; D shows that repeating the query a third time adds nothing, which is why")
    print("the repeat count is two by measurement rather than by taste. E is the control:")
    print("it maximises the probe and guts TC-016, which is the behaviour being protected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
