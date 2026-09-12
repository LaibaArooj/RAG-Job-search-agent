# Viva Preparation

Questions an examiner is likely to ask, ordered roughly by how likely they are. Write your own
answer under each one in your own words — a rehearsed answer in someone else's phrasing falls
apart on the first follow-up.

Rehearse out loud. Silently thinking "yes I know that" is not the same skill as saying it.

---

## The five you will almost certainly get

### 1. "Explain your project in two minutes."

Cover: the problem, what the system does, the three-stage pipeline, the learning loop, and
what makes it different from a job board. Practise until it's fluent — this sets the tone for
everything after.

**Your answer:**

### 2. "Where is your vector database?"

They're testing whether you understand RAG or just implemented a tutorial. The answer is that
the corpus is external and volatile, so there's nothing stable to index; you'd be serving stale
postings. Embeddings are computed per request and discarded, with a 60-minute cache for repeats.

Follow-up to expect: *"So when would you use one?"* — a system with its own crawled corpus.

**Your answer:**

### 3. "How is this better than keyword search?"

The honest answer has two halves, and giving only the first is what gets you caught. It ranks
by meaning, so a user who doesn't know the right job title still gets relevant results — and
you have the precision@5 numbers to show it. But it can only re-rank what keyword search
returned, so it improves ordering, not discovery.

Volunteering the limitation before they find it is worth more than the feature itself.

**Your answer:**

### 4. "Walk me through what happens when I type a query."

All ten steps, in order, from auth check to rendered page. Know where the fork is, where the
try/except sits, and what happens at each of the five decision points.

**Your answer:**

### 5. "What would you do differently with more time?"

Have three ready, specific and technical. Suggestions: hybrid retrieval (BM25 + dense) to break
the recall ceiling; a cross-encoder reranker on the top 50; chunking long descriptions instead
of truncating at 256 tokens. Vague answers ("more testing", "better UI") read as not having
thought about it.

**Your answer:**

---

## Design decisions they'll probe

- Why MongoDB and not a relational database? What would you lose?
- Why is everything in a single user document rather than separate collections?
- Why Flask rather than Django or FastAPI?
- Why `all-MiniLM-L6-v2` specifically? Did you compare it against anything?
- Why Llama 3 on Groq rather than another model?
- Why is `DatabaseManager` the only class that imports PyMongo?
- Why 5 jobs into the RAG prompt and 3 out? Why those numbers?

## The uncomfortable ones — prepare these properly

- **"Where did 0.02 come from?"** If you tuned it, say so and show the numbers. If you didn't,
  say "it's a hand-picked heuristic and it isn't tuned; here's how I'd tune it." Do not invent
  a justification — they'll ask a follow-up and it will collapse.
- **"How do you know the AI's explanations are correct?"** You don't. The LLM produces a
  confident rationale regardless. Mitigation is the AI-generated label, not verification.
- **"Your model truncates at 256 tokens. What are you losing?"** Most of each job description.
  Know that this is limitation 3 and that chunking is the proper fix.
- **"Is this actually an agent?"** Since the change to LLM-based intent parsing, it decides its
  own query variants — defensible. Before that it was if-statements. Don't overclaim autonomy.
- **"How many people tested this?"** One — you. Say so plainly and frame the evaluation as a
  small-scale relevance assessment with a single non-blind judge.
- **"What happens if Adzuna shuts off its free tier?"** The system stops working. It's an
  acknowledged dependency in SRS §2.5.

## Live demo — rehearse the failure paths too

Panels love asking you to break your own system.

- [ ] Demo script written and run end to end at least three times
- [ ] Groq disabled → AI panel hides, raw results still show, no stack trace
- [ ] Empty query → "Please enter a search term", no API call fired
- [ ] Two different user accounts → visibly different For You feeds
- [ ] Save a job → show the score change in Atlas, live
- [ ] Save the same job twice → score increments once
- [ ] Adzuna quota checked the morning of the demo
- [ ] Model pre-downloaded, first-run delay avoided
- [ ] Fallback plan if the venue wifi fails — recorded video or cached fixtures

## Things you should be able to draw on a whiteboard

- [ ] The five architecture layers
- [ ] The search pipeline as a flow with its decision points
- [ ] The user document schema
- [ ] Two vectors and the angle between them, explaining cosine similarity

## Self-test log

| Date | Question attempted | Went well / badly | What to fix |
|---|---|---|---|
| | | | |
