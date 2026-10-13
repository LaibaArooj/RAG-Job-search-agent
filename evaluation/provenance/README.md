# Judging provenance — who produced the relevance verdicts

**Disclosed by the developer on 2026-10-13.** Every relevance verdict in this evaluation was
proposed by Claude (Claude Sonnet 5.5, per the developer) in claude.ai chats, and adopted by
the developer. Until that date, every results file and doc said "Judge: the developer". That
statement was wrong. The disclosure is `evaluation/queries.md` § 10.

| Sheets | When | Proposed by | Marked by | Evidence beyond the card |
|---|---|---|---|---|
| 20 main sheets (139 cards) and the Adzuna supplement's first pass (13) | 2026-09-26 to 09-30 | Claude, chat A | The developer, who states she adopted the proposals unchanged | None. Sheet text pasted into the chat |
| Adzuna supplement re-read (13) and RAG sheet (42), including the Q10.1 and Q11.2 re-readings of § 8.6 | 2026-10-11 | Claude, chat B | The developer, copying the answers | Aggregator copies of the Superside posting (Q11.2) and the Dutch Welocalize posting (Q15–Q16). Chat B was also told to be strict ("cruel") |

## The two records

- **`chat-A-main-sheets.md`** is written by chat A, about the 20 main sheets and the first
  Adzuna pass. It says chat A proposed verdicts and the developer marked them. It lists five
  of its own errors, all corrected before scoring: the Q20 portfolio reasoning that became C2,
  4 of 7 duplicate pairs it flagged that were not duplicates, the "retrieval problem" claim on
  Q14, Q17 and Q18, and two others.
  - *Limits:* chat A saw only text pasted into it. It could check nothing against the
    repository.
- **`chat-B-supplements.md`** is written by chat B, about the two supplements. It covers its
  method, a timeline, every judgment call with a confidence rating, its biases, and its own
  recommended safeguards.
  - *Limits:* the URLs it searched were not saved, and the matches to the captured adverts
    were by wording only.

Both are copied **unedited**, byte for byte, from the files the developer provided on
2026-10-13. They are an AI's account of its own work, not independent evidence. Small slips
in them are left as written. For example, chat B mentions Gemini, but the project's LLM is
Groq `openai/gpt-oss-120b`.

**A third document was left out.** It was written by a claude.ai chat that had only saved
notes. It verifies nothing, says so itself, and states a wrong fact: that Gemini is the RAG
model.

## What this does and doesn't change

- **Blindness to the system held.** Neither chat ever saw `key*.json`, ranks or sources.
- **No verdict changes.** The results stand as computed, but they are AI-proposed verdicts
  from one model, with **no human validation yet**.
- **The RAG stage is exposed to circularity.** An LLM judged whether an LLM's picks were
  relevant. `rag_results.md` states this beside the numbers.
- **The § 9 second judge is now the human validation:** an independent person, using no AI,
  judging a random sample blind.
