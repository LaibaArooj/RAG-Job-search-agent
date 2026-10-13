# Judging provenance: who judged what, how, and how far to trust it

**Written by:** Claude (Anthropic), in a claude.ai chat inside the Project "RAG-Based Intelligent Job Search Agent"
**Date:** 2026-10-13
**Purpose:** An honest record of what I actually did when judging relevance for the RAG-stage and Adzuna-only supplement sheets, what I knew, what I did not know, and which verdicts are solid versus judgment calls. Nothing here is rounded up.

---

## 0. Bottom line

- **Not a bluff, but not rigorous in the way "judged blind by Claude" suggests.** Every verdict was made by applying the written rules R1–R5 to the text visible on each card. I did not invent evidence. But it was a single-rater, single-pass LLM judgment on truncated snippets, with only two external lookups.
- **Most verdicts are clear-cut.** About 41 of the 55 cards fail R2 (the role type is plainly wrong for the query) or fail R3/R5 on an explicit title or text. These are low-risk.
- **About 14 verdicts rest on a judgment call**, listed in section 7. Those are the ones to have a human check.
- **The statement "all the judging was done by Claude" is too broad.** The only sheets I judged are the two supplements (42 + 13 = 55 cards). I have no record in this conversation of judging the 20 main blind sheets. If those were judged by Claude in another session or by Claude Code, I cannot vouch for them.
- **I was not blind to everything.** I never saw `key.json`, `key_adzuna.json`, or which system ranked which job. I did know this was her FYP evaluation, and I was told to be strict ("be cruel", "precise"), which biases toward "not relevant".

---

## 1. Scope: exactly what I judged

| Sheet | Cards | Ticked `[x]` | Which |
|---|---|---|---|
| RAG-stage supplement (`evaluation/queries.md` § 8) | 42 | 3 | Q08.1, Q11.2, Q17.3 |
| Adzuna-only supplement (§ 7, C6) | 13 | 2 | Q02.1, Q19.1 |
| Main blind sheets (20 queries) | 0 | n/a | **Not judged by me, as far as this conversation shows** |

Notes on the table:
- On the Adzuna sheet, ticks and notes already existed when she pasted it (Q02.1, Q10.1, Q19.1). I do not know who made them. I re-judged all 13 cards from scratch and changed one (Q10.1, from relevant to not relevant).
- The Adzuna sheet had no `Status:` line, so I did not set one. On the RAG sheet I set `Status: marked` in the file I produced, after both external checks were done.
- Q10.1's original note refers to "Q10 #3 on the main sheet", judged relevant by someone else. I did not see that sheet.

---

## 2. How I knew about the project

I had no access to the repository, the code, `key.json`, `queries.md` as a file, or the scorer. What I knew came from four sources:

1. **A stored project note** (`areas/evaluation.md`, written in earlier chat sessions) that I read at the start. It described the precision@5 protocol, 20 frozen queries, A/B/C systems, blind judging, and the rules R1–R5. My first pass applied R1–R5 as that note stated them. The note did not include the clarifications C1–C4, and I said so at the time. I cannot re-display that file's exact text now, so I cannot re-verify my reading of it.
2. **What she pasted into this conversation:** both judging sheets, the full text of R1–R5 and C1–C4, and later a Claude Code log of the scoring run (commit ids, tables, results).
3. **Two sets of web searches** I ran myself (section 6).
4. **General knowledge** of what job titles typically mean (e.g. that a sales engineer is a sales role). This is background knowledge, not project knowledge, and it is the main place my R2 judgments can be wrong.

I did **not** know: how the pipeline scraped postings, which exact posting version the sheet captured, how the LLM picks were produced, or how the scorer defines K. I **assumed** K is the first-three baseline score for a query (so a failed run equals a tie). That is my reading of her log, not something I verified.

---

## 3. What each verdict was based on

- **Card text only** for 53 of 55 cards. Card text is truncated mid-sentence (typically around 220 characters), so I judged mostly on title, company, location and the first lines.
- **Card text plus an external posting** for Q11.2 (Superside) and the 8 Welocalize cards (Q15.1–15.4, Q16.1–16.4).
- Nothing else. No applicant profile, no system output, no scores.

---

## 4. Timeline (what happened, in order)

1. She pasted the RAG sheet and asked for verdicts under the five rules, "cruel" and precise. I read the stored note, applied R1–R5 as stored, and gave 3 ticks (Q08.1 borderline, Q11.2 conditional on checking the full posting, Q17.3). I left Q02.1 and the Welocalize cards unticked as ambiguous and told her C1–C4 were missing.
2. She asked for a copy-paste version, then a full-file replacement. Same verdicts, status `unmarked`.
3. She asked me to "sort out" the two open checks. I searched for Superside and Welocalize postings (section 6). Result: Q11.2 became not relevant (R3), Welocalize became not relevant (R2). I set the status to `marked`.
4. She pasted the real R1–R5 and C1–C4, including the rule "if genuinely ambiguous, mark not relevant and log why". No checkbox changed, but I corrected my own earlier overstatement: I had called Welocalize a clean R2 fail, when it was ambiguous. The notes were rewritten.
5. She pasted the Adzuna sheet. I re-judged all 13 cards: kept Q02.1 and Q19.1, flipped Q10.1 to not relevant (C3: judge on merits, not on a pattern from another card).
6. She pasted the RAG sheet again ("do the same"). I produced the same verdicts with per-card notes.
7. She asked for a **card-only** verdict on Q11.2. I said **relevant**. I recorded my external-posting reading (not relevant, R3) as the sensitivity value for § 8.6.
8. She pasted the Claude Code scoring log. I did not run or recompute anything except checking that the sign-test p-values are arithmetically consistent (3 wins/0 losses gives p=0.25; 7/0 gives p=0.0156). I answered a comprehension check about the design and updated the stored project note with the results from her paste.

**Q11.2 changed three times** across the conversation: conditional tick (card), not relevant (external), then relevant (card-only, at her instruction). The final card-only verdict is relevant; the external reading is kept only as a sensitivity row.

---

## 5. Method

- Rules applied: R1–R5 and C1–C4 as she pasted them (after step 4; before that, R2–R5 as stored).
- **R1 (real specific advert):** I did not examine R1 in detail. I did not see category pages or "register your CV" placeholders. I noted umbrella postings (Q11.3, Q11.5, Q17.4, all "all levels / all roles") but failed them on other rules, so R1 never decided a verdict. Duplicates (C3) are left to the scorer; I found no same-title duplicate pairs.
- **R2 (role type) decided almost everything.** It is the most subjective rule and the one most exposed to my background assumptions.
- **R3/R4/R5:** applied only on explicit statements. Silence passes (as per the rules and C1/C2).
- **Eligibility** (country, language fluency) was ignored, as required.
- **Tie-break:** genuinely ambiguous means not relevant (her rule, supplied after my first pass).
- **Strictness instruction:** I was told to be cruel and precise. I applied a strict reading of R2. That is a documented bias toward false negatives.

---

## 6. External lookups: the only evidence beyond the cards

Two search sessions, via a web search tool, using aggregator copies of the postings. Not the pipeline's own stored postings.

**Superside "Conceptual Copywriter" (for Q11.2):**
- Several different Superside copywriter postings exist with different requirements (including a junior in-house one and a lead one).
- The version whose wording matched the card (enterprise customers, translating complex technical ideas) stated 4+ years of agency or fast-paced marketing experience. Two aggregator copies agreed (remotedxb.com copies of the Superside posting).
- The match to the card was by wording only. I cannot prove it is the same posting the pipeline scraped.

**Welocalize "Sports Localization Specialist (Football)" (for Q15.1–15.4, Q16.1–16.4):**
- I read only the **Dutch** posting (and saw a Finnish sibling in search results). The Hebrew, Slovak and Ukrainian postings were **assumed** to share the same template. I did not open them.
- Findings from the aggregators (remotejobs.org copy, remoteleaf listing): the task type is quality control, translation, copy-edit and machine-translation post-editing; duties are reviewing, localizing, fact-checking, translating and adapting existing sports content; copywriting appears as one of several qualifying backgrounds; one board lists it as contract and junior.
- Because search results were later cleared from my context, I can no longer list every URL I saw. If this evidence matters for the write-up, redo the lookups and save dated snapshots to the repo.

---

## 7. Verdict register: every judgment call

**Ticked (5 total)**
| Card | Verdict | Basis | Confidence |
|---|---|---|---|
| RAG Q08.1 Motion Design, Superside | relevant | Brand-facing visual design is plausible for a graphic-designer query. No Figma/branding mention, silence passes. | Borderline |
| RAG Q11.2 Conceptual Copywriter, Superside | relevant (card-only) | Marketing-campaign copywriting is plausible for entry-level marketing; card is silent on seniority/degree. External reading says not relevant (R3). | Borderline, sensitivity row |
| RAG Q17.3 Solution Architecture Manager, Canonical | relevant | Customer-facing field engineering team, not sales; query has no seniority. | Fairly solid |
| Adzuna Q02.1 Family Help Practitioner | relevant | Supporting families at risk of homelessness fits "help people all day". | Fairly solid |
| Adzuna Q19.1 AS400 Lead, Infosys | relevant | Legacy AS/400 modernization is coding and not web development. "Implementing web services" is one listed skill. | Boundary case |

**Not ticked, but a judgment call (the tie-break did the work)**
| Card(s) | Why it is a judgment call |
|---|---|
| RAG Q02.1 Solution Engineer, RelationalAI | Pre-sales technical role, arguably "helping people", not clearly "all day". |
| RAG Q15.1–15.4, Q16.1–16.4 Welocalize (8 cards) | Review/translation/copy-edit/QC of existing content versus copywriting (Q15) or original writing (Q16). One decision applied to all eight; only Dutch was read. |
| Adzuna Q10.1 EdEx "Aspiring Primary Teacher" | Visible text never states a teaching assistant role. Also agency-advertised (R1 not decided). |

**Soft R2 calls (not ticked, less contested)**
- RAG Q17.1 (Senior/Staff/Principal Engineer: nothing on the card shows customer contact)
- RAG Q19.1 (Engineering Manager: management, domain not stated)
- Adzuna Q19.3 (UX Visual Designer: design, not coding)

Everything else fails R2 plainly (e.g. DevOps for an HR query, backend for data entry) or fails R3/R4/R5 on an explicit title or statement (Senior/Lead against junior or entry level, sales roles for Q17, hybrid or on-site against remote).

---

## 8. Justified or not?

**Justified**
- Applying written rules consistently to visible text, with a reason logged per card.
- The clear-cut R2/R3/R4/R5 failures. A careful human would very likely agree.
- Declining to tick ambiguous cards, as the rules instruct.
- Disclosing missing inputs (C1–C4 at the first pass) at the time.

**Weakly justified (could reasonably go the other way)**
- Q08.1, Q11.2, Q02.1 (RAG), Q19.1 (Adzuna), Q10.1, and the Welocalize group.
- The Welocalize verdict applied the Dutch posting's task description to three postings I did not read.

**Not justified, and I did not do these**
- Claiming independent, replicated or inter-rater-checked judgments. There was one rater, one pass, no repeats.
- Claiming I judged the main 20 blind sheets.
- Claiming to have verified the pipeline, the scorer, the K rule or the reported numbers (beyond the arithmetic of two p-values).

---

## 9. Known weaknesses and biases

1. **Single rater, LLM only.** No human agreement check. LLM judges can be consistently wrong in the same direction.
2. **Truncated cards.** Many verdicts rest on a title and a few lines. Silence passes by rule, but R2 is judged from titles.
3. **Strictness instruction** ("cruel") plus the tie-break rule both push toward not relevant. Direction of the resulting bias on the A/B/C comparison is unknown; it could affect systems unequally.
4. **Stored-note dependence.** My first pass relied on a note's version of R1–R5. Later pasted text matched my application of R2–R5, but R1 was not part of my first pass.
5. **Aggregator evidence** for Q11.2 and Welocalize. Not the original or scraped posting.
6. **Order effects.** I saw the sheets over several turns with her running commentary (for example, her suspicion about Q11.2). I tried to judge each card on its merits, but I cannot rule out influence from that context.
7. **Possible shared-model correlation.** I am an LLM judging the output of an LLM-based pipeline (the project uses Groq/Gemini per the stored notes, not Claude). Correlated blind spots between LLMs are plausible.

---

## 10. What I cannot vouch for

- Anything in the repo, the scorer, or the commits (I only saw her pasted log).
- The reported precision@3, the p-values' inputs, win/tie/loss counts, and the 9 failed runs.
- That verdicts were committed before scoring (I only have her statement and log).
- Judgments on any sheet other than the two supplements.
- The 4+ years finding being on the exact posting the pipeline captured.

---

## 11. Things that played a key role in the outcome

1. The **tie-break rule** (ambiguous means not relevant) decided the Welocalize group and Q10.1.
2. **Silence passes** (C1/C2) is why Q11.2 and Q08.1 are ticked on the cards.
3. **Q11.2's card-only versus external reading** is the single largest swing of any one card, and it moves Q11 from a zero to a non-zero in the mean (C4).
4. **Q10.1's flip** moves the Adzuna sheet's result; she reports it brings B − A for precision@5 to 0.00.
5. **Zero-relevant queries** (C4) mean many queries score 0 on these sheets; the fewer ticks I give, the more zeros.
6. **Failed LLM runs scored as ties** make 16 of 19 Adzuna-only comparisons ties. That rule is conservative against any claim that the LLM helps.

---

## 12. Recommended safeguards before citing this in the report

1. **Have a human (you) independently re-judge a random sample (at least 10 cards) plus every card in section 7**, then report agreement with my verdicts. I have not done this and it has not been done.
2. **Run sensitivity rows for every judgment call**, not only Q10.1 and Q11.2: Q08.1, Q02.1 (both sheets), Q19.1, and the Welocalize group flipped to relevant.
3. **Open the Hebrew, Slovak and Ukrainian Welocalize postings** and confirm the Dutch reading.
4. **Save dated snapshots** of the external postings used (Superside, Welocalize) and record URLs and access dates.
5. **Correct the record in Claude Code**: judging by Claude covers the two supplements only.
6. **Disclose LLM-assisted judging** and its limits in the methods section; do not describe it as blind beyond hidden system identity.

---

## 13. Suggested wording for the methods section

> Relevance for the two supplement sheets (55 candidates) was judged by an LLM (Claude) applying rules R1–R5 and clarifications C1–C4 to the visible card text, blind to which system ranked each job. Two cards' judgments drew on external postings (Superside, Welocalize), accessed via third-party aggregators. Judging was single-rater and unreplicated. Ambiguous cases were marked not relevant. Sensitivity analyses report the effect of flipping the judgment-call cards. A human check of a random sample is reported separately [add once done].
