"""Freeze one job pool per fresh query, the same way the original 20 were frozen.

Run with:  venv\\Scripts\\python.exe evaluation/fresh/fetch_fresh.py

The protocol is evaluation/fresh/queries.md. Writes evaluation/fresh/fixtures/NNN.json and
prints COUNTS ONLY. It refuses to run until all 15 queries and the contamination disclosure
have been written, and it refuses to overwrite a frozen pool. It never touches
evaluation/fixtures/.

The fetch is the original one: one call per query, no expansion, no skills, no level. The one
change is the country. The original 20 ran as country=gb; these run as a PAKISTAN user
(decided 2026-10-27, per the 10-25 plan), because that is who the deployed product is for.
Adzuna has no Pakistan market, so it is skipped and every pool is Himalayas only (remote jobs
open worldwide or to Pakistan). So a fresh pool is NOT comparable to an original one.
"""

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent))

import config  # noqa: E402
from adapters.api_client import fetch_variant  # noqa: E402

FIXTURES = HERE / "fixtures"
EXPECTED = [f"N{n:02d}" for n in range(1, 16)]
PLACEHOLDER = "_write your query here_"
DISCLOSURE_PLACEHOLDER = "_Replace this paragraph."

# Neutral apart from the country, as in generate_fixtures.PROFILE. Recorded in each fixture.
PROFILE = {"country": "pk", "skills": [], "experience": None, "category_scores": {}}


def load_queries():
    """Read the fifteen pre-registered queries from fresh/queries.md, refusing placeholders."""
    text = (HERE / "queries.md").read_text(encoding="utf-8")
    if DISCLOSURE_PLACEHOLDER in text:
        raise ValueError("the contamination disclosure (F0) has not been written yet")
    disclosure = text.split("## F0.", 1)[-1].split("## F1.", 1)[0]
    if re.search(r"\[[^\]]*\]", disclosure):
        raise ValueError("the contamination disclosure (F0) still has an unfilled [ ] choice")
    found = re.findall(r"^\|\s*(N\d\d)\s*\|\s*(.+?)\s*\|\s*$", text, flags=re.M)
    if [qid for qid, _ in found] != EXPECTED:
        raise ValueError(f"expected rows N01-N15 in order, found {[q for q, _ in found]}")
    blank = [qid for qid, query in found if query == PLACEHOLDER or not query.strip()]
    if blank:
        raise ValueError(f"queries still to be written: {', '.join(blank)}")
    return found


def main():
    """Fetch and freeze one pool per fresh query, printing counts and nothing else."""
    try:
        queries = load_queries()
    except ValueError as error:
        print(f"NOT FETCHING -- {error}.")
        return 1

    FIXTURES.mkdir(exist_ok=True)
    written = 0
    for qid, query in queries:
        path = FIXTURES / f"{qid}.json"
        if path.exists():
            print(f"  {qid}  already frozen, left alone")
            continue
        result = fetch_variant(query, config.ADZUNA_APP_ID, config.ADZUNA_APP_KEY,
                               work_type=None, experience=None, country=PROFILE["country"])
        jobs = [card.to_dict() for card in result["jobs"]]
        path.write_text(json.dumps({
            "query_id": qid,
            "query": query,
            "profile": PROFILE,
            "expansion": False,
            "failed_sources": result["failed_sources"],
            "empty_sources": result["empty_sources"],
            "jobs": jobs,  # fetch order, untouched
        }, indent=2), encoding="utf-8")
        print(f"  {qid}  {len(jobs):3} jobs  failed sources: {result['failed_sources'] or 'none'}")
        written += 1

    print(f"\n{written} pools frozen. Not displayed on purpose.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
