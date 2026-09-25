"""Freeze one job pool per pre-registered query, so both systems rank identical data.

Run with:  venv\\Scripts\\python.exe evaluation/generate_fixtures.py

Step 2 of the protocol in docs/EVALUATION.md. Writes evaluation/fixtures/QNN.json and prints
COUNTS ONLY -- the results are deliberately not displayed, because the queries were
pre-registered precisely so that nothing downstream could be chosen after seeing them.

Re-running refuses to overwrite an existing fixture. Once a pool is frozen it is the pool the
evaluation was run against, and silently replacing it would make the numbers unreproducible.

TWO METHOD DECISIONS, both made before generation and both affecting what the number means.

1. NO QUERY EXPANSION. The pipeline normally fetches once per LLM-generated variant and
   unions the results. This script fetches the user's query ONCE. The reason is that the
   baseline is defined as "the raw order the API returned", and across a union of three
   fetches there is no such thing as a raw order. docs/EVALUATION.md requires both systems to
   rank the SAME pool; one fetch is what makes that true.

   The cost, and it belongs in the report: precision@5 therefore measures the RANKING claim,
   not the whole deployed system. Query expansion is a retrieval change -- it widens what is
   available to rank -- and it is not measured here. Do not report this number as though it
   evaluated expansion.

2. A NEUTRAL PROFILE. country=gb so that Adzuna is queried at all (it is the headline
   baseline, and it has no market for the author's own country). Empty skills, no stated
   level, and empty category_scores, so enrich_query contributes the same constant to every
   query and cannot favour some of the twenty over others. TC-016's profile injection is
   therefore also NOT measured here.

   The category boost is exercised separately, in the ranking step, against a synthetic score
   set that is recorded alongside the results rather than baked into the pool.
"""

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from adapters.api_client import fetch_variant  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

# The profile every fetch runs under. Recorded in each fixture so a reader can see it without
# reading this file.
PROFILE = {"country": "gb", "skills": [], "experience": None, "category_scores": {}}


def load_queries():
    """Read the twenty pre-registered queries out of queries.md, in order."""
    # Parsed from the committed markdown rather than duplicated here, so the queries that are
    # RUN are provably the queries that were pre-registered. A second copy could drift, and a
    # drifted copy is exactly how a pre-registration quietly stops meaning anything.
    text = (pathlib.Path(__file__).resolve().parent / "queries.md").read_text(encoding="utf-8")
    found = re.findall(r"^\|\s*(Q\d\d)\s*\|\s*(.+?)\s*\|$", text, flags=re.MULTILINE)
    return [(qid, query) for qid, query in found if query.lower() != "query"]


def main():
    """Fetch and freeze one pool per query, printing counts and nothing else."""
    FIXTURES.mkdir(exist_ok=True)
    queries = load_queries()

    if len(queries) != 20:
        print(f"Expected 20 queries in queries.md, found {len(queries)}. Aborting.")
        return 1

    print(f"{len(queries)} pre-registered queries. Profile: {PROFILE}\n")
    written = skipped = 0

    for qid, query in queries:
        path = FIXTURES / f"{qid}.json"
        if path.exists():
            print(f"  {qid}  already frozen, left alone")
            skipped += 1
            continue

        result = fetch_variant(
            query,
            config.ADZUNA_APP_ID,
            config.ADZUNA_APP_KEY,
            work_type=None,
            experience=None,
            country=PROFILE["country"],
        )
        jobs = [card.to_dict() for card in result["jobs"]]

        path.write_text(json.dumps({
            "query_id": qid,
            "query": query,
            "profile": PROFILE,
            "expansion": False,
            "failed_sources": result["failed_sources"],
            "empty_sources": result["empty_sources"],
            # Stored in FETCH ORDER, untouched. That order IS the baseline system, so
            # sorting or deduplicating here would destroy the thing being measured.
            "jobs": jobs,
        }, indent=2), encoding="utf-8")

        by_source = {}
        for job in jobs:
            by_source[job["source"]] = by_source.get(job["source"], 0) + 1
        adzuna = by_source.get("Adzuna", 0)
        flag = "  <-- no Adzuna, headline cannot use this query" if not adzuna else ""
        print(f"  {qid}  {len(jobs):3} jobs  {by_source}{flag}")
        written += 1

    print(f"\n{written} frozen, {skipped} already existed.")
    print("Pools are NOT displayed on purpose. Judge from the blind export, not from here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
