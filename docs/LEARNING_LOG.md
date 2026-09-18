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
| Parallel fetch | | | What's actually running concurrently, and what does it save? |

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
| precision@k | | | Define it. Why @5 and not @10? |
| Precision vs recall | | | Which one can you measure here, and which can't you? Why? |
| Why blind judging matters | | | What bias is it controlling for? |
| Cold start problem | | | Why is a brand-new user's feed no better than search? |

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
