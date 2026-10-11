"""Write the BLIND judging sheet for the fresh experiment: the pooled union per query.

Run with:  venv\\Scripts\\python.exe evaluation/fresh/sheet_fresh.py

The protocol is evaluation/fresh/queries.md, section F6. For each query, judges the union of
K's three and every L5 and L10 pick across all runs. Writes

    evaluation/fresh/judging/SHEET.md   the sheet you mark -- which system chose what is HIDDEN
    evaluation/fresh/judging/key.json   card -> job_id and membership -- DO NOT OPEN BEFORE MARKING

Cards are shuffled per query and use the same format as every earlier sheet. Refuses to
overwrite.
"""

import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent))

from build_export import readable  # noqa: E402
from core.agent import JobSearchAgent  # noqa: E402

FIXTURES = HERE / "fixtures"
PICKS = HERE / "picks"
JUDGING = HERE / "judging"
SHUFFLE_SEED = 20261013
K = 3


def members(record):
    """Return {job_id: set of systems that returned it} for one query's frozen picks."""
    out = {}
    for job_id in record["arms"]["L5"]["candidates"][:K]:
        out.setdefault(job_id, set()).add("K")
    for arm, frozen in record["arms"].items():
        for run in frozen["runs"]:
            for pick in run["picks"]:
                out.setdefault(pick["job_id"], set()).add(arm)
    return out


def main():
    """Build one shuffled section per query and the key beside it."""
    if (JUDGING / "SHEET.md").exists():
        print("The fresh sheet already exists. Delete it deliberately to rebuild.")
        return 1
    records = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(PICKS.glob("N*.json"))]
    if len(records) != 15:
        print(f"Expected 15 pick files, found {len(records)}. Run picks_fresh.py first.")
        return 1

    rng = random.Random(SHUFFLE_SEED)
    key = {"queries": {}}
    sections = []
    for record in records:
        qid = record["query_id"]
        fixture = json.loads((FIXTURES / f"{qid}.json").read_text(encoding="utf-8"))
        # First occurrence, as every earlier sheet showed it.
        by_id = {j["job_id"]: j for j in reversed(JobSearchAgent.deduplicate(
            [dict(j) for j in fixture["jobs"]]))}
        union = members(record)
        job_ids = list(union)
        rng.shuffle(job_ids)

        key["queries"][qid] = {"query": record["query"], "cards": {}}
        sections += [f"## {qid} — `{record['query']}`", ""]
        for n, job_id in enumerate(job_ids, 1):
            job = by_id[job_id]
            key["queries"][qid]["cards"][str(n)] = {
                "job_id": job_id, "title": job.get("title") or "Untitled",
                "eligibility": job.get("eligibility"), "systems": sorted(union[job_id]),
            }
            sections += [
                f"### {qid}.{n}. {job.get('title') or 'Untitled'}",
                "",
                f"- **Company:** {job.get('company') or 'Unknown'}",
                f"- **Location:** {job.get('location') or 'Unknown'}",
                f"- {readable(job.get('description'))[:240] or '_no description supplied_'}",
                "",
                "- [ ] relevant",
                "",
            ]

    total = sum(len(q["cards"]) for q in key["queries"].values())
    header = [
        "# Fresh queries — judging sheet",
        "",
        "**Status:** unmarked",
        "",
        f"{total} cards over 15 queries, shuffled within each query. Mark each `[x]` if RELEVANT",
        "under R1–R5 in `evaluation/queries.md` § 3, read with C1–C4 in § 7, on the card alone.",
        "Genuinely ambiguous means not relevant; write one line saying why. Eligibility is not",
        "part of relevance. Note any card that is the same vacancy as another in its query.",
        "",
        "Do not open `key.json` or `fresh/picks/` until every card is marked. When done, change",
        "the Status line to `marked`.",
        "",
        "---",
        "",
    ]
    JUDGING.mkdir(exist_ok=True)
    (JUDGING / "SHEET.md").write_text("\n".join(header + sections), encoding="utf-8")
    (JUDGING / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"{total} cards written to fresh/judging/SHEET.md; key.json beside it.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
