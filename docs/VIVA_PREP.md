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

**Updated 2026-09-30: you measured it, and on ranking alone it isn't better.** Give the
number first; don't let them drag it out of you. On 20 pre-registered, blind-judged queries,
semantic re-ranking scored precision@5 0.32 against Adzuna's keyword order at 0.31, with
3 wins, 3 losses and 13 ties. That is indistinguishable. `evaluation/results.md` has the
table.

What you can defend, in this order:

1. **The claim was tested, not assumed**, with pre-registered queries, a relevance rule
   fixed before judging, and blind judging. The null result is the finding.
2. **Where it did differ, the pattern is informative.** It helped some vague and negation
   queries (Q16 `not journalism`, 0 → 0.4) and hurt specific ones (Q08, Q11, Q15), where
   Adzuna's keyword order was already good. Know two examples of each by heart.
3. **What the system adds beyond ranking order** is not what precision@5 measures: intent
   parsing, the eligibility badge on every card, the explained AI picks, and the
   save/reject loop.
4. **It can only re-rank what keyword search returned**, so it never could improve
   discovery. That limitation still stands.

Do not say "it's better in practice" or "the sample was too small to show it". The first is
unsupported. The second is half true, but it sounds like an excuse unless you add that a
larger sample could equally confirm there's no effect.

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
- Why `openai/gpt-oss-120b` on Groq, and not the Llama 3 the SRS names? (Forced twice, by
  model retirements. Know the reasoning-token trap.)
- Why is `DatabaseManager` the only class that imports PyMongo?
- Why 5 jobs into the RAG prompt and 3 out? Why those numbers?

## The uncomfortable ones — prepare these properly

- **"Where did 0.02 come from?"** Hand-picked, and never tuned; say so. You now also have
  the ablation (system C): the boost changed only 3 of 20 queries, helping 1 and hurting 2,
  under a synthetic profile you declared in advance. That's evidence it barely matters, and
  where it does, a wrong guess about the user costs more than a right one gains. Don't claim
  it was validated.
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

## The evaluation — questions the result invites (added 2026-09-30)

Source: `evaluation/results.md`, `evaluation/queries.md` § 7, and the 2026-09-30 changelog.

- **"So what was the point of the semantic ranker?"** See #3 above. Lead with the number,
  then say what the system does besides re-ranking.
- **"You changed the rules after judging."** Clarifications, not changes. They're recorded
  separately in § 7, and every one was made before `key.json` was opened, so none could
  favour a system. The git history shows the marked sheets and the rules committed before
  the scorer's first run.
- **"Why did you drop Q04 from the headline?"** It has no Adzuna listings, so Adzuna-only
  precision is undefined, not zero. Why only 13 of 19 can discriminate: on six queries the
  Adzuna pool has ≤5 listings, so every system returns the same set.
- **"Four queries found nothing relevant. Isn't that the system failing?"** Only among the
  judged candidates, the union of three top 5s. You can't claim the pool holds none. That's
  pooled judging; know why it supports precision but not recall.
- **"eligible@5 went up. Doesn't that show it helps?"** Not as a design claim. The ranker
  never reads eligibility; it happened to rank more worldwide-hiring Jobicy listings higher.
- **"What does p = 1.0 mean?"** An even win/loss split. A high p is not evidence that there's
  no effect; with this few non-tied queries, only a large, consistent effect could be
  detected.
- **"Who judged?"** You, once, not blind to the project but blind to the system. Name it as
  the main threat to validity before they do.

### The RAG stage (added 2026-10-01; result in `evaluation/rag_results.md`)

- **"Does the LLM actually improve anything, or is it decoration?"** That's what the
  RAG-stage evaluation measures. Lead with the precision@3 number, whatever it is.
- **"Why compare against the first three of the five, not the top three by cosine?"**
  Because both systems then get identical inputs, so any difference comes from the LLM alone.
  `rag_candidates` lifts applicable jobs from lower ranks; comparing against the cosine top 3
  would mix that re-partition into the LLM's score.
- **"The LLM is random. How do you know you didn't get a lucky run?"** Three frozen runs
  per query, the mean reported with the per-run spread, and the model pinned so the fallback
  chain couldn't switch models mid-experiment. Picks are never regenerated.
- **"What if Groq failed during the evaluation?"** A failed run scores as K, because K is
  what the product shows when Groq fails (FR-018). It's never retried, because retrying only
  the failures would change the rule. The count is in the results.
- **"How do you know the judging wasn't influenced by which jobs the LLM picked?"** The new
  sheet was built and committed before any pick existed; the git history shows it. The
  candidates don't depend on the LLM, so the sheet couldn't leak them.
- **"The prompt tells it to prefer jobs you can apply for. Doesn't that skew it?"** Yes, and
  it's pre-registered as a confound. Relevance excludes eligibility, so an LLM that obeys its
  prompt can lose on precision@3 and win on eligible@3. Both are reported side by side.

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
