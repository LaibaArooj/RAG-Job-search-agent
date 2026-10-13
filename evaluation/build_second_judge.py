"""Build the second judge's blind sheet: 6 randomly drawn queries, every card judged for them.

Run with:  venv\\Scripts\\python.exe evaluation/build_second_judge.py

The protocol is evaluation/queries.md § 9, committed before this script first ran. Writes

    evaluation/second_judge/RULES.md    standalone rules -- send this folder to the judge
    evaluation/second_judge/SHEET.md    the cards to mark
    evaluation/judging/key_judge2.json  sheet position -> job_id, kept OUT of that folder

and prints counts only. Refuses to overwrite.

WHY A SEPARATE RULES SHEET
--------------------------
queries.md cannot be given to judge 2. § 7 and § 8.6 name specific cards and say how judge 1
ruled on them, which would make the second judgement a copy of the first. RULES.md states
the same rules without naming a single card, and without mentioning systems, rankers, the LLM
or any result.
"""

import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_export import readable  # noqa: E402
from core.agent import JobSearchAgent  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
JUDGING = HERE / "judging"
OUT = HERE / "second_judge"
KEY = JUDGING / "key_judge2.json"

# queries.md § 9.1 -- fixed and committed before this script first ran.
DRAW_SEED = 20261011
DRAW_SIZE = 6
QUERY_IDS = [f"Q{n:02d}" for n in range(1, 21)]

# Shuffles cards within each query, so position carries no signal. Independent of the draw.
SHUFFLE_SEED = 20261012

RULES = """# Judging rules

Thank you for doing this. You are the second, independent judge for a final-year project
on job search. Budget about an hour, and do it in one sitting if you can.

## What you are judging

Each section of `SHEET.md` starts with a **search** someone typed, followed by job cards. For
each card, decide whether it is **relevant** to that search. That is all. You are not told
where the cards came from or how they were chosen, on purpose.

## The rule

A card is **relevant** only if **all five** of these hold:

| | |
|---|---|
| **R1** | It is a real, specific job advert, not a category page or a "register your CV with us" placeholder. |
| **R2** | The **kind of role** is one a person making this search would plausibly click. |
| **R3** | If the search states a **seniority** ("junior", "entry level"), the card does not contradict it. A Senior, Lead or Principal title contradicts "entry level". |
| **R4** | If the search states a **work type** (remote, part-time, freelance), the card does not contradict it. |
| **R5** | If the search **excludes** something ("not sales", "isn't recruitment", "not journalism", "isn't web development", "doesn't need a portfolio"), the card is not in that excluded set. |

### How to read the rules

- **Silence is not a contradiction.** A card that doesn't mention remote working does not fail
  R4. Only a card that states something incompatible fails.
- **Qualifications count under R3.** If the search says "no degree" or "no prior experience",
  a card that *explicitly* requires a degree or experience fails. A card that says nothing
  passes.
- **"Doesn't need a portfolio"**: a card fails only if it *states* that a portfolio is
  required. Don't apply what you think the industry usually expects.
- **Whether you personally could apply** (your country, visa, location) is **not** part of
  relevance. Judge the role against the search.
- **Judge the card only.** Do not look the job up online. A live advert may have changed, and
  every other judgement was made on the card alone.
- **If a rule is genuinely ambiguous for a card, mark it not relevant**, and write one line
  saying why under it. A recorded doubt is useful; a silently resolved one is not.

## How to mark

- Change `- [ ] relevant` to `- [x] relevant` for each relevant card. Leave the others alone.
- Don't reorder, add or delete cards, because the scorer matches on position.
- When every card is done, change the `**Status:** unmarked` line at the top of `SHEET.md` to
  `**Status:** marked`, and send the file back.

**Judge entirely by yourself.** Please don't use ChatGPT, Claude or any other AI tool, and
don't ask anyone else. The point is to record one person's own judgement.

Please don't discuss the cards with the project's author until you have sent the sheet back.
"""


def judged_job_ids(qid, keys):
    """Every job_id that has a verdict for this query, on any sheet, in a stable order."""
    seen = []
    for key in keys:
        for job_id in key["queries"].get(qid, {}).get("candidates", {}):
            if job_id not in seen:
                seen.append(job_id)
    return seen


def main():
    """Draw the sample, write the rules and the blind sheet, and the key beside the others."""
    if OUT.exists() or KEY.exists():
        print("The second-judge sheet already exists. It is drawn once, from a fixed seed;")
        print("delete it deliberately to rebuild, so a marked sheet is never replaced.")
        return 1

    keys = [json.loads((JUDGING / name).read_text(encoding="utf-8"))
            for name in ("key.json", "key_adzuna.json", "key_rag.json")]
    drawn = random.Random(DRAW_SEED).sample(QUERY_IDS, DRAW_SIZE)
    rng = random.Random(SHUFFLE_SEED)

    key = {"draw_seed": DRAW_SEED, "drawn": drawn, "queries": {}}
    sections = []
    for qid in drawn:
        fixture = json.loads((FIXTURES / f"{qid}.json").read_text(encoding="utf-8"))
        # The fixture holds raw fetch rows, duplicates included; the first occurrence is the
        # one every earlier sheet showed, because they all deduplicated the same way.
        by_id = {j["job_id"]: j for j in reversed(JobSearchAgent.deduplicate(
            [dict(j) for j in fixture["jobs"]]))}
        job_ids = judged_job_ids(qid, keys)
        rng.shuffle(job_ids)

        key["queries"][qid] = {"query": fixture["query"], "cards": {}}
        sections += [f"## {qid} — search: `{fixture['query']}`", ""]
        for n, job_id in enumerate(job_ids, 1):
            job = by_id[job_id]
            key["queries"][qid]["cards"][str(n)] = {"job_id": job_id,
                                                     "title": job.get("title") or "Untitled"}
            blurb = readable(job.get("description"))[:240]
            sections += [
                f"### {qid}.{n}. {job.get('title') or 'Untitled'}",
                "",
                f"- **Company:** {job.get('company') or 'Unknown'}",
                f"- **Location:** {job.get('location') or 'Unknown'}",
                f"- {blurb or '_no description supplied_'}",
                "",
                "- [ ] relevant",
                "",
            ]

    total = sum(len(q["cards"]) for q in key["queries"].values())
    header = [
        "# Job relevance — judging sheet",
        "",
        "**Status:** unmarked",
        "",
        f"{len(drawn)} searches, {total} cards. Read `RULES.md` first and keep it open.",
        "",
        "---",
        "",
    ]
    OUT.mkdir()
    (OUT / "RULES.md").write_text(RULES, encoding="utf-8")
    (OUT / "SHEET.md").write_text("\n".join(header + sections), encoding="utf-8")
    KEY.write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"Drew {len(drawn)} queries, {total} cards. Sheet and rules in evaluation/second_judge/.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
