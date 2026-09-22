# Project Spec — RAG-Based Intelligent Job Search Agent

Distilled from SRS v1.0 and SDD v1.0 (Laiba Arooj, 29 April 2026) for use as Claude Code's
working reference. **The SRS and SDD remain authoritative.** If this file contradicts them,
they win — and the contradiction should be fixed here.

---

# Part 1 — Product Requirements

## Project goal

An academic deliverable that must be **demonstrable on a local machine and defensible in a viva**.
Not a production product. The SRS explicitly scopes it to local development and demonstration;
100% uptime is not required.

Implication for build decisions: prioritise the requirements with test cases attached, make the
happy path solid, handle the failure modes the SRS names explicitly (API down, LLM down, rate
limit hit), and don't gold-plate anything else.

## Who it's for

- **Primary:** university students and recent graduates. Basic computer literacy. They don't know
  the exact job titles they should be searching for — that's the problem being solved.
- **Secondary:** working professionals wanting context-aware ranking against their experience level.
- **Internal:** the developer, who has full access to config, database and keys.

## Problems it solves

1. Job boards force users to translate intent into keyword permutations they may not know.
2. Results are ranked by keyword match, not by meaning, so relevant roles get buried.
3. No job board learns from what a user saves or rejects within a session-to-session profile.

## What the product does

### Registration and profile setup (FR-001 to FR-007)

- Entry point: `/register`
- Flow: username + password → uniqueness check → Werkzeug hash → user document created →
  redirect to profile setup → skills (tag input), experience (Entry/Mid/Senior radio),
  location (text, defaults "remote"), work arrangement (multi-select pills) → save → `/search`
- Error state: duplicate username shows inline "Username taken — please choose another"
- Missing profile data falls back to defaults (empty skills, entry level, remote) so search still works
- **Done when:** TC-001 to TC-005 pass

### Natural language search (FR-010 to FR-015)

- Entry point: search bar in the navbar, present on every page
- Flow:
  1. User types a casual query; autocomplete suggests from predefined categories and past searches
  2. `parse_intent()` calls Groq to extract structured intent — work type, experience level,
     category, and **2–3 alternative keyword phrasings** — returned as JSON
     (see "Deviations from the SRS" below; falls back to keyword matching if Groq is down)
  3. User context fetched from MongoDB and injected into the query
  4. `SemanticEngine.encode()` produces a 384-dim vector for the enriched query
  5. Adzuna and Remotive fetched **in parallel**, once per query variant, results unioned
     and deduplicated on `job_id` (SHA of title + company)
  6. Job descriptions batch-encoded; cosine similarity computed against the query vector
  7. Score = similarity + (category_score × 0.02) boost; sorted descending
- Output: ranked job cards — title, company, location, salary if available, source, similarity
  score, Save / Reject / View-on-site
- Empty query: "Please enter a search term", no API call made (TC-017)
- No results: friendly message. API unreachable: error banner with retry. Adzuna 429:
  "Job data temporarily unavailable" (TC-018)
- **Done when:** TC-006, TC-007, TC-015, TC-016, TC-017, TC-018 pass

### RAG pipeline and AI recommendations (FR-016 to FR-018)

- Input: top 5 ranked jobs + user context + original query
- Prompt built by `RAGPipeline.augment()`, sent to Llama 3 8B-instant via Groq
- Output: three top picks with plain-English explanations, in a highlighted band **above** the
  raw results, clearly labelled as AI-generated
- Failure: section hidden entirely, raw ranked results still shown, no crash (TC-009)
- **Done when:** TC-008 and TC-009 pass

### Save / reject and preference learning (FR-008, FR-009)

- Save: job object appended to `saved_jobs` (`$addToSet`), `category_scores[category]` `$inc` +1
- Reject: title appended to `rejected_jobs`, `category_scores[category]` `$inc` −1
- Saving the same job twice must not double-increment (TC-013)
- Button changes state after action
- **Done when:** TC-010, TC-011, TC-013 pass

### For You feed (FR-019, FR-020)

- Reads the user's top-scoring categories, fetches and ranks jobs for those categories
- Re-ranked on every login, so two users with different histories see different feeds (TC-014)
- Match-quality badge per card: Top Match / Great Match / Worth a Look
- **Done when:** TC-012 and TC-014 pass

### Filters and sorting (FR-021 to FR-023) — Medium priority

- Filter chips: Remote / Hybrid / Entry / Mid, applied client-side to the current ranked list
- Sort dropdown: Relevance (default) / Date posted
- **Done when:** TC-015 passes

### Test cases from SRS v1.0 §4 (extracted 2026-09-13, verbatim)

Recorded here so the SRS document does not have to be opened to check one.

| TC ID | Test case | Input | Expected output |
|---|---|---|---|
| TC-001 | User Registration — Valid | Valid username, strong password | Account created, profile setup page shown, document stored in MongoDB |
| TC-002 | Registration — Duplicate Username | Existing username | Error: "Username taken", no account created |
| TC-003 | Login — Correct Credentials | Valid username and password | Session created, redirect to home feed |
| TC-004 | Login — Incorrect Password | Valid username, wrong password | Error: "Invalid username or password" displayed |
| TC-005 | Unauthenticated Access | Visit `/feed` without login | Redirect to `/login` page |
| TC-006 | Semantic Search — Intent Match | "remote job writing no experience" | Results ranked by semantic similarity — writing/remote jobs ranked highest |
| TC-007 | Autocomplete — Partial Match | Type "tec" in search bar | Dropdown shows "Technology", "Tech Support" |
| TC-008 | RAG LLM Response | Complete semantic search results | AI Recommendations section displays top 3 picks with plain-English explanation |
| TC-009 | LLM API Unavailable Fallback | Groq API down (mocked) | Raw ranked results shown, no crash, AI section hidden gracefully |
| TC-010 | Save Job — Score Update | Click Save on a writing job | `writing` score in MongoDB incremented by +1 |
| TC-011 | Reject Job — Score Update | Click Reject on a tech job | `tech` score in MongoDB decremented by −1 |
| TC-012 | For You Feed — Personalized | User with writing=5, tech=−2 | For You feed shows writing jobs prominently, tech jobs absent |
| TC-013 | Same Job Saved Twice | Save same job card twice | Score only incremented once, no duplicate in `saved_jobs` |
| TC-014 | Two Users — Different Feeds | User A likes writing; User B likes tech | A and B see completely different For You feeds |
| TC-015 | Filter by Remote | Apply Remote filter on results | Only remote-tagged jobs shown |
| TC-016 | Context Injection | User profile has "Python" skill | Results for "developer job" rank Python roles higher |
| TC-017 | Empty Search | Submit empty search bar | "Please enter a search term" — no API call made |
| TC-018 | API Rate Limit Reached | Adzuna returns 429 | Friendly banner: "Job data temporarily unavailable" |

### New test cases (not in SRS v1.0 — add to the final test table)

| TC ID | Test case | Input | Expected output |
|---|---|---|---|
| TC-019 | LLM intent parsing | "something creative I can do from home, I'm just starting out" | Structured intent: work_type=remote, experience=entry, category=creative/writing/design |
| TC-020 | Intent parsing fallback | Groq unavailable (mocked) | Falls back to keyword matching, search still completes, no crash |
| TC-021 | Query expansion | "remote writing job no experience" | 2–3 variants generated; API called per variant; union larger than any single variant's result set |
| TC-022 | Cross-source deduplication | Same job present in both Adzuna and Remotive responses | Job appears exactly once in the ranked list |

## Explicitly out of scope (SRS §1.2 and §3.6)

- Direct job application submission — external links only
- Any employer-facing feature or job posting
- Mobile app — desktop browser only, 1366×768 minimum
- Paid, premium or subscription anything
- Emails or notifications
- Generating job listings — only fetching and re-ranking real ones
- Collecting PII beyond username and password

## Milestones — revised for a sub-one-month timeline

The SRS assumes an 8-week timeline. There is under a month left, so the plan below front-loads
everything that has a test case and defers the Medium-priority items.

### M1 — Foundation: auth, profile, database (target: week 1)

- MongoDB Atlas cluster, `users` collection, unique index on `username`
- `config.py` loading all secrets from `.env`
- `DatabaseManager` facade — the only PyMongo consumer
- `AuthController`: register, login, logout, `require_auth`
- Profile setup page and save route
- Base Jinja template + navbar
- **Done when:** a user can register, set up a profile, log out, log back in, and TC-001 to
  TC-005 all pass

### M2 — Search pipeline (target: week 2)

- `APIClient` with `fetch_adzuna`, `fetch_remotive`, run in parallel, plus rate-limit handling
- `JobCard` normalising the two APIs' differing field shapes into one
- **Deduplication** on `job_id` — the two APIs return overlapping listings
- `SemanticEngine` wrapping all-MiniLM-L6-v2 with `encode`, `batch_encode`, `similarity`
- `intent_parser.parse_intent` — **LLM-based via Groq**, returning structured JSON intent
  plus 2–3 query variants, with keyword matching as the fallback path
- **Query expansion:** fetch once per variant, union and dedupe before ranking
- `JobSearchAgent.run()` orchestrating the whole pipeline including the category-score boost
- Search results page with job cards
- **Done when:** a plain-English query returns semantically ranked real jobs; TC-006, TC-016,
  TC-017, TC-018 pass, and TC-019/TC-020 (new, below) pass

### M3 — RAG, learning loop and feed (target: week 3)

- `RAGPipeline`: retrieve, augment, generate, parse_response, fallback
- Groq integration and the AI Recommendations panel
- Save / reject routes with atomic `$addToSet` + `$inc`
- For You feed and `generate_feed()`
- **Done when:** TC-008 to TC-014 pass. **This is the milestone that makes it a RAG project** —
  protect its time.

### M4 — Evaluation, polish and demo (target: week 4)

**Evaluation comes first this week — it is the highest-value item in the whole project.**

- **Retrieval evaluation** (one day, see `docs/EVALUATION.md`): 20 test queries, judge the
  top 5 results relevant/not-relevant by hand, compute precision@5 for semantic ranking vs
  raw API order. Report the numbers whatever they say.
- Autocomplete, filter chips, sort dropdown
- Walk all test cases and record actual results
- Error banners verified for every failure path
- Write up the Known Limitations section below in the final report
- README, requirements.txt pinned, demo script rehearsed
- **Done when:** the demo runs start to finish without you touching the terminal, and you
  have a precision@5 number for both ranking methods

### Cut list — drop these first if time runs short

1. `job_cache` collection — the SDD already marks it optional
2. Render.com deployment — the SRS permits local-only demonstration
3. Sort by salary — not in any FR
4. Autocomplete (FR-011) — degrade to a static category dropdown if needed

---

# Part 2 — Engineering Design

## Tech stack (SDD Appendix A — fixed, do not substitute)

| Layer | Technology | Version |
|---|---|---|
| Language | Python | 3.11 |
| Web framework | Flask | 3.0+ |
| Templating | Jinja2 + HTML5 | — |
| Frontend | Bootstrap | 5.3 |
| Database | MongoDB Atlas | 7.0+ |
| DB driver | PyMongo | 4.6+ |
| Embeddings | sentence-transformers, `all-MiniLM-L6-v2` | 2.7+ |
| LLM | Llama 3 8B-instant via Groq API | — |
| Auth | Werkzeug | ships with Flask |
| Job sources | Adzuna + Remotive | — |
| Config | python-dotenv | — |

## Retrieval architecture — the design decision to be able to defend

**Live retrieval with semantic re-ranking.** No vector database, no persistent index.

Per request: fetch a candidate pool from Adzuna and Remotive, embed the query and every returned
job description in memory with MiniLM, rank by cosine similarity, discard the vectors.

Rationale: the corpus is other people's live job listings. It changes constantly and cannot be
usefully snapshotted, so there is nothing stable to index. Storing embeddings would mean serving
stale postings. The optional `job_cache` collection with a 60-minute TTL handles repeated queries
without introducing staleness beyond an hour.

Trade-off to acknowledge honestly: embedding cost is paid on every search (~200 ms for ~42 jobs)
rather than once at index time, and recall is bounded by whatever the two APIs return for the
parsed keywords. A production system with its own crawled corpus would use a real vector store.

## Deviations from the SRS — declare these in the final report

The SRS is v1.0 and authoritative. Five changes have been made since — four intentional, one
forced. Each needs a one-line justification in the report; supervisors generally accept
documented deviations and penalise undocumented ones.

| Change | SRS said | Now | Why |
|---|---|---|---|
| Intent parsing | `parse_intent` matches keywords with if-statements (SDD §5.1) | Groq call returning structured JSON, keyword matching as fallback | The SRS defines an Agent as something that "autonomously decides what steps to take". Keyword matching doesn't meet that definition. This makes the claim true. |
| Query strategy | One API call per search on the parsed keywords | 2–3 LLM-generated query variants, results unioned and deduped | Directly addresses the recall ceiling described below |
| Evaluation | Not specified | precision@5 over 20 queries, semantic vs raw | The project claims semantic ranking is better; that claim needs evidence |
| **LLM model** | **Llama 3 8B-instant via Groq** | **`groq/compound-mini` via Groq** | **Forced, not chosen — see below** |
| `rejected_jobs` contents | `Array<String>` of job **titles** (§ Data model) | `Array<String>` of **`job_id`** | Titles are not unique across employers. TC-012 requires rejected jobs to be *absent* from the feed; keyed on title, rejecting one "Software Engineer" hides every job with that title from every company. `saved_jobs` already keys on `job_id` for the same reason (TC-013). Field type is unchanged — still an array of strings. |

### The LLM substitution is forced, not a preference

Verified against the live Groq model list on 2026-09-13:

- `llama3-8b-8192` → `400 ... has been decommissioned and is no longer supported`
- `llama-3.1-8b-instant` → `404 ... does not exist or you do not have access to it`
- No Llama **chat** model remains on the account's model list at all. The only `llama` entries
  are `llama-prompt-guard-2-22m/86m`, which are safety classifiers, not generative models.

Everything else about the design is unchanged: same provider (Groq), same free tier, no credit
card, same two-calls-per-search pattern, same try/except and fallback. The model id lives in a
single constant `GROQ_MODEL` in `rag_pipeline.py`, so if a Llama model returns to Groq this is
a one-line revert.

**Action required:** tell the supervisor. The honest viva answer is "the SRS named a model the
provider retired during implementation; the architecture isolates that choice to one constant,
so the substitution cost one line." Do **not** claim the system runs Llama 3 anywhere in the
report, the code comments or the demo.

Both new Groq calls sit behind the same try/except and fallback pattern as the RAG call, so
FR-018's "never crash if the LLM is unavailable" still holds.

**Under consideration, not yet decided:** `all-MiniLM-L6-v2` is trained for *symmetric* sentence
similarity (two texts of similar length) and truncates at 256 tokens. This system matches a
short query against long job descriptions — an *asymmetric* task — so most of each description
is silently discarded. `msmarco-MiniLM-L6-v3` is trained for exactly this case and is a
one-string change. Deviating from the model named in the SRS needs supervisor sign-off, so
either get it or keep the current model and name the mismatch as a limitation.

## Known limitations — write these up honestly

An FYP that names its own weaknesses scores better than one that pretends it has none. These
are the ones an examiner is most likely to find.

1. **Recall is bounded by keyword search.** The system re-ranks whatever Adzuna and Remotive
   return for the parsed keywords. If keyword search misses a relevant job, embeddings cannot
   recover it. This is semantic *re-ranking*, not semantic *retrieval*. Query expansion widens
   the pool but does not remove the ceiling.
2. **No persistent vector index.** Justified — the corpus is external and volatile — but it
   means embedding cost is paid per request rather than once, and no cross-session retrieval
   is possible.
3. **Truncation.** MiniLM's 256-token limit means only roughly the first paragraph of each job
   description is embedded.
4. **The 0.02 boost coefficient is unjustified.** It was chosen by hand, not tuned. Cosine
   similarities cluster in a narrow band, so a category score of 5 shifts ranking materially.
   Either tune it during evaluation or state plainly that it is a heuristic.
5. **LLM explanations are unverifiable.** Llama 3 will produce a fluent, confident rationale
   whether or not the match is real, and may reference requirements the listing never stated.
   The UI labels the section as AI-generated; that is a mitigation, not a fix.
6. **Preference learning is shallow.** A single integer per category, ±1 per interaction, with
   no decay and no notion of *why* a job was rejected (wrong salary? wrong location? wrong
   role?). It captures category preference and nothing finer.
7. **Cold start.** A brand-new user has no scores, so personalisation contributes nothing until
   they have saved or rejected several jobs.
8. **No evaluation of the LLM stage.** precision@5 measures the ranking. Whether the three AI
   picks are better than the top three by similarity alone is untested.
9. **Categories are assigned by keyword matching.** Added 2026-09-21. A job's category — which
   is what the whole save/reject preference loop scores — comes from substring matching the job's
   title and first 500 characters against a hand-written hint table, first match winning. It
   misfiles jobs whose text names no category word (they fall back to the query's category, or
   `"other"`) and jobs that mention two fields (order of the table decides). It is not
   classification by meaning and the report must not describe it as such. A learned classifier,
   or the embedding model itself, would be the upgrade; both were weighed and rejected as harder
   to justify in a viva than a table you can read.

## Data model — MongoDB `users` collection

Single denormalised document per user (SRS §3.7).

| Field | Type | Notes |
|---|---|---|
| `_id` | ObjectId | auto |
| `username` | String | **unique index** |
| `password` | String | Werkzeug PBKDF2 hash |
| `skills` | Array\<String\> | |
| `experience` | String | entry / mid / senior |
| `location` | String | or "remote" |
| `preferred_work` | Array\<String\> | remote / hybrid / on-site / freelance |
| `category_scores` | Object | dynamic, e.g. `{writing: 5, tech: -2}` |
| `search_history` | Array\<String\> | |
| `saved_jobs` | Array\<Object\> | `{job_id, title, company, category, location, source, source_url, saved_at}` |
| `rejected_jobs` | Array\<String\> | job titles |
| `created_at` | Date | auto |

`job_id` = SHA hash of title + company, used for duplicate-save detection.
`category_scores` is a dynamic object specifically so new categories need no schema change.

Optional `job_cache` collection: `query_hash` (MD5 of normalised query) as key, `query_text`,
`results`, `vector`, `hit_count`, `created_at` with a 60-minute TTL index.

## Module layout (SDD Appendix B)

```
job_search_agent/
├── app.py                    # Flask app factory + route registration
├── config.py                 # env-driven config (API keys, DB URI)
├── controllers/
│   ├── auth_controller.py    # register, login, logout, require_auth
│   └── ui_controller.py      # search, feed, save, reject, profile
├── core/
│   ├── agent.py              # JobSearchAgent
│   ├── semantic_engine.py    # SemanticEngine
│   ├── rag_pipeline.py       # RAGPipeline
│   └── intent_parser.py      # parse_intent
├── adapters/
│   ├── api_client.py         # Adzuna, Remotive, Groq
│   └── db_manager.py         # MongoDB facade
├── models/
│   ├── user.py               # User dataclass
│   └── job_card.py           # JobCard dataclass
├── templates/                # base, login, profile_setup, search_results, for_you
├── static/css/, static/js/
├── requirements.txt
├── .env.example
└── README.md
```

## Non-functional targets (SRS §3.5)

- Search results within 5 s; Groq response within ~3 s; single-query encoding under 1 s after
  model load; end-to-end target ~4 s (SDD Appendix C)
- Loading indicator during API calls — never a frozen UI
- Passwords hashed, keys in env vars, `.env` gitignored, Flask secret key from env
- CSRF token on every form post
- Modules split as `routes / models / agent / utils`; one-line docstring per function
- Runs on any machine with Python 3.11; `requirements.txt` installs in one command

## Infrastructure status

- [x] Adzuna API key obtained, in `.env`
- [x] Remotive — no key required
- [x] Groq API key obtained, in `.env`
- [ ] **MongoDB Atlas cluster created, connection string in `.env`** ← current blocker
- [ ] Unique index created on `users.username`
- [ ] `all-MiniLM-L6-v2` downloaded on first run (~90 MB, needs internet once)

## Open questions

- [x] **How is a job's `category` determined?** — settled 2026-09-21. Neither taxonomy is
      mapped. Every job, whichever source returned it, is classified locally from its own title
      and description against `config.CATEGORY_HINTS` by `core.intent_parser.classify_category`
      — the same table and matcher the `parse_intent` keyword fallback uses on a query. One
      rule for both sources, so a category score cannot fragment by source, and no per-source
      mapping table has to be defended or kept current. Cost, to be stated in the report: it is
      substring keyword matching over job text, first match wins, and a job whose text names no
      category word falls back to the parsed intent's category or `"other"`.
- [ ] Where does the autocomplete category list come from — hardcoded constant, or built from
      `search_history`? SRS says both.
- [x] Does the For You feed call the live APIs (costing Adzuna quota on every visit) or reuse
      the last search's results? **Settled 2026-09-21: live, through the existing 60-minute
      cache, keyed on the category NAME.** The quota objection does not survive inspection —
      `CATEGORIES` is a closed set of 13 strings, so every user and every feed visit shares the
      same cache keys and all feed traffic in the app costs at most ~13 Adzuna calls per hour
      against a 250/day budget. A user with no positive category scores returns before any
      fetch at all. See `docs/ARCHITECTURE.md` § For You feed request flow.
