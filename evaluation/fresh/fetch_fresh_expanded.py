"""Freeze one pool per fresh query the way PRODUCTION fetches it: with query expansion.

Run with:  venv\\Scripts\\python.exe evaluation/fresh/fetch_fresh_expanded.py

Added 2026-10-27 (evaluation/fresh/queries.md, F7). fetch_fresh.py sends the raw query as
keywords, and 7 of the 15 pools came back with 0 or 1 jobs: "jobs for introverts who are good
at math" is a sentence no advert contains. Production never searches that way. It asks Groq
for 2-3 job titles (parse_intent), fetches the query and each title, and unions the results.

This script does exactly that, once per query, and freezes the INTENT alongside the jobs, so
the Groq-chosen titles and exclusions are part of the record and the pool never changes again.
Writes evaluation/fresh/fixtures_expanded/NNN.json, prints counts only, refuses to overwrite.
The raw pools in fresh/fixtures/ are untouched and stay committed as what F2 first produced.
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent))

import config  # noqa: E402
from adapters.api_client import fetch_variant  # noqa: E402
from core.intent_parser import parse_intent  # noqa: E402
from fetch_fresh import PROFILE, load_queries  # noqa: E402

FIXTURES = HERE / "fixtures_expanded"


def main():
    """Parse intent, fetch every variant, and freeze the union per fresh query."""
    try:
        queries = load_queries()
    except ValueError as error:
        print(f"NOT FETCHING -- {error}.")
        return 1

    FIXTURES.mkdir(exist_ok=True)
    for qid, query in queries:
        path = FIXTURES / f"{qid}.json"
        if path.exists():
            print(f"  {qid}  already frozen, left alone")
            continue
        intent = parse_intent(query)
        jobs, failed = [], []
        for variant in intent["variants"]:
            # The same arguments JobSearchAgent.run passes, with the neutral profile's country.
            result = fetch_variant(variant, config.ADZUNA_APP_ID, config.ADZUNA_APP_KEY,
                                   work_type=intent["work_type"], experience=intent["experience"],
                                   country=PROFILE["country"])
            jobs.extend(card.to_dict() for card in result["jobs"])
            failed += [s for s in result["failed_sources"] if s not in failed]
        path.write_text(json.dumps({
            "query_id": qid,
            "query": query,
            "profile": PROFILE,
            "expansion": True,
            "intent": intent,
            "failed_sources": failed,
            "jobs": jobs,  # the raw union in variant order; deduplicated when ranked
        }, indent=2), encoding="utf-8")
        unique = len({j["job_id"] for j in jobs})
        print(f"  {qid}  {unique:3} unique jobs  intent from {intent['source']}  "
              f"failed sources: {failed or 'none'}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
