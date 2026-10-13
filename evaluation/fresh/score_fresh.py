"""Score the fresh experiment: precision@3 for K, L5 and L10, with L10 vs L5 as the primary.

Run with:  venv\\Scripts\\python.exe evaluation/fresh/score_fresh.py          (writes fresh/results.md)
           venv\\Scripts\\python.exe evaluation/fresh/score_fresh.py --check  (validates, scores nothing)
           ... --sheet PATH --out PATH   score another copy (the identity test only)

The protocol is evaluation/fresh/queries.md. precision, eligible, compare and the sign test come
from evaluation/score.py, so the rules are applied by the same code as before.
"""

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from score import SheetError, compare, eligible, fmt, mean, precision, read_box  # noqa: E402
from score_rag import sheet_is_marked  # noqa: E402

PICKS = HERE / "picks"
JUDGING = HERE / "judging"
RESULTS = HERE / "results.md"
K = 3
SYSTEMS = ("K", "L5", "L10")

# F6: pairs of sheet positions within one query that are the SAME vacancy, declared before
# this script first runs. {"N01": [(2, 5)]} means N01.2 and N01.5.
DUPLICATES = {}

CARD = re.compile(
    r"^### (N\d\d)\.(\d+)\. (.*)\n\n- \*\*Company:\*\* .*\n- \*\*Location:\*\* .*\n"
    r"- .*\n\n- \[(.?)\] relevant",
    re.M,
)


def load_verdicts(text, key):
    """Map {qid: {job_id: verdict}} from the sheet, checking every title against the key."""
    by_position = {(m[1], int(m[2])): (m[3], m[4]) for m in CARD.finditer(text)}
    verdicts = {}
    for qid, entry in key["queries"].items():
        verdicts[qid] = {}
        for n, card in entry["cards"].items():
            title, mark = by_position.pop((qid, int(n)))
            if title != card["title"]:
                raise SheetError(f"{qid}.{n}: sheet says {title!r}, key says {card['title']!r}")
            verdicts[qid][card["job_id"]] = read_box(mark, f"{qid}.{n}")
    if by_position:
        raise SheetError(f"cards with no key entry: {sorted(by_position)}")
    return verdicts


def run_list(run, first_three):
    """The list a run shows the user, per F3: K on failure, nothing on a decline, else the picks."""
    if run["state"] == "failed":
        return first_three
    return [p["job_id"] for p in run["picks"]]


def score_query(record, verdicts, duplicate_of, cards):
    """Return {system: precision@3} plus eligible@3, run states and stability for one query."""
    first_three = record["arms"]["L5"]["candidates"][:K]
    row = {"K": precision(first_three, verdicts, duplicate_of, k=K),
           "eligible": {"K": eligible(first_three, cards, duplicate_of, k=K)}, "states": {},
           "stable": {}}
    for arm in ("L5", "L10"):
        lists = [run_list(r, first_three) for r in record["arms"][arm]["runs"]]
        row[arm] = mean(precision(lst, verdicts, duplicate_of, k=K) for lst in lists)
        row["eligible"][arm] = mean(eligible(lst, cards, duplicate_of, k=K) for lst in lists)
        row["states"][arm] = [r["state"] for r in record["arms"][arm]["runs"]]
        row["stable"][arm] = len({frozenset(lst) for lst in lists}) == 1
    return row


def main():
    """Validate, then score every fresh query and write fresh/results.md."""
    sheet = pathlib.Path(sys.argv[sys.argv.index("--sheet") + 1]) if "--sheet" in sys.argv \
        else JUDGING / "SHEET.md"
    out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else RESULTS
    key = json.loads((JUDGING / "key.json").read_text(encoding="utf-8"))
    text = sheet.read_text(encoding="utf-8")
    try:
        verdicts = load_verdicts(text, key)
    except SheetError as error:
        print(f"REFUSING TO SCORE -- {error}")
        return 1

    records = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(PICKS.glob("N*.json"))}
    if set(records) != set(key["queries"]):
        print("REFUSING TO SCORE -- the picks and the key cover different queries.")
        return 1
    if "--check" in sys.argv:
        print(f"OK: {sum(map(len, verdicts.values()))} cards mapped over {len(verdicts)} queries.")
        return 0
    if not sheet_is_marked(text):
        print("REFUSING TO SCORE -- the sheet says it is unmarked.")
        return 1

    rows = {}
    for qid, record in records.items():
        cards_by_n = key["queries"][qid]["cards"]
        duplicate_of = {}
        for a, b in DUPLICATES.get(qid, []):
            ja, jb = cards_by_n[str(a)]["job_id"], cards_by_n[str(b)]["job_id"]
            duplicate_of[ja], duplicate_of[jb] = jb, ja
        cards = {c["job_id"]: {"eligibility": c["eligibility"]} for c in cards_by_n.values()}
        rows[qid] = score_query(record, verdicts[qid], duplicate_of, cards)

    write_results(key, rows, out)
    print(f"Scored {len(rows)} fresh queries. Written to {out}.")
    return 0


def write_results(key, rows, out_path):
    """Write the results file: tables and facts only."""
    lines = [
        "# Fresh-query experiment — does the LLM pick better from 10 candidates than from 5?",
        "",
        "Generated by `evaluation/fresh/score_fresh.py`. Do not edit by hand; re-run the script.",
        "Protocol: `evaluation/fresh/queries.md`, pre-registered before any pool was fetched.",
        "",
        "- **K** = first three of the five candidates. **L5** / **L10** = the LLM's picks from 5 / 10",
        "  candidates, mean of 3 runs. precision@3, always ÷ 3. A decline scores 0; a failure scores",
        "  as K (F3). All-sources pool only (F2). Single judge: the developer, by hand, without AI assistance.",
        "",
        "| Query | | K | L5 | L10 | L5 runs | L10 runs |",
        "|---|---|---|---|---|---|---|",
    ]
    for q, r in rows.items():
        lines.append(f"| {q} | {key['queries'][q]['query']} | {r['K']:.2f} | {r['L5']:.2f} | "
                     f"{r['L10']:.2f} | {', '.join(r['states']['L5'])} | "
                     f"{', '.join(r['states']['L10'])} |")
    m = {s: mean(r[s] for r in rows.values()) for s in SYSTEMS}
    lines += ["", "| Mean over 15 queries | K | L5 | L10 |", "|---|---|---|---|",
              f"| precision@3 | {fmt(m['K'])} | {fmt(m['L5'])} | {fmt(m['L10'])} |"]
    e = {s: mean(r["eligible"][s] for r in rows.values()) for s in SYSTEMS}
    lines.append(f"| eligible@3 (out of 3) | {fmt(e['K'])} | {fmt(e['L5'])} | {fmt(e['L10'])} |")

    lines += ["", "| Comparison | Mean difference | Wins | Ties | Losses | Sign test p | Lost on |",
              "|---|---|---|---|---|---|---|"]
    for label, better, worse in (("**L10 vs L5 (primary)**", "L10", "L5"),
                                 ("L5 vs K", "L5", "K"), ("L10 vs K", "L10", "K")):
        c = compare(rows, better, worse)
        lines.append(f"| {label} | {fmt(m[better] - m[worse])} | {c['wins']} | {c['ties']} | "
                     f"{c['losses']} | {c['p']:.3f} | {', '.join(c['lost_on']) or '—'} |")

    states = {arm: {s: sum(r["states"][arm].count(s) for r in rows.values())
                    for s in ("picked", "declined", "failed")} for arm in ("L5", "L10")}
    stable = {arm: sum(r["stable"][arm] for r in rows.values()) for arm in ("L5", "L10")}
    lines += ["", "| Arm | Runs picked | Declined | Failed | Queries where all 3 runs agreed |",
              "|---|---|---|---|---|"]
    for arm in ("L5", "L10"):
        lines.append(f"| {arm} | {states[arm]['picked']} | {states[arm]['declined']} | "
                     f"{states[arm]['failed']} | {stable[arm]} of {len(rows)} |")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
