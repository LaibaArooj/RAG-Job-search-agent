"""Score the second judge against the first: Cohen's kappa, and whether the conclusions hold.

Run with:  venv\\Scripts\\python.exe evaluation/score_agreement.py          (writes agreement_results.md)
           venv\\Scripts\\python.exe evaluation/score_agreement.py --check  (validates, scores nothing)
           ... --sheet PATH --out PATH   score another copy of SHEET.md into another file
                                         (the identity test only; never the real results)

The protocol is evaluation/queries.md § 9, pre-registered before the sample was drawn. Judge
1's verdicts come through the same loaders the two scorers use, so no verdict is re-read in a
second way; judge 2's come from evaluation/second_judge/SHEET.md and key_judge2.json.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import score as score_module  # noqa: E402
from score import (  # noqa: E402
    DUPLICATES, JUDGING, SheetError, fmt, load_main_verdicts, load_supplement_verdicts, mean,
    parse_cards, read_box,
)
from score_rag import PICKS, duplicate_map, load_rag_verdicts, score_pool, sheet_is_marked  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
SHEET = HERE / "second_judge" / "SHEET.md"
RESULTS = HERE / "agreement_results.md"

# Landis & Koch (1977). Cited as a convention for describing kappa, not as a pass mark.
LANDIS_KOCH = ((0.0, "poor"), (0.20, "slight"), (0.40, "fair"), (0.60, "moderate"),
               (0.80, "substantial"), (1.01, "almost perfect"))


def agreement_table(pairs):
    """Return (a, b, c, d): both relevant, only judge 1, only judge 2, neither."""
    a = sum(1 for j1, j2 in pairs if j1 and j2)
    b = sum(1 for j1, j2 in pairs if j1 and not j2)
    c = sum(1 for j1, j2 in pairs if not j1 and j2)
    d = sum(1 for j1, j2 in pairs if not j1 and not j2)
    return a, b, c, d


def cohens_kappa(pairs):
    """Cohen's kappa for two judges' binary verdicts: agreement corrected for chance."""
    a, b, c, d = agreement_table(pairs)
    n = a + b + c + d
    if n == 0:
        return None
    observed = (a + d) / n
    # Chance agreement: how often two judges with these marginal rates would agree at random.
    expected = ((a + b) * (a + c) + (c + d) * (b + d)) / n ** 2
    if expected == 1:
        # Both judges gave every card the same single label, so chance explains everything.
        return 1.0 if observed == 1 else 0.0
    return (observed - expected) / (1 - expected)


def positive_agreement(pairs):
    """Agreement on the relevant cards only, 2a / (2a + b + c); None if neither judge marked any."""
    a, b, c, _ = agreement_table(pairs)
    return None if 2 * a + b + c == 0 else 2 * a / (2 * a + b + c)


def band(kappa):
    """Name the Landis-Koch band a kappa falls in."""
    if kappa is None:
        return "undefined"
    if kappa < 0:
        return "poor"
    return next(name for upper, name in LANDIS_KOCH[1:] if kappa < upper)


def load_judge2(sheet_text, key_judge2):
    """Map {qid: {job_id: verdict}} from judge 2's sheet, checking every title against the key."""
    by_position = {(qid, n): (title, mark) for qid, n, title, mark in parse_cards(sheet_text)}
    verdicts = {}
    for qid, entry in key_judge2["queries"].items():
        verdicts[qid] = {}
        for n, card in entry["cards"].items():
            title, mark = by_position.pop((qid, int(n)))
            if title != card["title"]:
                raise SheetError(f"judge 2 sheet {qid}.{n}: title mismatch")
            verdicts[qid][card["job_id"]] = read_box(mark, f"judge 2 sheet {qid}.{n}")
    if by_position:
        raise SheetError(f"judge 2 cards with no key entry: {sorted(by_position)}")
    return verdicts


def conclusions(sample, verdicts_main, verdicts_adz, verdicts_rag, key, key_adzuna, key_rag,
                positions, pairs):
    """Means over the sampled queries: P@5 all-sources and Adzuna-only (A/B/C), P@3 (K/L)."""
    sub = lambda k: {"queries": {q: e for q, e in k["queries"].items() if q in sample}}  # noqa: E731
    p5_all = score_module.score(sub(key), verdicts_main, pairs)
    p5_adz = score_module.score(sub(key_adzuna), verdicts_adz, pairs)
    out = {
        "p5_all": {s: mean(r[s] for r in p5_all.values()) for s in score_module.SYSTEMS},
        "p5_adz": {s: mean(r[s] for r in p5_adz.values()) for s in score_module.SYSTEMS},
    }
    for pool in ("adzuna", "all"):
        rows = []
        for qid in sample:
            record = json.loads((PICKS / f"{qid}.json").read_text(encoding="utf-8"))
            if pool in record["pools"]:
                frozen = record["pools"][pool]
                rows.append(score_pool(frozen["candidates"], frozen["runs"], verdicts_rag[qid],
                                       duplicate_map(qid, positions, key_rag)))
        out[f"p3_{pool}"] = {"K": mean(r["K"] for r in rows), "L": mean(r["L"] for r in rows)}
    return out


def substitute(judge1, judge2, sample):
    """Return judge 1's verdict map with judge 2's verdicts in place for the sampled queries."""
    out = {q: dict(v) for q, v in judge1.items()}
    for qid in sample:
        for job_id in out.get(qid, {}):
            out[qid][job_id] = judge2[qid][job_id]
    return out


def main():
    """Validate both judges' verdicts, then score agreement and write agreement_results.md."""
    sheet = pathlib.Path(sys.argv[sys.argv.index("--sheet") + 1]) if "--sheet" in sys.argv else SHEET
    key = json.loads((JUDGING / "key.json").read_text(encoding="utf-8"))
    key_adzuna = json.loads((JUDGING / "key_adzuna.json").read_text(encoding="utf-8"))
    key_rag = json.loads((JUDGING / "key_rag.json").read_text(encoding="utf-8"))
    key_judge2 = json.loads((JUDGING / "key_judge2.json").read_text(encoding="utf-8"))
    text = sheet.read_text(encoding="utf-8")
    try:
        main_v, positions = load_main_verdicts(key)
        adz_v = load_supplement_verdicts(key_adzuna, main_v)
        rag_v = load_rag_verdicts(key_rag, main_v, adz_v,
                                  (JUDGING / "SUPPLEMENT-rag.md").read_text(encoding="utf-8"))
        judge2 = load_judge2(text, key_judge2)
    except SheetError as error:
        print(f"REFUSING TO SCORE -- {error}")
        return 1

    sample = key_judge2["drawn"]
    # Judge 1's single verdict per (query, job), wherever it was given. The three maps agree
    # wherever they overlap, because the later ones were built by reusing the earlier.
    judge1 = {q: {**main_v.get(q, {}), **adz_v.get(q, {}), **rag_v.get(q, {})} for q in sample}
    missing = [(q, j) for q in sample for j in judge2[q] if j not in judge1[q]]
    if missing:
        print(f"REFUSING TO SCORE -- no judge 1 verdict for {missing}")
        return 1

    if "--check" in sys.argv:
        print(f"OK: {sum(map(len, judge2.values()))} judge 2 cards mapped, each with a judge 1 verdict.")
        return 0
    if not sheet_is_marked(text):
        print("REFUSING TO SCORE -- the judge 2 sheet says it is unmarked.")
        return 1

    pairs_cards = [(judge1[q][j], judge2[q][j]) for q in sample for j in judge2[q]]
    disagreements = [(q, n, c["title"], judge1[q][c["job_id"]])
                     for q in sample for n, c in key_judge2["queries"][q]["cards"].items()
                     if judge1[q][c["job_id"]] != judge2[q][c["job_id"]]]

    dup_pairs = {qid: [(positions[qid][a], positions[qid][b]) for a, b in pp]
                 for qid, pp in DUPLICATES.items()}
    j1 = conclusions(sample, main_v, adz_v, rag_v, key, key_adzuna, key_rag, positions, dup_pairs)
    j2 = conclusions(sample, substitute(main_v, judge2, sample), substitute(adz_v, judge2, sample),
                     substitute(rag_v, judge2, sample), key, key_adzuna, key_rag, positions,
                     dup_pairs)

    out = pathlib.Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else RESULTS
    write_results(sample, key_judge2, pairs_cards, disagreements, j1, j2, out)
    print(f"Scored {len(pairs_cards)} cards over {len(sample)} queries. Written to {out}.")
    return 0


def write_results(sample, key_judge2, pairs, disagreements, j1, j2, out_path):
    """Write evaluation/agreement_results.md: tables and facts only."""
    a, b, c, d = agreement_table(pairs)
    n = len(pairs)
    kappa = cohens_kappa(pairs)
    out = [
        "# Second-judge agreement",
        "",
        "Generated by `evaluation/score_agreement.py`. Do not edit by hand; re-run the script.",
        "Protocol: `evaluation/queries.md` § 9, pre-registered before the sample was drawn.",
        "",
        f"- **Sample:** {', '.join(sample)}, drawn with seed {key_judge2['draw_seed']}: {n} cards.",
        "- **Judge 1:** the committed headline verdicts, proposed by Claude (Claude Sonnet 5.5) and",
        "  adopted by the developer (`queries.md` § 10). **Judge 2:** an independent person, using no",
        "  AI, who saw only the cards and `second_judge/RULES.md`. So this measures human-versus-",
        "  AI-assisted agreement.",
        "- **Known asymmetry (§ 9.2):** judge 2 was given C1 and C2 before marking; judge 1 got",
        "  them afterwards.",
        "",
        "## Agreement",
        "",
        "| | Judge 2 relevant | Judge 2 not |",
        "|---|---|---|",
        f"| **Judge 1 relevant** | {a} | {b} |",
        f"| **Judge 1 not** | {c} | {d} |",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Raw agreement | {fmt((a + d) / n if n else None)} |",
        f"| Cohen's kappa | {fmt(kappa)} ({band(kappa)}, Landis–Koch convention) |",
        f"| Positive agreement, 2a / (2a + b + c) | {fmt(positive_agreement(pairs))} |",
        f"| Judge 1 marked relevant | {a + b} of {n} |",
        f"| Judge 2 marked relevant | {a + c} of {n} |",
        "",
        "Relevant cards are rare, so kappa can be low while raw agreement is high (§ 9.3). Read",
        "the three together.",
        "",
        "## Every disagreement",
        "",
        "| Card on judge 2's sheet | Title | Judge 1 | Judge 2 |",
        "|---|---|---|---|",
    ]
    for q, nn, title, v1 in disagreements:
        out.append(f"| {q}.{nn} | {title} | {'relevant' if v1 else 'not'} | "
                   f"{'not' if v1 else 'relevant'} |")
    if not disagreements:
        out.append("| — | none | | |")

    def row(name, m, x, y):
        return (f"| {name} | {fmt(m[x])} | {fmt(m[y])} | {fmt(m[x] - m[y]) if m[x] is not None else 'n/a'} |")

    out += [
        "",
        f"## Do the conclusions hold under judge 2? (the {len(sample)} sampled queries only)",
        "",
        "Only the direction of each difference is compared. Six queries cannot show significance.",
        "",
        "| Measure over the sample, X vs Y | X | Y | X − Y |",
        "|---|---|---|---|",
    ]
    for label, part, x, y in (("precision@5 Adzuna-only, B vs A", "p5_adz", "B", "A"),
                              ("precision@5 all-sources, B vs A", "p5_all", "B", "A"),
                              ("precision@3 Adzuna-only, L vs K", "p3_adzuna", "L", "K"),
                              ("precision@3 all-sources, L vs K", "p3_all", "L", "K")):
        out.append(row(f"{label}, judge 1", j1[part], x, y))
        out.append(row(f"{label}, judge 2", j2[part], x, y))
    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
