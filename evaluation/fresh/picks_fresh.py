"""Freeze the LLM's picks for both arms, L5 and L10, three runs each per fresh query.

Run with:  venv\\Scripts\\python.exe evaluation/fresh/picks_fresh.py

The protocol is evaluation/fresh/queries.md, sections F2 to F4. Writes
evaluation/fresh/picks/NNN.json and prints COUNTS ONLY. Refuses to overwrite.

Calls RAGPipeline.run exactly as production does. The only thing that differs between the arms
is top_k, so the 5 or 10 candidates come from the same rag_candidates over the same ranking.
"""

import json
import pathlib
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE.parent))

from build_export import rank_systems  # noqa: E402
from core.agent import JobSearchAgent  # noqa: E402
from core.rag_pipeline import RAGPipeline  # noqa: E402
from core.semantic_engine import SemanticEngine  # noqa: E402
from generate_rag_picks import MODEL, PAUSE_SECONDS, RUNS, model_still_offered  # noqa: E402

FIXTURES = HERE / "fixtures"
PICKS = HERE / "picks"
ARMS = {"L5": 5, "L10": 10}

# F4: production's budget. Checked by the probe below before any fresh call is made.
BUDGET = 1200
PROBE_FIXTURE = HERE.parent / "fixtures" / "Q07.json"  # an ORIGINAL query, already seen


def candidates(query, jobs, engine):
    """Return {arm: candidate list} for one pool, asserting that L10 sees a superset of L5."""
    ranked = rank_systems(query, jobs, engine)["B"]
    out = {arm: JobSearchAgent.rag_candidates(ranked, top_k=k) for arm, k in ARMS.items()}
    five, ten = ([j["job_id"] for j in out[a]] for a in ("L5", "L10"))
    assert ten[:len(five)] == five, "the first 5 of the 10 candidates must be the 5 candidates"
    return out


def budget_is_enough(engine):
    """F4 probe: one k=10 call on an original query; False if the reply was cut off."""
    # Reads finish_reason, which RAGPipeline.run does not expose, so this one call is made
    # directly on the pipeline's own client with the production parameters.
    fixture = json.loads(PROBE_FIXTURE.read_text(encoding="utf-8"))
    pipeline = RAGPipeline(model=MODEL, top_k=10)
    cands = candidates(fixture["query"], fixture["jobs"], engine)["L10"]
    response = pipeline.client.chat.completions.create(
        model=MODEL, temperature=0.3, max_tokens=BUDGET,
        messages=[{"role": "user", "content": pipeline.build_prompt(fixture["query"], cands)}],
    )
    reason = response.choices[0].finish_reason
    print(f"Truncation probe at k=10, max_tokens={BUDGET}: finish_reason={reason!r}")
    return reason != "length"


def one_run(pipeline, query, cands):
    """Ask once and keep the three states apart: failed (None), declined ([]), or picked."""
    # Not generate_rag_picks.one_run. That one predates 2026-10-11 and counts a decline as a
    # failure, while F3 scores them differently: a failure as K, a decline as 0.
    picks = pipeline.run(query, cands)
    if picks is None:
        return {"state": "failed", "picks": []}
    joined = JobSearchAgent.join_picks(picks, cands)
    ids = {c["job_id"] for c in cands}
    assert all(j["job_id"] in ids for j in joined), "a pick is not among its candidates"
    return {
        "state": "picked" if joined else "declined",
        "picks": [{"job_id": j["job_id"], "reason": j.get("ai_reason", "")} for j in joined],
    }


def main():
    """Probe, then generate and freeze RUNS runs per arm per fresh query."""
    fixtures = sorted(FIXTURES.glob("N*.json"))
    if len(fixtures) != 15:
        print(f"Expected 15 fresh pools, found {len(fixtures)}. Run fetch_fresh.py first.")
        return 1
    PICKS.mkdir(exist_ok=True)
    if any(PICKS.glob("N*.json")):
        print("fresh/picks/ already holds picks. They are one frozen sample; not regenerated.")
        return 1

    engine = SemanticEngine()
    if not budget_is_enough(engine):
        print("STOPPING -- k=10 truncates at the production budget. Record this in F4 and")
        print("decide a common budget for both arms before generating anything.")
        return 1
    pipelines = {arm: RAGPipeline(model=MODEL, top_k=k) for arm, k in ARMS.items()}
    if not model_still_offered(pipelines["L5"]):
        print(f"{MODEL} is no longer offered. Stopping.")
        return 1

    tally = {arm: {"failed": 0, "declined": 0, "picked": 0} for arm in ARMS}
    for path in fixtures:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        qid, query = fixture["query_id"], fixture["query"]
        cands = candidates(query, fixture["jobs"], engine)
        record = {"query_id": qid, "query": query, "model": MODEL, "budget": BUDGET, "arms": {}}
        for arm in ARMS:
            runs = []
            for _ in range(RUNS):
                runs.append(one_run(pipelines[arm], query, cands[arm]))
                tally[arm][runs[-1]["state"]] += 1
                time.sleep(PAUSE_SECONDS)
            record["arms"][arm] = {"candidates": [c["job_id"] for c in cands[arm]], "runs": runs}
        (PICKS / f"{qid}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        print(f"  {qid}  candidates: L5 {len(cands['L5'])}, L10 {len(cands['L10'])}", flush=True)

    print(f"\nRun states (counts only): {tally}")
    print("Picks frozen in fresh/picks/. Do not open them until the sheet is marked.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
