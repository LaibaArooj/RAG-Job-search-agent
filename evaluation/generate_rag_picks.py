"""Freeze the LLM's picks for the RAG-stage evaluation, three runs per query and pool.

Run with:  venv\\Scripts\\python.exe evaluation/generate_rag_picks.py

The protocol is evaluation/queries.md § 8, committed before this script first ran. Writes
evaluation/rag_picks/QNN.json and prints COUNTS ONLY. Like key.json, the picks are not
looked at before the RAG sheet is marked, so the judge cannot learn which candidates the LLM
chose.

Re-running refuses to overwrite. A pick file is one sample of a stochastic system, and
regenerating it until the numbers looked better would be the same selection that
pre-registering the queries rules out.

WHAT IS AND IS NOT UNDER TEST
-----------------------------
The candidates come from rag_candidates over system B's ranking -- the five jobs production
hands the LLM. K is the first three of them; L is what the LLM picks from the same five. The
ranking is held fixed, so this measures the LLM's choice and nothing upstream of it.
"""

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_export import rank_systems  # noqa: E402
from core.agent import JobSearchAgent  # noqa: E402
from core.rag_pipeline import RAGPipeline, complete, model_is_gone  # noqa: E402
from core.semantic_engine import SemanticEngine  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
PICKS = HERE / "rag_picks"

# § 8.3. Pinned so the fallback chain cannot change the model being measured partway through.
MODEL = "openai/gpt-oss-120b"
RUNS = 3

# § 8.3. Spaced so the free tier's per-minute token limit is never hit. A rate-limited call
# returns None and would be scored as a tie, which is an artefact of the experiment rather
# than something the product does to a single user.
PAUSE_SECONDS = 20

POOLS = ("adzuna", "all")


def candidates_for(query, jobs, engine):
    """Return {pool: [the five candidates the AI panel would be handed]} for one fixture."""
    # Shared with build_rag_supplement.py, so the jobs that get judged are provably the jobs
    # the LLM was offered.
    pools = {
        "adzuna": [job for job in jobs if job.get("source") == "Adzuna"],
        "all": list(jobs),
    }
    out = {}
    for name, pool in pools.items():
        if not pool:
            continue
        ranked_b = rank_systems(query, pool, engine)["B"]
        out[name] = JobSearchAgent.rag_candidates(ranked_b)
    return out


def model_still_offered(pipeline):
    """Probe the pinned model once, so a retirement stops the run instead of scoring as ties."""
    # Necessary because RAGPipeline.run catches everything and returns None. With a single
    # pinned model, a retired one would look exactly like three failed runs per query, and
    # § 8.3 scores a failure as a tie -- the evaluation would quietly report "no difference".
    try:
        complete(pipeline.client, [{"role": "user", "content": "Reply with the word OK."}],
                 models=pipeline.models, max_tokens=200)
        return True
    except Exception as e:
        print(f"Probe failed: {e}")
        return not model_is_gone(e)


def one_run(pipeline, query, candidates):
    """Ask the LLM once and return {picks: [{job_id, reason}], failed}."""
    picks = pipeline.run(query, candidates)
    joined = JobSearchAgent.join_picks(picks, candidates)
    if not joined:
        return {"picks": [], "failed": True}
    ids = {c["job_id"] for c in candidates}
    for job in joined:
        # join_picks takes every field from the dict we passed, so this cannot fail unless
        # that boundary breaks. Asserted anyway: a pick outside the five would be scored
        # against a verdict that may not exist.
        assert job["job_id"] in ids, f"pick {job['job_id']} is not among the candidates"
    return {
        "picks": [{"job_id": job["job_id"], "reason": job.get("ai_reason", "")} for job in joined],
        "failed": False,
    }


def main():
    """Generate and freeze RUNS sets of picks per query and pool."""
    PICKS.mkdir(exist_ok=True)
    if any(PICKS.glob("Q*.json")):
        print("evaluation/rag_picks/ already holds picks. They are one frozen sample;")
        print("delete them deliberately to regenerate, and record why in queries.md § 8.")
        return 1

    pipeline = RAGPipeline(model=MODEL)
    if not model_still_offered(pipeline):
        print(f"{MODEL} is no longer offered. Stopping, per queries.md § 8.3 -- record it there.")
        return 1

    engine = SemanticEngine()
    failures = calls = 0
    for path in sorted(FIXTURES.glob("Q*.json")):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        qid, query = fixture["query_id"], fixture["query"]
        record = {"query_id": qid, "query": query, "model": MODEL, "pools": {}}

        for pool, candidates in candidates_for(query, fixture["jobs"], engine).items():
            runs = []
            for _ in range(RUNS):
                runs.append(one_run(pipeline, query, candidates))
                calls += 1
                time.sleep(PAUSE_SECONDS)
            failures += sum(r["failed"] for r in runs)
            record["pools"][pool] = {
                "candidates": [c["job_id"] for c in candidates],
                "runs": runs,
            }

        (PICKS / f"{qid}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        # Counts only. Which jobs were picked stays in the file until the RAG sheet is marked.
        sizes = ", ".join(f"{p} {len(v['candidates'])}" for p, v in record["pools"].items())
        print(f"  {qid}  candidates: {sizes}", flush=True)

    print(f"\n{calls} calls, {failures} failed runs (scored as K, per § 8.3).")
    print("Picks frozen in evaluation/rag_picks/. Do not open them until SUPPLEMENT-rag.md is marked.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
