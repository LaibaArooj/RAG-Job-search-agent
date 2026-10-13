# Judging Process Disclosure

**Purpose:** an honest account of what the Claude-chat assistant (this document's author)
actually knows about the RAG-Based Intelligent Job Search Agent project, what role it played
in judging the 20-query precision@5 evaluation, and where that role was and wasn't justified.
Written for Laiba to use, share, or discard at her discretion — nothing here is written to
flatter the process or make it look more rigorous than it was.

---

## 1. How this assistant knows about the project at all

**Everything below came from what Laiba pasted into this one chat conversation.** This
assistant has no independent access to:

- The actual codebase, repository, or file system
- `evaluation/fixtures/`, `evaluation/judging/`, `key.json`, `key_adzuna.json`
- `evaluation/queries.md`, `evaluation/score.py`, or `evaluation/results.md` directly
- Git history, commit timestamps, or the Opus/Fable session's tool-call log
- Anything the Opus/Fable session actually ran, beyond the text summaries Laiba copy-pasted
  back into this chat

What this assistant *did* see: screenshots (terminal errors), one `session_summary.md`
upload, the `EVALUATION.md` and `queries.md` planning documents (pasted as text), 20
judging sheets (pasted as text, one per message, in the order Laiba sent them), a 13-item
supplement sheet (pasted as text), and summarized tool-output text from the Opus/Fable
session (also pasted, not independently verified).

**This means: nothing here was independently confirmed.** If Laiba mistyped a listing, cut
a sheet short, or the Opus session's self-reported actions didn't match what it actually
did, this assistant would have no way of knowing. All reasoning below is built entirely on
trust in what was pasted, in the order it was pasted.

---

## 2. What this assistant's role actually was — and wasn't

**This assistant did not judge any candidate.** It never checked a box. For every one of
the 20 sheets plus the 13-item supplement, Laiba pasted the sheet, this assistant proposed
a verdict and reasoning for each candidate against rules R1–R5, and Laiba decided whether
to accept, modify, or override each call before marking the actual checkbox herself.

The accurate description of this process is: **a single human judge (Laiba) applied a
pre-registered relevance rule, using an AI assistant as an interpretive aid** — similar in
kind to using a second pair of eyes, a style guide, or a research assistant who proposes
readings of a rule but does not have final authority. It is **not** a second independent
judge, and it does not satisfy any claim of "multiple raters" or "inter-rater reliability."

The project's own contamination disclosure already states: *"the same person who debugged
the ranker is choosing the queries and will judge the results"* and names this as a judge
who is *"not blind to the project."* That characterization remains accurate. What should be
added, for full honesty, is that **this single judge used an AI assistant throughout the
judging process to interpret ambiguous cases against the fixed rule.** If an examiner asks
"was this judged by you alone," the honest answer is: *the verdicts and final marks are
mine; I used Claude to help me apply the rule consistently and to catch cases I might have
read inconsistently across 20 sheets.*

---

## 3. Was the guidance methodologically sound? Yes, with real caveats.

**What was sound:**
- The rule (R1–R5) was applied the same way, sheet to sheet, by explicitly checking the
  query's own stated constraints before judging a listing — not letting listing-text
  language (e.g., "expertise," "Senior") trigger a rule the query itself never invoked.
- Ambiguous cases were flagged for notes rather than silently decided, consistent with the
  protocol's own instruction.
- When this assistant's proposed verdict was uncertain or contested, it was marked as "your
  call" rather than asserted as settled — several of those were later overridden or
  qualified by the Opus/Fable session's independent check (see §4).
- The overall evaluation design — pre-registration before seeing results, blind judging,
  frozen fixtures, a documented contamination disclosure, Adzuna-only as the honest
  keyword-vs-semantic headline, git commits made before the scorer ran — is methodologically
  legitimate and was not something this assistant designed; it was already in place in the
  documents Laiba provided.

**What was NOT fully sound, and should be named directly:**

| # | What happened | Why it was a problem | How it was caught |
|---|---|---|---|
| 1 | On Q20 (Superside motion designer), this assistant initially advised leaning "not relevant" based on outside knowledge that creative-agency roles typically require a portfolio in practice — even though the listing's visible text did not state that requirement and R5 only excludes listings that *state* a portfolio requirement. | This applied a rule the text didn't support, selectively, to one listing, while every other unstated requirement on other sheets was given the benefit of the doubt. That's an inconsistency this assistant introduced, not a neutral application of R1–R5. | The Opus/Fable session, reviewing the ruling independently, flagged that the rule as written is clear and the "industry expects it anyway" reasoning was external knowledge being smuggled in. Verdict was corrected to relevant, with both readings reported as a sensitivity check. |
| 2 | Across multiple sheets (Q05, Q07, Q08, Q10, Q12, Q17), this assistant flagged 7 candidate pairs as likely duplicate postings, based on matching or near-identical description text. | This was pattern-matching on visible text alone — this assistant never had access to the underlying fixture job IDs or full listing data to confirm whether two postings were actually the same vacancy or just shared boilerplate from a template (common with agency-posted ads). | The Opus/Fable session compared the actual fixture rows directly. Only 3 of the 7 flagged pairs (Q05 #1/#4, Q08 #4/#5, Q10 #1/#4) were confirmed genuine duplicates. The other 4 were different vacancies that happened to share template language. This assistant's flags were roughly 43% accurate on this specific judgment. |
| 3 | For the three zero-relevant-candidate queries (Q14, Q17, Q18), this assistant characterized the result as a "retrieval-layer problem" — concluding the data source itself wasn't returning matching jobs, as opposed to the ranking systems failing to surface relevant jobs that existed further down the pool. | This conclusion was asserted based only on the top-5 union each query's sheet showed — this assistant never saw the full candidate pool (which turned out to be 60, 55, and 11 jobs respectively for Q14/Q17/Q18) and had no basis to rule out a ranking failure instead of a retrieval failure. | The Opus/Fable session caught this directly, noting the full pool had never been examined, and recommended the queries be included as 0 in the aggregate score with the retrieval-vs-ranking question left open rather than asserted. |
| 4 | On several sheets, R3/R4 "free pass" logic (a rule only applies if the query itself states that constraint) was stated and re-derived fresh each time, rather than being treated as a settled interpretation from the start. | Minor, but worth naming: this created a risk that the logic could have been applied inconsistently in earlier sheets before the pattern was made explicit (around Q02–Q03), even though in practice it appears to have held throughout once articulated. | No external catch — this is a self-flagged risk, not a confirmed error. Worth Laiba's own spot-check if she wants full confidence. |
| 5 | Two genuine rule gaps (qualification requirements like "no degree required"/"no prior experience" not covered by R1–R5 at all; and the silence-vs-industry-convention ambiguity surfaced by Q20) were identified correctly during judging, but this assistant's own proposed fix (extending R3 "by analogy") was exactly the kind of unilateral rule-patching the protocol is supposed to prevent a judge from doing mid-stream. | Flagging the gap was right; quietly resolving it sheet-by-sheet without authorization was not — a judge isn't supposed to redesign the rule they're being measured against. | This was self-caught and explicitly escalated to the Opus/Fable session as something needing a ruling rather than silently applied as settled — see C1 in the final clarifications. This is the one case where the error was caught *before* an external system had to correct it. |

**Net assessment:** the guidance was not a bluff — the reasoning was applied consistently to
the text available and flagged honestly where it was uncertain, matching the rule's own
language rather than inventing new criteria. But it was also not infallible, and a
meaningful fraction of its proposed judgments (most visibly, the duplicate-pair flagging
and the Q14/17/18 retrieval conclusion) were wrong or overreaching, and were only corrected
because a second AI session with actual file access checked the underlying data directly.
**Where this assistant had no way to verify a claim against source data, it should have
flagged that limitation more explicitly in real time than it did.**

---

## 4. What this means for the final results

The numbers in `evaluation/results.md` are not compromised by any of the above — the
Opus/Fable session's corrections were made and applied *before* `score.py` ran and before
any precision@5 number existed, which is exactly what the git-commit-before-scoring
discipline was designed to protect against. The errors this assistant made were caught
inside the blind phase, not after the fact.

What **should** change is how the judging process itself gets described, if it's described
at all in the report or viva:

- It is accurate to say: *"a single developer-judge, assisted by an AI tool in applying the
  relevance rule, with corrections made by a second, independently-verifying process before
  unblinding."*
- It would **not** be accurate to say: *"judged by Claude,"* *"independently verified by
  two separate judges,"* or anything implying this assistant's proposed verdicts were
  authoritative on their own.
- If asked directly whether AI was used in judging, the honest answer is yes — both to
  propose readings of the rule, and separately (in the other session) to verify data
  integrity against the fixtures — and that distinction between the two roles is itself
  worth being able to explain clearly.

---

## 5. Open items this disclosure doesn't resolve

- This assistant cannot confirm that every sheet pasted into this chat was pasted completely
  or in its original, unedited form. That verification can only happen by comparing this
  chat's record against the actual files on disk.
- Item 4 above (the possibility of inconsistent R3/R4 application on the earliest sheets)
  has not been independently checked by anyone. If full confidence matters for the report,
  a quick pass back through Q01–Q03 against the now-settled logic would close that gap.

---

*Written at Laiba's request, for her own use. Nothing in this document should be read as
this assistant certifying its own reliability — that determination is hers to make, using
whatever independent checks she judges necessary.*
