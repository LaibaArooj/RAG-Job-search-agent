# Learning Log

The code track and the understanding track are separate. Shipping a feature does not mean you
can explain it. This file tracks the second one.

## How to use this

After finishing any component, run `/explain <component>` in Claude Code, answer the two
questions it asks you at the end, then update your rating here. Be harsh — an inflated rating
here becomes a silence in the viva.

**Rating scale**

| | Meaning |
|---|---|
| 🔴 | Don't know what this is |
| 🟡 | Recognise it, can't explain it unprompted |
| 🟢 | Can explain it out loud, without notes, to someone who doesn't know it |
| ⭐ | Can also explain the alternatives and why this one was chosen |

**Target before submission:** 🟢 minimum on everything in Tier 1, ⭐ on the six starred rows.

---

## Tier 1 — You will be asked about these

### The AI/ML core

| Concept | Rating | Last checked | Notes / gaps |
|---|---|---|---|
| ⭐ What RAG is — retrieve, augment, generate | | | Lewis et al. 2020. What problem does it solve that a bare LLM doesn't? |
| ⭐ What an embedding is | | | Why is a 384-number vector a "meaning"? What makes two vectors close? |
| ⭐ Cosine similarity | | | Why cosine and not Euclidean distance? What does `normalize_embeddings=True` change? |
| Sentence transformers vs plain BERT | | | Reimers & Gurevych 2019. Why does BERT alone give bad sentence vectors? |
| Symmetric vs asymmetric semantic search | | | Which is yours? Why does it matter for model choice? (See limitation 3) |
| Semantic search vs keyword search | | | Give a concrete query where each wins |
| What a transformer / attention is, roughly | | | You don't need the maths. You need one honest paragraph |
| Tokens and the 256-token limit | | | What actually happens to text past the limit? |
| LLM hallucination | | | Why can't you verify the AI's explanations? |
| Prompt construction / context injection | | | What exactly goes into your RAG prompt, in what order? |

### Your system's design

| Concept | Rating | Last checked | Notes / gaps |
|---|---|---|---|
| ⭐ Why there is no vector database | | | The single most likely question. Rehearse this one |
| ⭐ The recall ceiling | | | Re-ranking vs retrieval. Know it before they tell you |
| The full search pipeline, in order | | | Be able to walk all 10 steps from memory |
| Layered architecture / separation of concerns | | | Why is `DatabaseManager` the only PyMongo consumer? |
| The 0.02 category boost | | | Where did the number come from? Honest answer required |
| The fallback design | | | What happens when Groq fails, and why is that the right behaviour? Verified working 2026-09-13 — be able to describe how it was tested |
| Isolating a vendor choice to one constant | | | Added 2026-09-13. Groq retired Llama 3 mid-project. Why did that cost one line instead of a rewrite? This is the layering argument paying off — use it as the concrete example |
| Parallel fetch | | | **Not built — know this as a deferral, not a feature.** The SDD specifies query encoding ‖ Adzuna ‖ Remotive; `core/agent.py` fetches sequentially instead (2026-09-19). Be able to say what the fork would have saved and why it was traded away. Claiming it works in the viva when the code loops is the worst answer here |
| **Circular imports / partially initialized modules** | | | Added 2026-09-19. `ui_controller` -> `core.agent` -> `core.intent_parser` -> `ui_controller` raised "cannot import name ... from partially initialized module". Why does Python fail here rather than looping forever? And the sharp bit: the same three imports **passed** with the import at the bottom of the file and **failed** at the top, where PEP 8 puts it. Why does line order decide it? |
| **Validating LLM output against a closed set** | | | Added 2026-09-19. `parse_intent` lists the allowed values in the prompt *and* re-checks membership on the way out. Why isn't the prompt enough? Tie it to the field-path injection row below — the category reaches `category_scores.<category>` in M3. |
| **Dependency injection / test doubles** | | | Added 2026-09-19. `JobSearchAgent.__init__` takes `db`, `semantic_engine` and `rag_pipeline` as arguments instead of constructing them. That one choice is why `verify_agent.py` runs offline in under a second with no model load, no Atlas and no Adzuna quota. Question to be ready for: which of the 57 assertions could *not* be written without doubles? (Answer: the TC-017 ones — proving a call did **not** happen needs a counter, not a return value.) |
| **Hashing as an identity, not as a secret** | | | Added 2026-09-19. SHA-256 appears twice in this project doing completely different jobs: `JobCard.make_job_id` uses it to decide two listings are the same job (TC-022), and `_cache_key` uses it to turn a query string into a safe MongoDB `_id`. Neither is security. Why is SHA-256 right for these and wrong for passwords — and why does the password row above want something deliberately *slow*? Also: why does `make_job_id` lowercase and join with `"|"`? |

### Backend and data

| Concept | Rating | Last checked | Notes / gaps |
|---|---|---|---|
| ⭐ Password hashing vs encryption | | | Why is hashing one-way, and why does that matter? What is a salt? |
| PBKDF2 | | | Why deliberately slow? |
| Flask sessions and signed cookies | | | Where is session state stored? What stops a user forging one? |
| CSRF | | | What's the attack, and how does the token stop it? Yours is hand-rolled — why not Flask-WTF? |
| **Session fixation** | | | Added 2026-09-19. `login()` calls `session.clear()` *before* setting `username`. What attack does that stop, and why isn't setting the key enough on its own? |
| **Constant-time comparison** | | | Added 2026-09-19. `hmac.compare_digest` instead of `==` for the CSRF token. What does `==` leak, and why does it leak it? |
| **Username enumeration** | | | Added 2026-09-19. Unknown user and wrong password produce the *same* message. What does an attacker learn from two different messages? |
| **Flask blueprints** | | | Added 2026-09-19. Routes now live in `auth_bp` and `ui_bp`, and templates say `url_for('auth.login')`, not `url_for('login')`. What does a blueprint buy you over routes on `app`? |
| **Decorators and `functools.wraps`** | | | Added 2026-09-19. `require_auth` wraps a view. What breaks in Flask if you omit `wraps` — and why is the symptom an endpoint-name collision? |
| **Why embeddings cannot filter seniority** | | | Added 2026-09-20. `all-MiniLM-L6-v2` rates `similarity("junior developer", "senior developer") = 0.806` — the two are near-synonyms in embedding space, because they appear in near-identical contexts. Questions to have ready: why does cosine similarity behave this way, and what does it imply about which jobs a semantic ranker can and cannot distinguish? Why is the level filter keyword-based rather than learned? |
| **Keyword AND-matching vs semantic search** | | | Added 2026-09-20. Adzuna's `what=` is an AND match, so "remote junior software engineer" returns 0 where "junior software engineer" returns 77. This is the concrete demonstration of the project's own honesty claim — the system re-ranks what keyword search returns, so a query keyword search cannot match yields nothing to re-rank. |
| **"Succeeded" is not "returned something"** | | | Added 2026-09-20. Adzuna answering HTTP 200 with zero results is not a failure, so `failed_sources` stayed empty and no banner showed, while the pool silently filled with another source's constant list. What is the general lesson about error signals, and why did the offline test suite pass throughout? |
| **Endpoint names vs URLs** | | | Added 2026-09-20. Moving the search route changed the *endpoint* from `home` to `ui.search` while the *URL* stayed `/`. Six `url_for("home")` calls had to move with it. Two questions: why is a `BuildError` raised at render time rather than at startup, and what does that imply about how much a test suite that only checks status codes can catch? |
| **`app.config` as the wiring seam** | | | Added 2026-09-20. Controllers read `current_app.config["DB"]` and `["AGENT"]` rather than importing `app`. Why would importing `app` be a circular import, and what does this buy over a module-level global? Related: the SDD wants a `create_app()` factory — what does a factory give you that this does not? Pairs with the dependency-injection row. |
| **Same-origin fetch and CSRF** | | | Added 2026-09-21. `decisions.js` posts with `fetch` and a **form-encoded** body, not JSON, because `check_csrf()` reads `request.form` — a JSON body arrives with `request.form` empty and fails every token check. Two questions: why does the CSRF token still protect a `fetch` request at all, and what does `credentials: "same-origin"` do that matters here? |
| **Validating at the boundary vs at the sink** | | | Added 2026-09-21. The category is checked against `CATEGORIES` in the route *and* in `_score_path`. The route check is not redundant: without it the same bad value reaches the user as a **500** instead of a **400**. Question: when is a duplicated check defence in depth, and when is it just noise? |
| **Dead code that passes its tests** | | | Added 2026-09-21. The `category_scores[job.category] × 0.02` boost was green in `verify_agent.py` throughout M2 while contributing exactly 0 in the running app, because `JobCard.category` was always `""` and the test passed categories in directly. Question: what class of bug does a test that supplies its own inputs systematically miss, and what kind of assertion catches it? Same family as the TC-021 gap found on 2026-09-20. |
| NoSQL vs relational | | | Why MongoDB here? What would you lose moving to Postgres? |
| Denormalisation | | | Why is everything in one user document? |
| Database indexes | | | What does the unique index on `username` actually do? |
| Atomic operations — `$inc`, `$addToSet` | | | Why not read-modify-write? |
| **Idempotency via a conditional filter** | | | Added 2026-09-13. `save_job` filters on `{"saved_jobs.job_id": {"$ne": id}}` so a repeat save matches no document and the `$inc` never runs — TC-013 with no read first. Why is reading the document and then deciding unsafe? What is the race? |
| NoSQL injection via **field paths** | | | Added 2026-09-13. `models.py` builds `f"category_scores.{category}"` from API data. A value containing `.` or `$` writes to the wrong place. Why is a field path more dangerous than a value? |
| Data normalisation across two APIs | | | Added 2026-09-13. Adzuna nests `company.display_name`, Remotive uses a flat `company_name`. What breaks if the route layer sees raw shapes? (It did — dicts rendered into the page.) |
| Reading a connection error | | | Added 2026-09-13, extended same day. Three distinct failures now seen on this project: `bad auth` (reached Atlas, credential wrong), `ServerSelectionTimeout` (never reached it), and TCP connecting but the **TLS handshake** timing out on :27017 while :443 works (a middlebox on that port). Which layer does each one rule out, and why does the third mean the password is irrelevant? |
| Unicode homoglyphs in credentials | | | Added 2026-09-13. Cyrillic `а` U+0430 vs Latin `a` U+0061 are visually identical. Why can't you spot this by reading the file? |
| REST APIs and HTTP status codes | | | What is 429 and how do you handle it? |
| Rate limiting | | | 250/day — how does your code respect it? |
| TTL indexes | | | Added detail 2026-09-13. `expireAfterSeconds` on `job_cache.created_at`. Who deletes the document — your code or the server? How often does the sweeper run, and why is expiry therefore approximate? Which direction does a *longer* TTL move your Adzuna quota use? |

### Evaluation

| Concept | Rating | Last checked | Notes / gaps |
|---|---|---|---|
| precision@k | | | Define it. Why @5 and not @10? Why is the RAG stage precision@3 (added 2026-10-01), and why is it still divided by 3 when the LLM returns fewer picks? |
| Precision vs recall | | | Which one can you measure here, and which can't you? Why? |
| Why blind judging matters | | | What bias is it controlling for? |
| Cold start problem | | | Why is a brand-new user's feed no better than search? |
| Pooled judging | | | Added 2026-09-30. You judged only the union of the three top 5s, not the whole pool. Why is that enough for precision@5 but useless for recall? Why can't you claim Q14/Q17/Q18 have *no* relevant jobs? Why did the Adzuna-only headline need a supplementary sheet? |
| Repeated sampling of a stochastic system | | | Added 2026-10-01. The RAG-stage evaluation runs the LLM 3 times per query, because temperature 0.3 with no seed means one run is one sample. Why is the mean of 3 runs fairer than 1 run? Why are the picks frozen and never regenerated? Why does a failed run count as K instead of being retried or dropped? |
| Isolating one stage of a pipeline | | | Added 2026-10-01. The RAG-stage baseline is "the first 3 of the same 5 candidates", not "the top 3 by cosine". Why does handing both systems identical inputs mean any difference comes from the LLM alone? What would the other baseline have mixed in? |
| Forced-count prompts, and decline vs failure | | | Added 2026-10-11. Why does asking an LLM for "the three best" produce anti-recommendations when nothing fits? Why must "the model said no match" ([]) and "the call failed" (None) be different states, and what does each render? Why was re-measuring the new prompt on the same 20 queries ruled out? |
| Cohen's kappa | | | Added 2026-10-11. Agreement between two judges, corrected for the agreement you'd get by chance. Compute it from a 2×2 table by hand. Why isn't raw agreement enough? What does kappa = 0 mean? |
| The kappa paradox | | | Added 2026-10-11. Relevant cards are rare here (13 of 58 in the sample, by your verdicts). Why can kappa be low when two judges agree on 90% of cards? Why is positive agreement, 2a / (2a + b + c), reported beside it? |
| Sign test | | | Added 2026-09-30. `score.py` reports one. Why does it ignore ties? Why is it a better fit than a t-test for 0.0–1.0 scores in steps of 0.2 over ~13 queries? Why is a high p-value here *not* evidence that the ranker doesn't help? |

---

## Tier 2 — Nice to have, ask only if time allows

| Concept | Rating | Notes |
|---|---|---|
| Content-based vs collaborative filtering | | Which is yours? Why can't you do the other one? |
| Vector databases (FAISS, Pinecone, pgvector) | | Know what they are, so "why no vector DB" has weight |
| Chunking strategies for long documents | | How you'd handle the truncation problem properly |
| Reranker models (cross-encoders) | | The proper fix for asymmetric search |
| Hybrid search (BM25 + dense) | | The industry answer to your recall ceiling |

---

## Weekly self-check

Every Friday, pick three rows at random and explain them out loud with the file closed. If you
can't, drop the rating and note the gap.

| Date | Rows tested | Result | Action taken |
|---|---|---|---|
| | | | |
