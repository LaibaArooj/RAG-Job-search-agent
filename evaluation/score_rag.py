"""Unblind the RAG-stage evaluation: precision@3 for the LLM's picks (L) vs the first three (K).

Run with:  venv\\Scripts\\python.exe evaluation/score_rag.py          (writes rag_results.md)
           venv\\Scripts\\python.exe evaluation/score_rag.py --check  (validates, scores nothing)

The protocol is evaluation/queries.md § 8, pre-registered before any pick existed. Reads,
and never writes to:

    evaluation/rag_picks/QNN.json            the frozen picks, from generate_rag_picks.py
    evaluation/judging/key_rag.json          the candidates and where each verdict lives
    evaluation/judging/SUPPLEMENT-rag.md     the marked RAG sheet
    evaluation/judging/QNN.md, SUPPLEMENT-adzuna.md, key.json, key_adzuna.json
                                             the earlier verdicts, reused (§ 8.2)

and writes evaluation/rag_results.md. Verdict loading, the C3 duplicate pairs, precision and
the sign test all come from score.py. One rule set, applied by one piece of code.
"""

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from score import (  # noqa: E402
    APPLICABLE, DUPLICATES, JUDGING, SheetError, compare, eligible, fmt, load_main_verdicts,
    load_supplement_verdicts, mean, parse_cards, precision, read_box,
)

HERE = pathlib.Path(__file__).resolve().parent
PICKS = HERE / "rag_picks"
SHEET = JUDGING / "SUPPLEMENT-rag.md"
RESULTS = HERE / "rag_results.md"

K = 3  # § 8.2: precision@3, always divided by 3.

# § 8.2: C3 pairs among RAG-sheet candidates, declared before this script is first run.
# Each side is ("main", sheet position) or ("rag", supplement number), within one query.
RAG_DUPLICATES = {}

POOL_NAMES = {"adzuna": "Adzuna-only", "all": "all-sources"}


def sheet_is_marked(text):
    """Return True only once the judge has changed the sheet's status line to 'marked'."""
    found = re.search(r"^\*\*Status:\*\* (\w+)", text, re.M)
    return bool(found) and found[1] == "marked"


def load_rag_verdicts(key_rag, main_verdicts, adzuna_verdicts, text):
    """Map every RAG candidate to one verdict, wherever it was judged, checking titles."""
    by_position = {(qid, n): (title, mark) for qid, n, title, mark in parse_cards(text)}
    verdicts = {}
    for qid, entry in key_rag["queries"].items():
        verdicts[qid] = {}
        for job_id, candidate in entry["candidates"].items():
            where = candidate["judged_on"]
            if where == "main":
                verdicts[qid][job_id] = main_verdicts[qid][job_id]
            elif where == "adzuna":
                verdicts[qid][job_id] = adzuna_verdicts[qid][job_id]
            else:
                title, mark = by_position.pop((qid, candidate["rag_n"]))
                if title != (candidate["title"] or "Untitled"):
                    raise SheetError(f"RAG sheet {qid}.{candidate['rag_n']}: title mismatch")
                verdicts[qid][job_id] = read_box(mark, f"RAG sheet {qid}.{candidate['rag_n']}")
    if by_position:
        raise SheetError(f"RAG sheet cards with no key entry: {sorted(by_position)}")
    return verdicts


def duplicate_map(qid, positions, key_rag):
    """Return the symmetric job_id -> job_id duplicate map for one query (C3 plus § 8.2)."""
    rag_ids = {c.get("rag_n"): jid for jid, c in key_rag["queries"][qid]["candidates"].items()
               if c["judged_on"] == "rag"}
    resolve = {"main": positions.get(qid, {}), "rag": rag_ids}
    pairs = [(positions[qid][a], positions[qid][b]) for a, b in DUPLICATES.get(qid, [])]
    pairs += [(resolve[sa][a], resolve[sb][b]) for (sa, a), (sb, b) in RAG_DUPLICATES.get(qid, [])]
    out = {}
    for a, b in pairs:
        out[a], out[b] = b, a
    return out


def score_pool(candidates, runs, verdicts, duplicate_of):
    """Score one query in one pool: K, the per-run and mean L, failures and stability."""
    # Pure, so it can be checked on a hand-made case without any file on disk.
    first_three = candidates[:K]
    per_run, same_as_k, failed = [], 0, 0
    for run in runs:
        if run["failed"]:
            # § 8.3: a failed run is what the product shows when Groq fails -- the ranked
            # list -- so it scores as K and can only ever tie.
            picked = first_three
            failed += 1
        else:
            picked = [p["job_id"] for p in run["picks"]]
        per_run.append(precision(picked, verdicts, duplicate_of, k=K))
        same_as_k += set(picked) == set(first_three)
    return {
        "K": precision(first_three, verdicts, duplicate_of, k=K),
        "L": mean(per_run),
        "runs": per_run,
        "failed": failed,
        "same_as_k": same_as_k,
        "picked_lists": [first_three if r["failed"] else [p["job_id"] for p in r["picks"]]
                         for r in runs],
    }


def main():
    """Validate everything, then score both pools and write evaluation/rag_results.md."""
    key = json.loads((JUDGING / "key.json").read_text(encoding="utf-8"))
    key_adzuna = json.loads((JUDGING / "key_adzuna.json").read_text(encoding="utf-8"))
    key_rag = json.loads((JUDGING / "key_rag.json").read_text(encoding="utf-8"))
    text = SHEET.read_text(encoding="utf-8")
    try:
        main_verdicts, positions = load_main_verdicts(key)
        adzuna_verdicts = load_supplement_verdicts(key_adzuna, main_verdicts)
        verdicts = load_rag_verdicts(key_rag, main_verdicts, adzuna_verdicts, text)
    except SheetError as error:
        print(f"REFUSING TO SCORE -- {error}")
        return 1

    picks = {}
    for qid, entry in key_rag["queries"].items():
        path = PICKS / f"{qid}.json"
        if not path.exists():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        for pool, frozen in record["pools"].items():
            # The picks were generated against these candidates; if the ranking code has
            # changed since, the two would silently disagree. Refuse instead.
            if frozen["candidates"] != entry["pools"].get(pool):
                print(f"REFUSING TO SCORE -- {qid} {pool}: picks were made from other candidates")
                return 1
        picks[qid] = record

    if "--check" in sys.argv:
        new = sum(1 for e in key_rag["queries"].values()
                  for c in e["candidates"].values() if c["judged_on"] == "rag")
        print(f"OK: {sum(map(len, verdicts.values()))} RAG candidates mapped to a verdict "
              f"({new} from the RAG sheet). Picks present for {len(picks)} of "
              f"{len(key_rag['queries'])} queries.")
        return 0

    if not sheet_is_marked(text):
        print("REFUSING TO SCORE -- SUPPLEMENT-rag.md says it is unmarked. Mark it, then change")
        print("its Status line to `marked`. Scoring now would read every blank box as a verdict.")
        return 1
    if len(picks) != len(key_rag["queries"]):
        print("REFUSING TO SCORE -- picks are missing. Run generate_rag_picks.py first.")
        return 1

    rows, eligible_rows = {}, {}
    for pool in POOL_NAMES:
        rows[pool] = {}
        for qid, record in picks.items():
            if pool not in record["pools"]:
                continue
            frozen = record["pools"][pool]
            dup = duplicate_map(qid, positions, key_rag)
            row = score_pool(frozen["candidates"], frozen["runs"], verdicts[qid], dup)
            row["pool_size"] = len(frozen["candidates"])
            rows[pool][qid] = row
            if pool == "all":
                cands = key_rag["queries"][qid]["candidates"]
                eligible_rows[qid] = {
                    "K": eligible(frozen["candidates"][:K], cands, dup, k=K),
                    "L": mean(eligible(p, cands, dup, k=K) for p in row["picked_lists"]),
                }

    write_results(key_rag, rows, eligible_rows)
    print(f"Scored {len(rows['adzuna'])} queries Adzuna-only and {len(rows['all'])} all-sources.")
    print(f"Written to {RESULTS.relative_to(HERE.parent)}.")
    return 0


def means_block(rows, label):
    """Markdown lines for the means, the delta and the head-to-head over one set of rows."""
    answerable = {q: r for q, r in rows.items() if r["K"] or any(r["runs"])}
    lines = ["| Mean over | n | K first three | L LLM picks | L − K |", "|---|---|---|---|---|"]
    for name, subset in ((label, rows), ("queries where K or L found a relevant result", answerable)):
        k, l = mean(r["K"] for r in subset.values()), mean(r["L"] for r in subset.values())
        delta = None if k is None else l - k
        lines.append(f"| {name} | {len(subset)} | {fmt(k)} | {fmt(l)} | {fmt(delta)} |")
    c = compare(rows, "L", "K")
    lines += ["", "| Comparison | Wins | Ties | Losses | Sign test p (two-sided) | Lost on |",
              "|---|---|---|---|---|---|",
              f"| L vs K | {c['wins']} | {c['ties']} | {c['losses']} | {c['p']:.3f} | "
              f"{', '.join(c['lost_on']) or '—'} |"]
    return lines


def pool_section(pool, rows, queries):
    """Markdown lines for one pool: the per-query table, then the means over two subsets."""
    same_set = {q for q, r in rows.items() if r["pool_size"] <= K}
    out = ["| Query | | K | L (mean) | L per run | Runs = K's set | Failed |",
           "|---|---|---|---|---|---|---|"]
    for q, r in rows.items():
        mark = " †" if q in same_set else ""
        runs = " / ".join(f"{x:.2f}" for x in r["runs"])
        out.append(f"| {q}{mark} | {queries[q]} | {r['K']:.2f} | {r['L']:.2f} | {runs} | "
                   f"{r['same_as_k']}/{len(r['runs'])} | {r['failed']} |")
    out += [""] + means_block(rows, f"all {len(rows)} {POOL_NAMES[pool]} queries")
    if same_set:
        discriminating = {q: r for q, r in rows.items() if q not in same_set}
        out += ["", f"† {', '.join(sorted(same_set))}: three or fewer candidates, so K and L hold "
                    "the same set and tie by construction. Over the rest:", ""]
        out += means_block(discriminating, f"{len(discriminating)} discriminating queries")
    return out


def write_results(key_rag, rows, eligible_rows):
    """Write evaluation/rag_results.md: tables and facts only; interpretation is the report's."""
    queries = {q: e["query"] for q, e in key_rag["queries"].items()}
    all_runs = [r for pool in rows.values() for row in pool.values() for r in row["runs"]]
    failed = sum(row["failed"] for pool in rows.values() for row in pool.values())
    out = [
        "# RAG-stage results — precision@3",
        "",
        "Generated by `evaluation/score_rag.py`. Do not edit by hand; re-run the script.",
        "Protocol: `evaluation/queries.md` § 8, pre-registered before any pick was generated.",
        "",
        "- **Question:** given the five candidates the AI panel is handed, are the LLM's three picks",
        "  (L) more relevant than the first three in rank order (K)? The ranking is held fixed.",
        "- **Judge:** the developer, as for precision@5. Verdicts are reused from the earlier sheets;",
        "  candidates no sheet had shown were judged blind on `SUPPLEMENT-rag.md`.",
        "- **precision@3** = relevant ÷ 3, always 3 (§ 8.2). A duplicate vacancy counts once (C3).",
        "- **L** is the mean over 3 runs of `openai/gpt-oss-120b` (temperature 0.3, no seed).",
        f"  {failed} of {len(all_runs)} runs failed and were scored as K (§ 8.3).",
        "- **Significance:** two-sided exact sign test over non-tied queries. A high p is not",
        "  evidence of no effect.",
        "",
        "## Headline — Adzuna-only",
        "",
        "Every Adzuna listing is `local`, so the candidates are B's Adzuna-only top 5. Q04 has no",
        "Adzuna listings and is excluded as undefined.",
        "",
    ]
    out += pool_section("adzuna", rows["adzuna"], queries)
    out += [
        "",
        "## Secondary — all-sources",
        "",
        "Here `rag_candidates` lifts applicable jobs from anywhere in the ranking, so the five",
        "candidates are not B's top 5.",
        "",
    ]
    out += pool_section("all", rows["all"], queries)
    out += [
        "",
        "## Secondary — eligible@3, all sources",
        "",
        "**A known confound (§ 8.5):** the prompt asks the LLM to prefer roles the seeker can apply",
        "for, and relevance excludes eligibility. Read this beside precision@3, not instead of it.",
        f"Computed from the data: eligibility in {APPLICABLE}.",
        "",
        "| Query | K | L (mean) |",
        "|---|---|---|",
    ]
    for q, r in eligible_rows.items():
        out.append(f"| {q} | {r['K']} | {r['L']:.2f} |")
    out += ["", f"Mean eligible@3: K {fmt(mean(r['K'] for r in eligible_rows.values()))}, "
                f"L {fmt(mean(r['L'] for r in eligible_rows.values()))} (out of 3)."]
    RESULTS.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
