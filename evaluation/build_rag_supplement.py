"""Write a BLIND sheet for the RAG-stage candidates that no earlier sheet showed.

Run with:  venv\\Scripts\\python.exe evaluation/build_rag_supplement.py

WHY THIS EXISTS -- see evaluation/queries.md § 8.4
--------------------------------------------------
The AI panel is handed rag_candidates over system B's ranking: applicable jobs first, from
anywhere in the list. In the all-sources pools that lifts jobs ranked 6th or lower, which no
main or Adzuna sheet ever showed. This finds them and writes:

    evaluation/judging/SUPPLEMENT-rag.md   the sheet you mark up
    evaluation/judging/key_rag.json        where every candidate's verdict lives

THE SHEET CANNOT LEAK THE LLM'S CHOICES. Candidates are computed from the frozen pools and the
ranking alone; the LLM is not called and evaluation/rag_picks/ is not read. Which jobs were
picked is therefore not on this sheet, and could not be put there by accident.

Adzuna-only candidates need no new judging: every Adzuna listing is `local`, so
rag_candidates reduces to B's Adzuna-only top 5, all of which key_adzuna.json already covers.
That is asserted below rather than assumed.
"""

import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_export import readable  # noqa: E402
from core.semantic_engine import SemanticEngine  # noqa: E402
from generate_rag_picks import candidates_for  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
JUDGING = HERE / "judging"
SHEET = JUDGING / "SUPPLEMENT-rag.md"
KEY = JUDGING / "key_rag.json"

# Independent of the two earlier shuffles, and fixed so the scorer can check the sheet.
SHUFFLE_SEED = 20261001


def main():
    """Find every RAG candidate with no verdict yet and write them to one shuffled sheet."""
    if SHEET.exists():
        print(f"{SHEET.name} already exists. Delete it deliberately to rebuild,")
        print("so a half-marked sheet is never silently replaced.")
        return 1

    # Read for job ids only -- which listings already have a verdict -- and nothing printed.
    main_key = json.loads((JUDGING / "key.json").read_text(encoding="utf-8"))
    adzuna_key = json.loads((JUDGING / "key_adzuna.json").read_text(encoding="utf-8"))

    engine = SemanticEngine()
    rng = random.Random(SHUFFLE_SEED)
    key = {"queries": {}}
    sections = []
    total = 0

    for path in sorted(FIXTURES.glob("Q*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        qid, query = fixture["query_id"], fixture["query"]
        on_main = set(main_key["queries"].get(qid, {}).get("candidates", {}))
        on_adzuna = {jid for jid, c in adzuna_key["queries"].get(qid, {}).get("candidates", {}).items()
                     if c["judged_on"] == "supplement"}

        pools = candidates_for(query, fixture["jobs"], engine)
        for job in pools.get("adzuna", []):
            if job["job_id"] not in on_main | on_adzuna:
                print(f"  {qid}  an Adzuna-only candidate has no verdict -- § 8.4 assumed none")
                return 1

        entry = key["queries"][qid] = {"query": query, "pools": {}, "candidates": {}}
        unjudged = []
        for pool, candidates in pools.items():
            entry["pools"][pool] = [job["job_id"] for job in candidates]
            for job in candidates:
                jid = job["job_id"]
                if jid in entry["candidates"]:
                    continue
                where = "main" if jid in on_main else "adzuna" if jid in on_adzuna else "rag"
                entry["candidates"][jid] = {
                    "title": job.get("title"),
                    # Not judged -- computed, for the separate eligible@3 metric (§ 8.5).
                    "eligibility": job.get("eligibility"),
                    "source": job.get("source"),
                    "judged_on": where,
                }
                if where == "rag":
                    unjudged.append(job)

        rng.shuffle(unjudged)
        for position, job in enumerate(unjudged, 1):
            entry["candidates"][job["job_id"]]["rag_n"] = position

        if not unjudged:
            continue
        total += len(unjudged)
        sections += [f"## {qid} — `{query}`", ""]
        for position, job in enumerate(unjudged, 1):
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
        "# RAG-stage supplement — judging sheet",
        "",
        f"{total} candidates that no earlier sheet showed. They are needed for the all-sources",
        "RAG-stage comparison (`evaluation/queries.md` § 8). Nothing on this sheet says which",
        "jobs the LLM picked, and nothing could: the candidates were chosen without calling it.",
        "",
        "Mark each `[x]` if RELEVANT under R1–R5 in `evaluation/queries.md` § 3, **read with the",
        "clarifications C1–C4 in § 7**. Leave `[ ]` if not. When a rule is genuinely ambiguous,",
        "leave it unmarked and note why.",
        "",
        "Reminder: eligibility is NOT part of relevance. Judge the role, not whether the",
        "employer would hire you from your country.",
        "",
        "Also note any listing that is the SAME vacancy as another in its query (C3's",
        "definition), so the pair can be declared in § 8.2 before scoring.",
        "",
        "---",
        "",
    ]
    SHEET.write_text("\n".join(header + sections), encoding="utf-8")
    KEY.write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"\n{total} candidates written to {SHEET.name}; {KEY.name} beside it.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
