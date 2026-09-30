"""Write a BLIND sheet for the Adzuna-only candidates the main sheets never showed.

Run with:  venv\\Scripts\\python.exe evaluation/build_supplement.py

WHY THIS EXISTS -- see evaluation/queries.md § 7, C6
----------------------------------------------------
build_export.py judged the three systems' ALL-SOURCES top 5s. The pre-registered headline is
ADZUNA-ONLY precision@5, where each system ranks only the Adzuna jobs in the pool. Those top
5s can reach listings that were never in any all-sources top 5, so they were never judged.
This finds them and writes one sheet to mark, plus a key for the scorer:

    evaluation/judging/SUPPLEMENT-adzuna.md   the sheet you mark up -- system HIDDEN
    evaluation/judging/key_adzuna.json        Adzuna-only ranks     -- DO NOT OPEN BEFORE JUDGING

The key records every Adzuna-only top-5 candidate, including the ones already judged on a main
sheet, so the scorer has the complete Adzuna-only ranking in one place.

Blinding is the same as the main export: each listing appears once, shuffled with a fixed
seed, with no source, rank or eligibility on the sheet. key.json is read only for its job ids
-- which listings are already judged -- and nothing from it is printed.
"""

import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_export import TOP_N, rank_systems, readable  # noqa: E402
from core.semantic_engine import SemanticEngine  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
JUDGING = HERE / "judging"
SHEET = JUDGING / "SUPPLEMENT-adzuna.md"
KEY = JUDGING / "key_adzuna.json"

# A different seed from build_export.py, so this shuffle is fixed but independent of that one.
SHUFFLE_SEED = 20260930


def main():
    """Rank each pool's Adzuna jobs under A, B and C and write the unjudged ones to one sheet."""
    if SHEET.exists():
        print(f"{SHEET.name} already exists. Delete it deliberately to rebuild,")
        print("so a half-marked sheet is never silently replaced.")
        return 1

    main_key = json.loads((JUDGING / "key.json").read_text(encoding="utf-8"))
    engine = SemanticEngine()
    rng = random.Random(SHUFFLE_SEED)
    key = {"boost": main_key["boost"], "scores": main_key["scores"], "queries": {}}
    sections = []
    total = 0

    for path in sorted(FIXTURES.glob("Q*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        qid, query = fixture["query_id"], fixture["query"]
        adzuna = [job for job in fixture["jobs"] if job.get("source") == "Adzuna"]
        if not adzuna:
            print(f"  {qid}  no Adzuna jobs, nothing to rank")
            continue

        # The same ranking code as the main export, fed only the Adzuna rows. A stays fetch
        # order, because filtering a list preserves the order of what survives.
        systems = rank_systems(query, adzuna, engine)
        already_judged = set(main_key["queries"].get(qid, {}).get("candidates", {}))

        candidates = {}
        for name, ranked in systems.items():
            for position, job in enumerate(ranked[:TOP_N], 1):
                entry = candidates.setdefault(job["job_id"], {"job": job, "ranks": {}})
                entry["ranks"][name] = position

        unjudged = [e for jid, e in candidates.items() if jid not in already_judged]
        rng.shuffle(unjudged)

        key["queries"][qid] = {
            "query": query,
            "adzuna_pool_unique": len(systems["A"]),
            "candidates": {
                job_id: {
                    "title": entry["job"].get("title"),
                    "ranks": entry["ranks"],
                    "eligibility": entry["job"].get("eligibility"),
                    # Where the verdict lives: a main sheet, or this supplement's position.
                    "judged_on": "main" if job_id in already_judged else "supplement",
                }
                for job_id, entry in candidates.items()
            },
        }
        for position, entry in enumerate(unjudged, 1):
            key["queries"][qid]["candidates"][entry["job"]["job_id"]]["supplement_n"] = position

        if not unjudged:
            continue
        total += len(unjudged)
        sections += [f"## {qid} — `{query}`", ""]
        for position, entry in enumerate(unjudged, 1):
            job = entry["job"]
            blurb = readable(job.get("description"))[:240]
            sections += [
                f"### {qid}.{position}. {job.get('title') or 'Untitled'}",
                "",
                f"- **Company:** {job.get('company') or 'Unknown'}",
                f"- **Location:** {job.get('location') or 'Unknown'}",
                f"- {blurb or '_no description supplied by the source_'}",
                "",
                "- [ ] relevant",
                "",
            ]
        print(f"  {qid}  {len(unjudged)} to judge")

    header = [
        "# Adzuna-only supplement — judging sheet",
        "",
        f"{total} candidates the main sheets never showed. They are needed for the headline",
        "Adzuna-only precision@5 (`evaluation/queries.md` § 7, C6). Which system ranked which is",
        "in key_adzuna.json — do not open it until this sheet is marked.",
        "",
        "Mark each `[x]` if RELEVANT under R1–R5 in `evaluation/queries.md` § 3, **read with the",
        "clarifications C1–C3 in § 7**. Leave `[ ]` if not. When a rule is genuinely ambiguous,",
        "leave it unmarked and note why.",
        "",
        "Reminder: eligibility is NOT part of relevance. Judge the role, not whether the",
        "employer would hire you from your country.",
        "",
        "---",
        "",
    ]
    SHEET.write_text("\n".join(header + sections), encoding="utf-8")
    KEY.write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"\n{total} candidates written to {SHEET.name}.")
    print(f"{KEY.name} written beside it. DO NOT OPEN IT until the sheet is marked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
