"""Unblind the marked sheets and compute precision@5 and eligible@5 for systems A, B and C.

Run with:  venv\\Scripts\\python.exe evaluation/score.py

Step 5 of the protocol in docs/EVALUATION.md. Reads, and never writes to:

    evaluation/judging/QNN.md                the marked main sheets (all-sources top 5s)
    evaluation/judging/SUPPLEMENT-adzuna.md  the marked supplement (Adzuna-only top 5s)
    evaluation/judging/key.json              all-sources ranks, from build_export.py
    evaluation/judging/key_adzuna.json       Adzuna-only ranks, from build_supplement.py

and writes evaluation/results.md. Nothing is re-ranked here: the ranks are the ones recorded
when the sheets were built, so the scores are over exactly the lists that were judged.

Every rule applied below is pre-registered in evaluation/queries.md § 3 or clarified, blind,
in § 7. The scorer adds no judgement of its own -- where a decision was needed, it is a named
constant with the clarification it comes from.
"""

import json
import math
import pathlib
import random
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
JUDGING = HERE / "judging"
RESULTS = HERE / "results.md"

TOP_N = 5
SYSTEMS = ("A", "B", "C")
NAMES = {"A": "Baseline", "B": "System", "C": "Ablation"}

# Must equal build_export.SHUFFLE_SEED. The sheets do not carry job ids, so the scorer maps a
# sheet position back to a job by replaying the exact shuffle that produced the sheet. Every
# replayed position is then checked against the sheet's title, so a wrong seed cannot pass.
EXPORT_SHUFFLE_SEED = 20260926

# C3: pairs of main-sheet positions that are the SAME vacancy. Not judged by the reader --
# a blind judge cannot know which listings share a top 5 -- so R1's duplicate clause is
# applied here: when both copies fall in one system's top 5, only the higher-ranked counts.
DUPLICATES = {
    # Same employer or a sister company.
    "Q05": [(1, 4)],
    "Q08": [(4, 5)],
    "Q10": [(1, 4)],
    # The same vacancy advertised through an agency: same title, town, salary and role details.
    "Q01": [(3, 4)],
    "Q11": [(5, 7)],
    "Q15": [(1, 5)],
}

# C2: the reading of Q20 the judge first gave, before the ruling. Scored as a sensitivity
# check only; the headline uses the corrected sheet.
Q20_ORIGINAL_READING = ("Q20", 1, False)

# How production decides the seeker can apply -- JobSearchAgent's AI-panel filter. Reused
# rather than re-invented, so eligible@5 means what the app means by "can apply".
APPLICABLE = ("open", "unknown")

CARD = re.compile(
    r"^### (?:(Q\d\d)\.)?(\d+)\. (.*)\n\n- \*\*Company:\*\* .*\n- \*\*Location:\*\* .*\n"
    r"- .*\n\n- \[(.?)\] relevant",
    re.M,
)


class SheetError(Exception):
    """Raised when a sheet and its key disagree, so no score is produced from bad data."""


def read_box(mark, where):
    """Turn the character inside a checkbox into a verdict, refusing anything unexpected."""
    if mark in ("x", "X"):
        return True
    if mark in ("", " "):
        return False
    raise SheetError(f"{where}: unreadable checkbox [{mark}]")


def parse_cards(text):
    """Return [(query_id or None, position, title, relevant_mark)] for every card in a sheet."""
    return [(m[1], int(m[2]), m[3], m[4]) for m in CARD.finditer(text)]


def load_main_verdicts(key):
    """Map every main-sheet candidate to its verdict, checking each position against the key."""
    rng = random.Random(EXPORT_SHUFFLE_SEED)
    verdicts, positions = {}, {}
    # key.json lists queries in the order build_export.py shuffled them, and each query's
    # candidates in the order they were inserted before the shuffle. Replaying rng.shuffle
    # over those lists, in that order, reproduces every sheet exactly.
    for qid, entry in key["queries"].items():
        job_ids = list(entry["candidates"])
        rng.shuffle(job_ids)

        cards = parse_cards((JUDGING / f"{qid}.md").read_text(encoding="utf-8"))
        if len(cards) != len(job_ids):
            raise SheetError(f"{qid}: {len(cards)} cards on the sheet, {len(job_ids)} in the key")

        verdicts[qid], positions[qid] = {}, {}
        for (_, n, title, mark), job_id in zip(cards, job_ids):
            expected = entry["candidates"][job_id]["title"] or "Untitled"
            if title != expected:
                raise SheetError(f"{qid} #{n}: sheet says {title!r}, key says {expected!r}")
            verdicts[qid][job_id] = read_box(mark, f"{qid} #{n}")
            positions[qid][n] = job_id
    return verdicts, positions


def load_supplement_verdicts(key_adzuna, main_verdicts):
    """Add the supplement's verdicts, so every Adzuna-only top-5 candidate has exactly one."""
    cards = parse_cards((JUDGING / "SUPPLEMENT-adzuna.md").read_text(encoding="utf-8"))
    by_position = {(qid, n): (title, mark) for qid, n, title, mark in cards}
    verdicts = {}
    for qid, entry in key_adzuna["queries"].items():
        verdicts[qid] = {}
        for job_id, candidate in entry["candidates"].items():
            if candidate["judged_on"] == "main":
                verdicts[qid][job_id] = main_verdicts[qid][job_id]
                continue
            title, mark = by_position.pop((qid, candidate["supplement_n"]))
            if title != (candidate["title"] or "Untitled"):
                raise SheetError(f"supplement {qid}.{candidate['supplement_n']}: title mismatch")
            verdicts[qid][job_id] = read_box(mark, f"supplement {qid}.{candidate['supplement_n']}")
    if by_position:
        raise SheetError(f"supplement cards with no key entry: {sorted(by_position)}")
    return verdicts


def top_lists(entry):
    """Rebuild each system's top 5 from the recorded ranks, checking they are complete."""
    lists = {}
    for system in SYSTEMS:
        ranked = sorted((c["ranks"][system], jid) for jid, c in entry["candidates"].items()
                        if system in c["ranks"])
        if [rank for rank, _ in ranked] != list(range(1, len(ranked) + 1)):
            raise SheetError(f"{entry['query']!r}: {system}'s ranks have a gap")
        lists[system] = [jid for _, jid in ranked]
    return lists


def precision(top, verdicts, duplicate_of):
    """precision@5: relevant listings in the top 5, over 5, counting a duplicate only once (C3, C5)."""
    seen, hits = set(), 0
    for job_id in top[:TOP_N]:
        if verdicts[job_id] and duplicate_of.get(job_id) not in seen:
            hits += 1
        seen.add(job_id)
    return hits / TOP_N


def eligible(top, candidates, duplicate_of):
    """eligible@5: distinct vacancies in the top 5 the seeker could apply for, from data."""
    seen, count = set(), 0
    for job_id in top[:TOP_N]:
        if candidates[job_id]["eligibility"] in APPLICABLE and duplicate_of.get(job_id) not in seen:
            count += 1
        seen.add(job_id)
    return count


def sign_test(wins, losses):
    """Two-sided exact sign test over the non-tied queries; ties carry no direction."""
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(rows, better, worse):
    """Count the queries where `better` beat, tied or lost to `worse`, and name the losses."""
    wins = [q for q, r in rows.items() if r[better] > r[worse]]
    losses = [q for q, r in rows.items() if r[better] < r[worse]]
    ties = len(rows) - len(wins) - len(losses)
    return {"wins": len(wins), "ties": ties, "losses": len(losses), "lost_on": losses,
            "p": sign_test(len(wins), len(losses))}


def mean(values):
    """Arithmetic mean, or None for an empty set, so an undefined mean is never shown as 0."""
    values = list(values)
    return sum(values) / len(values) if values else None


def score(key, verdicts, duplicate_pairs):
    """Return {qid: {system: p@5}} for one key and its verdicts."""
    rows = {}
    for qid, entry in key["queries"].items():
        duplicate_of = {}
        for a, b in duplicate_pairs.get(qid, []):
            duplicate_of[a], duplicate_of[b] = b, a
        lists = top_lists(entry)
        rows[qid] = {s: precision(lists[s], verdicts[qid], duplicate_of) for s in SYSTEMS}
    return rows


def main():
    """Unblind, score both views, and write evaluation/results.md."""
    key = json.loads((JUDGING / "key.json").read_text(encoding="utf-8"))
    key_adzuna = json.loads((JUDGING / "key_adzuna.json").read_text(encoding="utf-8"))
    try:
        main_verdicts, positions = load_main_verdicts(key)
        adzuna_verdicts = load_supplement_verdicts(key_adzuna, main_verdicts)
    except SheetError as error:
        print(f"REFUSING TO SCORE -- {error}")
        return 1

    if "--check" in sys.argv:
        # Validates every sheet against its key and prints nothing about any system, so it
        # can be run before a ruling without unblinding anyone.
        total = sum(map(len, main_verdicts.values()))
        supplement = sum(1 for e in key_adzuna["queries"].values()
                         for c in e["candidates"].values() if c["judged_on"] == "supplement")
        print(f"OK: {total} main-sheet and {supplement} supplement verdicts mapped to job ids.")
        return 0

    # C3 pairs are declared by sheet position; the scorer works in job ids.
    pairs = {qid: [(positions[qid][a], positions[qid][b]) for a, b in pp]
             for qid, pp in DUPLICATES.items()}

    all_rows = score(key, main_verdicts, pairs)
    adz_rows = score(key_adzuna, adzuna_verdicts, pairs)

    # How many scores the C3 rule actually moved, so it is visible rather than silent.
    duplicate_effect = [
        f"{view} {q} {s}"
        for view, k, v, rows in (("all-sources", key, main_verdicts, all_rows),
                                 ("Adzuna-only", key_adzuna, adzuna_verdicts, adz_rows))
        for q, r in score(k, v, {}).items() for s in SYSTEMS if r[s] != rows[q][s]
    ]

    # Adzuna-only queries where every system ranks the same set, so they must tie (C6).
    same_set = {q for q, e in key_adzuna["queries"].items() if e["adzuna_pool_unique"] <= TOP_N}
    no_adzuna = sorted(set(key["queries"]) - set(key_adzuna["queries"]))

    eligible_rows = {}
    for qid, entry in key["queries"].items():
        duplicate_of = {}
        for a, b in pairs.get(qid, []):
            duplicate_of[a], duplicate_of[b] = b, a
        lists = top_lists(entry)
        eligible_rows[qid] = {s: eligible(lists[s], entry["candidates"], duplicate_of)
                              for s in SYSTEMS}

    # C2 sensitivity: the same scores with the judge's first reading of Q20 restored.
    qid, n, verdict = Q20_ORIGINAL_READING
    original = {q: dict(v) for q, v in main_verdicts.items()}
    original[qid][positions[qid][n]] = verdict
    q20_original = score(key, original, pairs)[qid]
    q20_in_adzuna = positions[qid][n] in key_adzuna["queries"].get(qid, {}).get("candidates", {})

    write_results(key, all_rows, adz_rows, eligible_rows, same_set, no_adzuna, q20_original,
                  q20_in_adzuna, duplicate_effect)
    print(f"Scored {len(all_rows)} queries all-sources and {len(adz_rows)} Adzuna-only.")
    print(f"Written to {RESULTS.relative_to(HERE.parent)}.")
    return 0


def fmt(value, places=2):
    """Format a score, showing an undefined mean as n/a rather than 0."""
    if value is None:
        return "n/a"
    # Rounded first, and + 0.0 turns -0.0 into 0.0: gains and losses that cancel exactly
    # leave float noise like -1e-17, which would otherwise print as a misleading "-0.00".
    return f"{round(value, places) + 0.0:.{places}f}"


def means_block(rows, label):
    """Markdown lines for the means, deltas and head-to-head counts over one set of rows."""
    answerable = {q: r for q, r in rows.items() if any(r.values())}
    lines = [
        f"| Mean over | n | A {NAMES['A']} | B {NAMES['B']} | C {NAMES['C']} | B − A | C − A | B − C |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for name, subset in ((label, rows), ("queries where any system found a relevant result",
                                         answerable)):
        m = {s: mean(r[s] for r in subset.values()) for s in SYSTEMS}
        delta = (lambda x, y: None if m[x] is None else m[x] - m[y])
        lines.append(
            f"| {name} | {len(subset)} | {fmt(m['A'])} | {fmt(m['B'])} | {fmt(m['C'])} | "
            f"{fmt(delta('B', 'A'))} | {fmt(delta('C', 'A'))} | {fmt(delta('B', 'C'))} |"
        )
    lines += ["", "| Comparison | Wins | Ties | Losses | Sign test p (two-sided) | Lost on |",
              "|---|---|---|---|---|---|"]
    for better, worse in (("B", "A"), ("C", "A"), ("B", "C")):
        c = compare(rows, better, worse)
        lines.append(f"| {better} vs {worse} | {c['wins']} | {c['ties']} | {c['losses']} | "
                     f"{c['p']:.3f} | {', '.join(c['lost_on']) or '—'} |")
    return lines


def write_results(key, all_rows, adz_rows, eligible_rows, same_set, no_adzuna, q20_original,
                  q20_in_adzuna, duplicate_effect):
    """Write evaluation/results.md: tables and facts only; interpretation belongs in the report."""
    queries = {q: e["query"] for q, e in key["queries"].items()}
    discriminating = {q: r for q, r in adz_rows.items() if q not in same_set}

    out = [
        "# Evaluation results — precision@5",
        "",
        "Generated by `evaluation/score.py` from the marked sheets and the unblinding keys. Do not",
        "edit by hand; re-run the script. Rules: `evaluation/queries.md` § 3, clarified blind in § 7.",
        "",
        f"- **Judge:** the developer — a single judge, not blind to the project (see `docs/EVALUATION.md`).",
        f"- **Profile for B:** synthetic `category_scores` {key['scores']}, "
        f"`CATEGORY_BOOST` = {key['boost']}. C is the same with the boost at 0.",
        "- **precision@5** = relevant listings in the top 5 ÷ 5, always 5 (C5). A duplicate",
        f"  vacancy counts once per list (C3; {sum(map(len, DUPLICATES.values()))} declared pairs).",
        f"  It changed {len(duplicate_effect)} of the per-query scores below"
        + (f": {', '.join(duplicate_effect)}." if duplicate_effect else "."),
        "- **Significance:** two-sided exact sign test over non-tied queries. With this few",
        "  queries it can detect only a large, consistent effect; a high p is not evidence of no effect.",
        "",
        "## Headline — Adzuna-only precision@5",
        "",
        "Each system ranks only the Adzuna listings in the frozen pool — the one source doing a",
        "genuine keyword search, so the only honest keyword-vs-semantic contrast.",
        f"{', '.join(no_adzuna)} has no Adzuna listings and is excluded as undefined, not scored 0.",
        f"On {', '.join(sorted(same_set))} the Adzuna pool has five or fewer listings, so all three",
        "systems return the same set and tie by construction (marked †).",
        "",
        "| Query | | A | B | C |",
        "|---|---|---|---|---|",
    ]
    for q, r in adz_rows.items():
        mark = " †" if q in same_set else ""
        out.append(f"| {q}{mark} | {queries[q]} | {r['A']:.1f} | {r['B']:.1f} | {r['C']:.1f} |")
    out += [""] + means_block(adz_rows, f"all {len(adz_rows)} Adzuna queries")
    out += ["", f"Over only the {len(discriminating)} queries that can discriminate (no †):", ""]
    out += means_block(discriminating, f"{len(discriminating)} discriminating queries")

    out += [
        "",
        "## Secondary — all-sources precision@5",
        "",
        "**Caveat, to be stated beside these numbers:** only Adzuna's order is a keyword ranking.",
        "Remotive's order is query-independent and filtered locally; Jobicy's `geo=anywhere` order",
        "is not a keyword ranking either. A is therefore not a pure keyword baseline here.",
        "",
        "| Query | | A | B | C |",
        "|---|---|---|---|---|",
    ]
    for q, r in all_rows.items():
        out.append(f"| {q} | {queries[q]} | {r['A']:.1f} | {r['B']:.1f} | {r['C']:.1f} |")
    out += [""] + means_block(all_rows, f"all {len(all_rows)} queries")

    zero = [q for q, r in all_rows.items() if not any(r.values())]
    out += [
        "",
        f"Queries with no relevant result in any system's top 5: {', '.join(zero) or 'none'}. They",
        "stay in the first mean as 0 (C4). This means none was found among the judged",
        "candidates — the union of the three top 5s — not that the pool holds none.",
        "",
        "## Sensitivity — Q20 under the judge's first reading (C2)",
        "",
        "| Q20 | A | B | C |",
        "|---|---|---|---|",
        f"| Corrected (headline) | {all_rows['Q20']['A']:.1f} | {all_rows['Q20']['B']:.1f} | "
        f"{all_rows['Q20']['C']:.1f} |",
        f"| First reading | {q20_original['A']:.1f} | {q20_original['B']:.1f} | "
        f"{q20_original['C']:.1f} |",
    ]
    shifted = {q: dict(r) for q, r in all_rows.items()}
    shifted["Q20"] = q20_original
    m = {s: mean(r[s] for r in shifted.values()) for s in SYSTEMS}
    out += ["", f"All-sources means under the first reading: A {m['A']:.2f}, B {m['B']:.2f}, "
                f"C {m['C']:.2f}."]
    out.append("The Superside listing is in an Adzuna-only top 5, so the headline is affected too"
               " — re-score it by hand." if q20_in_adzuna else
               "The Superside listing is in no Adzuna-only top 5, so the headline is unaffected.")

    out += [
        "",
        "## Secondary — eligible@5, all sources",
        "",
        "How many of each top 5 the seeker could apply for, computed from the data, not judged:",
        f"eligibility in {APPLICABLE}, the same test the app uses for the AI panel. Not reported",
        "for Adzuna-only, where every listing is `local` and the answer is 0 by construction.",
        "",
        "| Query | A | B | C |",
        "|---|---|---|---|",
    ]
    for q, r in eligible_rows.items():
        out.append(f"| {q} | {r['A']} | {r['B']} | {r['C']} |")
    m = {s: mean(r[s] for r in eligible_rows.values()) for s in SYSTEMS}
    out += ["", f"Mean eligible@5: A {m['A']:.2f}, B {m['B']:.2f}, C {m['C']:.2f} (out of 5)."]

    RESULTS.write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
