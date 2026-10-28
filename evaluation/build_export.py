"""Rank each frozen pool under all three systems and write a BLIND judging sheet.

Run with:  venv\\Scripts\\python.exe evaluation/build_export.py

Step 3 of the protocol in docs/EVALUATION.md. Reads evaluation/fixtures/, writes

    evaluation/judging/QNN.md   the sheet you mark up  -- system membership HIDDEN
    evaluation/judging/key.json the unblinding map     -- DO NOT OPEN BEFORE JUDGING

Nothing is fetched and nothing is changed; this only re-orders pools that are already frozen.

HOW THE BLINDING WORKS
----------------------
The three systems' top-5 lists are UNIONED, deduplicated and shuffled into one list per query.
That matters for two reasons:

  - Each job is judged ONCE, so the same listing cannot be called relevant in one system's
    list and irrelevant in another's.
  - Position carries no signal. Three separate lists would let the reader infer which is
    which from the ordering, which is not blind at all.

Source and eligibility are withheld from the sheet. Source leaks the baseline, because the
baseline IS fetch order and fetch order groups by source. Eligibility is not judged at all --
it was settled on 2026-09-26 that it does not count toward relevance, and it is computed from
the data into the key instead, as the separate eligible@5 metric.

THE THREE SYSTEMS, as pre-registered in evaluation/queries.md
-------------------------------------------------------------
  A  baseline   the raw order the APIs returned, untouched
  B  system     similarity + (category_score x CATEGORY_BOOST) -- JobSearchAgent.rank
  C  ablation   the same, with the boost forced to zero

B AND C DIFFER ONLY BY THE BOOST, so B needs a non-empty score set or the two are identical
and the ablation measures nothing. The set below is SYNTHETIC and declared, not discovered:
it represents someone who has saved three technology jobs and two writing jobs and rejected a
design one. It is plausible, but it is a choice, and it biases the comparison toward
technology and writing queries and against design ones. The per-query table is what shows
that -- read the queries where C beats B, not only the means.

Everything else is held constant: the same neutral profile from the fixtures (no skills, no
level) enriches the query for every system, so the ONLY difference between B and C is the
boost, and the only difference from A is the ranking itself.
"""

import html
import json
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core.agent import CATEGORY_BOOST, JobSearchAgent  # noqa: E402
from core.intent_parser import enrich_query, positive_query  # noqa: E402
from core.semantic_engine import SemanticEngine  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
JUDGING = HERE / "judging"

TOP_N = 5

# Declared, synthetic, and the single most arguable choice in this script. See the module
# docstring for what it represents and which way it biases the result.
SYNTHETIC_SCORES = {"technology": 3, "writing": 2, "design": -1}

# Fixed so that re-running produces the SAME shuffle. A sheet that reshuffles on every run
# cannot be checked against the key that was written beside it.
SHUFFLE_SEED = 20260926


def readable(description):
    """Strip an advert down to plain readable text for the judging sheet."""
    # Remotive descriptions are full HTML adverts. Two reasons to strip them, not one:
    # they are unreadable as markdown, AND their tracking links carry utm_source=remotive,
    # which names the source -- and source correlates with the baseline, because the
    # baseline IS fetch order and fetch order groups by source. That would unblind the sheet.
    text = re.sub(r"<[^>]+>", " ", str(description or ""))
    text = html.unescape(text)
    # Any surviving bare URL could still name a source (a jobicy.com or remotive.com link).
    text = re.sub(r"https?://\S+", " ", text)
    return " ".join(text.split())


def rank_systems(query, jobs, engine, exclude=None):
    """Return {system: [job, ...]} for the three pre-registered systems over one pool."""
    # `exclude` was added 2026-10-27 for the fresh experiment, which ranks as production now
    # does. Left as None, as every original-20 caller leaves it, nothing changes.
    # DEDUPLICATE FIRST, with the production function. fetch_variant deliberately does not --
    # it cannot, because deduplication is across all variants and only the agent sees those --
    # so a frozen pool is the raw union and repeats listings syndicated to several sources.
    # Measured across the twenty fixtures: 37 duplicate rows, one job appearing EIGHT times.
    #
    # Without this the baseline is nonsense: system A is fetch order, so its "top 5" could be
    # the same job five times, and precision@5 over it would measure nothing. It would also
    # diverge from the deployed system, which dedupes before it ranks.
    #
    # JobSearchAgent.deduplicate keeps the FIRST occurrence, which is what preserves A's
    # meaning -- the earliest position the APIs gave that listing.
    unique = JobSearchAgent.deduplicate([dict(j) for j in jobs])

    # The boost reads job["category"], which fixtures do not carry -- classification happens
    # in the agent, not at fetch time. Assigned here with intent_category=None because this
    # evaluation runs without intent parsing or expansion (see generate_fixtures.py).
    classified = JobSearchAgent.classify(unique, None)

    # The same neutral profile enriches the query for every system, so B and C differ ONLY by
    # the boost. A does not use the vector at all -- it is the order the APIs returned.
    vector = engine.encode(enrich_query(positive_query(query, exclude), {}))

    agent = JobSearchAgent(db=None, semantic_engine=engine, rag_pipeline=None)
    ranked_b = agent.rank(vector, [dict(j) for j in classified], SYNTHETIC_SCORES, exclude)
    ranked_c = agent.rank(vector, [dict(j) for j in classified], {}, exclude)

    return {"A": list(classified), "B": ranked_b, "C": ranked_c}


def main():
    """Build one blind sheet and one key entry per query."""
    fixtures = sorted(FIXTURES.glob("Q*.json"))
    if not fixtures:
        print("No fixtures. Run evaluation/generate_fixtures.py first.")
        return 1

    JUDGING.mkdir(exist_ok=True)
    if any(JUDGING.glob("Q*.md")):
        print("evaluation/judging/ already holds sheets. Delete them deliberately to rebuild,")
        print("so a half-marked sheet is never silently replaced.")
        return 1

    engine = SemanticEngine()
    rng = random.Random(SHUFFLE_SEED)
    key = {"boost": CATEGORY_BOOST, "scores": SYNTHETIC_SCORES, "queries": {}}

    for path in fixtures:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        qid, query, jobs = fixture["query_id"], fixture["query"], fixture["jobs"]

        if not jobs:
            print(f"  {qid}  empty pool, skipped")
            continue

        systems = rank_systems(query, jobs, engine)
        tops = {name: ranked[:TOP_N] for name, ranked in systems.items()}

        # Union, deduplicated on job_id, then shuffled. Each job judged once.
        candidates = {}
        for name, ranked in tops.items():
            for position, job in enumerate(ranked, 1):
                entry = candidates.setdefault(job["job_id"], {"job": job, "ranks": {}})
                entry["ranks"][name] = position

        shuffled = list(candidates.values())
        rng.shuffle(shuffled)

        lines = [
            f"# {qid} — judging sheet",
            "",
            f"**Query:** `{query}`",
            "",
            f"{len(shuffled)} candidates, shuffled. Which system ranked which is in key.json —",
            "do not open it until every sheet is marked.",
            "",
            "Mark each `[x]` if RELEVANT under R1–R5 in `evaluation/queries.md`. Leave `[ ]` if",
            "not. When a rule is genuinely ambiguous, leave it unmarked and note why.",
            "",
            "Reminder: eligibility is NOT part of relevance. Judge the role, not whether the",
            "employer would hire you from your country.",
            "",
            "---",
            "",
        ]
        for i, entry in enumerate(shuffled, 1):
            job = entry["job"]
            blurb = readable(job.get("description"))[:240]
            lines += [
                f"### {i}. {job.get('title') or 'Untitled'}",
                "",
                f"- **Company:** {job.get('company') or 'Unknown'}",
                f"- **Location:** {job.get('location') or 'Unknown'}",
                f"- {blurb or '_no description supplied by the source_'}",
                "",
                "- [ ] relevant",
                "",
            ]

        (JUDGING / f"{qid}.md").write_text("\n".join(lines), encoding="utf-8")

        key["queries"][qid] = {
            "query": query,
            "pool_size_fetched": len(jobs),
            "pool_size_unique": len(systems["A"]),
            "candidates": {
                job_id: {
                    "title": entry["job"].get("title"),
                    "ranks": entry["ranks"],
                    # Not judged -- computed, for the separate eligible@5 metric.
                    "eligibility": entry["job"].get("eligibility"),
                    "source": entry["job"].get("source"),
                }
                for job_id, entry in candidates.items()
            },
        }
        overlap = sum(1 for e in candidates.values() if len(e["ranks"]) == 3)
        unique_n = len(systems["A"])
        print(f"  {qid}  {len(jobs):3} fetched -> {unique_n:3} unique -> {len(shuffled):2} to "
              f"judge ({overlap} ranked top-5 by all three)")

    (JUDGING / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"\n{len(key['queries'])} sheets in evaluation/judging/.")
    print("key.json written beside them. DO NOT OPEN IT until the sheets are marked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
