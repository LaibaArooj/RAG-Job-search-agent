# Changelog — RAG-Based Intelligent Job Search Agent

All notable changes, newest first. Claude appends an entry after each shipped feature.

## [Unreleased]

### Added
### Changed
### Fixed
### Removed

---

## 2026-09-25 — TC-009 closed: the LLM-outage fallback is now measured

TC-009 is the test case behind FR-018 — *"Groq API down (mocked) → raw ranked results shown,
no crash, AI section hidden gracefully"* — and it was the one SRS test case with no assertion
carrying its name. Closed now, in three places it was not covered before.

### Why the existing checks were not enough

`test_rag_fallback` already asserted the fallback, but through `StubRAG(reply=None)`. That
proves the **agent** copes with a `None`; it never once executed `RAGPipeline`'s own
`try/except`. **The line FR-018 actually rests on was unmeasured** — which is precisely why a
dead Groq model went unnoticed from 2026-09-21 to 2026-09-23 while the AI panel was silently
absent from every single search.

### Added

- **`verify_agent.py`** — `_DownGroq`, a client double whose completion call raises, standing
  in for TC-009's "Groq API down (mocked)". Asserts `RAGPipeline.run` returns `None` rather
  than raising. Plus `_BlankGroq` for the second route to an empty panel: a call that
  *succeeds* and returns whitespace, which without `text or self.fallback()` would render an
  empty highlighted band rather than no band. Plus the no-jobs path, which must cost no call.
- **`verify_agent.py`** — an outage raises no `warning` banner either. The banner belongs to
  a failed *source*, not a failed LLM; a Groq outage costs the explanation and nothing else.
- **`verify_routes.py` §7b** — TC-009's remaining claim is about the *page*, so it is asserted
  on rendered HTML: the band is absent, the ranked cards and their decision groups still
  render, no error banner, no traceback. Rendered directly rather than POSTed, so it costs no
  Adzuna quota and no Groq call.

### The control that makes it mean something

§7b also renders the **same page with a working reply** and asserts the band *is* present.
Without it, a template that never rendered the band under any condition would pass every
other assertion — the check would be measuring a typo in the section name rather than the
fallback. A one-sided assertion about something being absent is usually worth this little.

`verify_all.py --offline`: 362 → **371 passed, 0 failed**. All 22 test cases now have at
least one assertion except TC-007 (autocomplete) and TC-015 (filters), both unbuilt.

---

## 2026-09-23 — Per-user source selection: the country field

The eligibility badges shipped earlier the same day made the problem visible; they did not
solve it. A user in Pakistan still saw a page where 22 of 28 listings were UK-local roles,
correctly labelled and still useless to them.

### The rule

> **Only query a source that can serve this user.**

One rule, no country-specific branches anywhere. `pk` is not excluded by us — Adzuna is a
country-market API and `jobs/pk/search` **returns 404**, so there is no endpoint to call.

### Measured — Adzuna's country list, because Adzuna does not publish it

Their docs show only `gb`. Probed every candidate on 2026-09-23:

- **19 markets returned HTTP 200:** `at au be br ca ch de es fr gb in it mx nl nz pl sg us za`
- **404:** `ru`, `se`, `pk`, `ae`, `ng`

Recorded in `config.ADZUNA_COUNTRIES`. Re-measure if searches start failing.

### Result, measured end to end on "junior frontend developer"

| Profile | Jobs | Applicable | Adzuna | Outage banner |
|---|---|---|---|---|
| `pk` | 32 | **31** | **0 — skipped** | none |
| `gb` | 34 | 31 | 2 local | none |

A Pakistan-based user goes from 6 applicable jobs to 31. **A UK user is not worse off** — they
gain the worldwide remote listings and keep their local ones.

### Added

- `config.COUNTRIES` — 196 sovereign states, ISO 3166-1 alpha-2.
- `config.ADZUNA_COUNTRIES`, `config.DEFAULT_ADZUNA_COUNTRY`.
- `adapters.api_client.adzuna_market(country)` — the single place the "can this source serve
  this user?" question is answered.
- `country` on the user document, on the registration form and on the profile form.

### Changed

- `fetch_variant` takes `country` and **skips Adzuna entirely** when it has no market for it.
- `_fetch_adzuna_raw` interpolates the market into the URL.
- `JobSearchAgent` reads `country` from the user context in both `run()` and `build_feed()`.

### Three decisions that are load-bearing

1. **A skipped source is in NEITHER `failed_sources` NOR `empty_sources`.** Both halves matter.
   `failed_sources` drives TC-018's outage banner, which would otherwise have fired on *every
   search a Pakistan-based user ran* — Adzuna did not fail, it was never asked. `empty_sources`
   marks a fetch as degraded so it is not cached, which would have made those users bypass the
   60-minute cache forever. Asserted offline.
2. **The job cache key now includes the market.** Without it, two users searching identical
   words — who now genuinely get different result sets — would have been served whichever of
   them searched first. This would have been a silent, intermittent, near-undebuggable bug.
3. **A missing country keeps the old behaviour.** If absent meant "skip Adzuna", every
   existing account would have silently lost most of its results on deploy — a data migration
   wearing a feature's clothes.

### Why the full country list rather than a curated ten

A curated list has no principled answer to "why these ten?", and arbitrary choices are what a
viva pulls on. The 19 Adzuna markets are a real, measured boundary, so the select is grouped by
it — "Local + remote jobs available" and "Remote jobs only" — and the dropdown tells the user
what they will get before they search. A `supported / other` flag was rejected for the same
reason `JobCard.location` had to be split: a sentinel would collapse Pakistan, Nigeria and the
UAE into one value and would have to be undone the moment region matching is attempted.

### Also fixes

`config.ADZUNA_COUNTRY` was read from `.env` and consumed by nothing, because `gb` was
hardcoded in the URL. Setting it changed nothing and reported no error. Now removed as dead
config — the market comes from the user.

### Framing note for the report

For a user in a country Adzuna does not cover, **every job the system can offer is remote**, so
the product is a semantic search engine for *remote roles open to your location*. That is a
real narrowing of the SRS's scope and the write-up must say so — but it is a sharper project
than a general job board, and geographic eligibility is something the large boards handle
badly.

`verify_all.py --offline`: 347 → **362 passed, 0 failed**.

---

## 2026-09-23 — Geographic eligibility: jobs the seeker can actually apply for

Found by using the app as a real user: every listing on the page was a UK role, and nothing
on the card said so. A job that will reject you on location is not a result.

### Decided — eligibility is a property of the USER, not of the app

Nothing is hardcoded to any country. The app stays general; it simply stops showing every
user the same UK-centric list. This extends the project's personalisation claim from
ranking into retrieval, which is a stronger thing to defend than a country filter.

### Decided — Jobicy added as a third source, after measuring the alternatives

| Source | Jobs/query | Eligibility field | Search works | Eligibility filter |
|---|---|---|---|---|
| Adzuna | 10–77 | none — concept absent | yes | no |
| Remotive | **18, always** | `candidate_required_location` | **no** | no |
| RemoteOK | 100 | `location`, 34% blank | untested | no |
| **Jobicy** | up to 100 | `jobGeo` | **yes** | **yes** (`geo=anywhere`) |

Remotive's `category` parameter is ignored exactly like `search` — 18 jobs for every value
tested and for no parameters at all. Its pool cannot be grown. Jobicy is the only free
source that both searches and filters eligibility server-side. Free, no key, no card.

### Added

- `adapters/api_client._fetch_jobicy_raw` — Jobicy with `geo=anywhere`. Its `tag` is an AND
  match that collapses on long queries ("entry level marketing no degree" → 0, "marketing"
  → 17), so the work-type and stopword stripping already written for Adzuna is applied
  first, with one retry on the longest token. Two HTTP calls per variant, capped.
- `adapters/api_client._filter_jobicy_level` — the same `_wrong_level` rule Remotive uses.
  Jobicy filters geography server-side but not seniority.
- `JobCard.candidate_location`, `JobCard.eligibility`, and `models.job_card.remote_eligibility`.
- Eligibility badge on every card in `index.html` and `feed.html`.
- `JobSearchAgent.rag_candidates` — chooses which jobs the AI panel explains.

### Changed

- **`JobCard.location` no longer carries two meanings.** Adzuna's "London" (where the job
  IS) and Remotive's "Worldwide" (where the candidate MAY LIVE) were both written into
  `location` and rendered in the same slot. That conflation is why this was invisible.
- **`RAGPipeline.build_prompt` states eligibility per job** and is told to prefer
  unrestricted roles and name any restriction plainly.
- **The AI panel now explains the best five the seeker can act on, not the top five by
  score.** The prompt change alone fixed nothing: measured on "junior software engineer",
  all five top-ranked jobs were UK-local and the four worldwide ones ranked sixth and below,
  so the prompt had nothing applicable to prefer. `rag_candidates` re-partitions the top of
  the list. **Nothing is re-scored** — the ranked list below the panel is still ordered
  purely by similarity plus the category boost.

### Measured

On "junior software engineer": jobs applicable from anywhere went from **1 to 5** of 28, and
all 28 cards are now labelled. All five jobs reaching the AI panel are unrestricted, and the
model writes "no geographic restrictions, so you can apply from anywhere".

### Four eligibility states, and why "unknown" is one of them

`open` / `regional` / `local` / `unknown`. Deciding whether `APAC` includes a given user is
a judgement the code is in no position to make, and getting it wrong costs the seeker a
wasted application. Anything not positively unrestricted is `regional`, and the raw text is
shown so the user can judge. Same lesson as the `ui` substring bug below.

### Not done, deliberately

- **Adzuna is not skipped for users outside its markets.** The rule would need the profile's
  country, and `location` defaults to the string "remote" for every user — so it would skip
  Adzuna for everyone and destroy the precision@5 baseline. Needs a country selector on the
  profile form first.
- **Remotive is labelled, not filtered.** Filtering to worldwide-only would drop its Europe
  and UK listings and hurt a UK user, which conflicts with keeping the app general.

### Known gaps

- `verify_live.py` has no Jobicy coverage and would not notice it going down. Its check
  "no cached entry was built from Remotive alone" is weaker with a third source, though the
  real guard in `agent.py` (`"Adzuna" in empty_sources`) still holds.
- The profile's **Preferred Location is still dead data** — collected, validated, stored,
  and read by nothing. `enrich_query` uses skills and level only.

---

## 2026-09-23 — Groq retired the replacement model too (second forced substitution)

`groq/compound-mini` began returning `404 ... does not exist or you do not have access to
it`. No `groq/compound-*` and no Llama chat model remains on the account. This is the
**second** forced substitution on the same line of the SRS and needs supervisor sign-off.

**It had been failing silently since 2026-09-21.** `verify_intent.py` reported TC-019 as
"SKIPPED — Groq unreachable", which reads like a network fault and was treated as one for
two sessions. It was a dead model. The AI Recommendations panel was simply absent from every
search, and FR-018's fallback worked so well that nothing else looked wrong.

### Changed

- `GROQ_MODEL` → `openai/gpt-oss-120b`.
- `parse_intent` `max_tokens` 300 → 600; `RAGPipeline.run` `max_tokens` 700 → 1200.

### The replacement is a reasoning model, and that is not a detail

gpt-oss models spend hidden reasoning tokens before emitting content, and `max_tokens`
covers both. Measured:

- **gpt-oss-20b at the old intent budget of 300**: 99 reasoning tokens, JSON truncated, no
  parseable object — so `parse_intent` fell back to keywords and **query expansion silently
  stopped happening**. TC-019 and TC-021 both broken with the app still appearing to work.
  That is the failure mode to watch for whenever this constant changes.
- **gpt-oss-120b at the old RAG budget of 700**: 475 reasoning tokens and
  `finish_reason="length"` — recommendations cut off mid-sentence.

Candidates measured on four queries: `qwen3.8-27b` spends 0 reasoning tokens and would need
no budget change, but reads "something creative I can do from home" as `other` and fails
TC-019; `gpt-oss-20b` reads "junior software engineer" as `engineering`; `gpt-oss-120b` gets
all four right. The cost is latency — 250–475 reasoning tokens per call, twice per search.
`qwen` is the fast fallback if the demo drags.

**TC-019 now passes. `verify_intent.py` 71 → 76, 0 failed.**

---

## 2026-09-22 — Category classification rewritten after reading the live user data

Four of the five jobs three real users had saved were filed as **`design`** when every one
was a software job, so two accounts carried a design preference nobody had expressed — and
the For You feed then keyword-searched "design" and returned genuine graphic-design jobs.

### The cause, in two halves

1. **`ui` is a design hint and hints were matched as bare substrings**, so it matched inside
   s-ui-ted, b-ui-lt and req-ui-rements. Close to every advert in existence contains one of
   those.
2. **`design` is listed before `technology`** and the first match won, so design took it on
   one incidental hint even where technology matched four real ones.

One job, "Junior Software Engineers", was misfiled by the word **"design"** appearing
legitimately in *"you will actively design, build, and integrate"* — that one needed
title-priority and hint-counting, not word boundaries. A single fix would not have caught
both.

### Changed — three rules replaced "first substring hit in table order"

1. **The title decides.** The description is consulted only when the title names no category.
2. **Word-boundary matching.** Hints of three characters or fewer (`ui`, `ux`, `seo`) must
   match a whole word; longer ones match at a word start, so the deliberate stems
   (`copywrit`, `illustrat`, `programm`, `journalis`) keep working.
3. **Most hint matches wins.** `CATEGORY_HINTS` order is now only the tie-break.

`CATEGORY_HINTS` itself is unchanged. Patterns are compiled once at import.

### Verified

14 regression checks added to `verify_agent.py` using the five real saved jobs and the
description excerpts recorded from `job_cache` before its TTL expired them. **They failed
first, then passed** — 8 failures before the fix, 0 after. Spot-checked one title per
category: all 23 correct, including `Account Executive` → `sales` on the order tie-break.
`verify_agent.py` 129 → 143.

### Data note

The three affected user documents were **deleted by the user on 2026-09-23**. Fixing the
classifier does not repair history, and no migration was written.

---

## 2026-09-22 — Profile "View" link went nowhere

`DatabaseManager._record_decision` renames a job's `url` to `source_url` on the way into
Mongo, but `profile.html` asked for `job.url`. Jinja renders an undefined as `""`, and an
empty URI reference resolves to the current document — so "View" reloaded `/profile` instead
of opening the advert.

### Fixed

- `templates/profile.html` reads `job.source_url`, and gained `rel="noopener noreferrer"`.
- One assertion in `verify_routes.py`, on the full `href="..."` rather than the bare URL —
  the URL alone would still be found if the attribute were empty and the link text held it.

`verify_routes.py` 57 → 58.

---

## 2026-09-21 — The For You feed (M3 complete)

M3's last task. `get_top_categories` and `rejected_jobs` had been green in `verify_db.py` since
M1 and nothing read them back; `/feed` rendered a placeholder string. The feed is now built, and
it is the only screen where the learned preference is the entire input.

### Decided — the feed fetches live, through the existing 60-minute cache

The open question `docs/PROJECT_STATUS.md` carried was whether the feed would spend Adzuna quota
on every visit. It fetches live, and the quota concern dissolves on inspection: the variant
strings are **category names**, a closed set of 13, so every user and every visit shares the same
cache keys. All feed traffic across the whole app costs at most ~13 Adzuna calls per hour against
a 250/day budget. A user with no positive scores returns before any fetch at all.

### Decided — a user with no preferences gets an empty feed, not a profile fallback

Falling back to the profile's skills would keep the feed populated from day one, but it would
give "why do two users see different feeds?" two possible answers instead of one. TC-014 exists
to rule that ambiguity out, so the empty state stays empty.

### Added

- `JobSearchAgent.build_feed(user_id)` — the second entry point beside `run()`. Reuses
  `_fetch_cached_variant`, `deduplicate`, `classify` and `rank` unchanged; adds only the
  category filter and the ranking-without-a-query step.
- `JobSearchAgent._filter_feed` — keeps jobs whose **self-assigned** category is in the user's
  top categories and drops any `job_id` in `rejected_jobs`. TC-012 says rejected categories are
  *absent*; "ranked last of twelve" is still present, so ranking alone would not satisfy it.
- `core.agent.match_band()` and `MATCH_BANDS` — FR-019's Top Match / Great Match / Worth a Look
  badge. The thresholds live in Python rather than Jinja so a verify script can assert on them.
- `FEED_CATEGORIES`, `FEED_LIMIT`, `MSG_FEED_EMPTY`, `MSG_FEED_NONE_FOUND`.
- `docs/ARCHITECTURE.md` § For You feed request flow.

### Changed

- `ui.feed` calls `build_feed` and renders the result; the M3 placeholder is gone. The route
  stays as thin as `search()` — no filtering and no policy in the controller.
- `feed.html` renders the match badge, and the same `error` / `warning` banner pair `index.html`
  uses, so a feed built while a source is down says so above the cards rather than instead
  of them.
- `verify_agent.py` 97 → 129 checks: TC-012 (writing shown, tech absent, rejected job absent),
  TC-014 (two users' feeds are **disjoint**, not merely different), the no-scores case proved by
  call counters on the stubs, the match bands, and the category-score tie-break.
- `verify_routes.py` gains `/feed` checks. They run **before** the saves in that script, while
  the throwaway user still has no positive score, so `build_feed` returns without fetching and
  the script stays free of Adzuna quota.

### Honesty note for the report

The feed runs a keyword search for each of the user's top category *names* and re-ranks what
comes back against their profile. It does not discover jobs matching their taste. Same recall
ceiling as the search path — the docstring, the architecture doc and the report all say so in
those words.

### Still hand-picked, TODO(M4)

`FEED_CATEGORIES = 3`, `FEED_LIMIT = 12` and the 85 / 65 match-band thresholds have no more
justification than `CATEGORY_BOOST` does. `normalized_score` is relative to the best match in
the feed, so the top card is a "Top Match" by construction — say that before being asked.

---

## 2026-09-21 — Job categorisation, and the save/reject learning loop

M3's first task. `DatabaseManager.save_job` / `reject_job` had been written and green in
`verify_db.py` since M1, but nothing above them existed: no category to score, no routes, no
buttons. All three are now built and the loop runs end to end.

### Decided — how a job's category is derived

This was the open question both `docs/PROJECT_STATUS.md` and `config.py` flagged as *must be
settled before M3*. **Neither API taxonomy is used.** Adzuna tags jobs with its own categories
and Remotive with a different set; reconciling them meant two mapping tables at different
granularities, with no answer for a job whose source omits the field. Instead every job —
whichever source returned it — is classified locally from its own title and description against
a single `config.CATEGORY_HINTS` table. One rule for both sources, so a user's score for a
category cannot fragment according to which API happened to return the job.

Stated plainly for the report: this is **substring keyword matching over job text**, first
matching key wins, and the order of `CATEGORY_HINTS` is the tie-break rule. A job whose title
and opening paragraph name no category word lands on the parsed intent's category, or `"other"`.
It is not classification by meaning and must not be described as such.

### Added

- `config.CATEGORY_HINTS` — the category vocabulary, promoted out of `intent_parser` so the
  query path and the job path match against one table. A query parsed as `writing` and a job
  classified as `content` would have incremented different keys and fragmented the loop.
- `core.intent_parser.classify_category(text, fallback)` — used for both. The fallback is
  validated against `CATEGORIES` too, because it reaches a MongoDB field path via `save_job`.
- `JobSearchAgent.classify` — new pipeline step 6b, between dedupe and rank.
- `POST /save_job` and `POST /reject_job` in `controllers/ui_controller.py`, returning JSON.
- `static/js/decisions.js` — one delegated listener, `fetch`, button flips in place. No
  framework. Form-encoded body so the existing `check_csrf()` works unchanged.
- `verify_routes.py` — 46 checks. TC-010/011/013 asserted through the HTTP routes, not just the
  data layer, plus the CSRF path, the category whitelist, the JSON contract and the rendered
  card markup. Registered in `verify_all.py`.

### Fixed

- **`feed.html` posted `category="{{ job.source | lower }}"`** — the source name, e.g. `adzuna`,
  which is not in `CATEGORIES`. Every click would have raised `ValueError` out of `_score_path`
  and reached the user as a 500. It was unreachable only because the feed renders no jobs yet.
  Both templates now use the same markup, and the route returns a 400 rather than a 500 for a
  bad category.
- **The category boost was dead code in production.** `JobCard.category` was `""` for every job,
  so `similarity + (category_score × 0.02)` scored 0 on the boost term for every listing.
  `verify_agent.py` proved the mechanism by passing categories in directly; it now proves it
  through the full pipeline.

### Verified

- **277 assertions green offline**: verify_db 27, verify_agent 97 (was 57), verify_auth 31,
  verify_routes 46, verify_intent 76.
- The button behaviour was driven in a real browser against the running server with `fetch`
  stubbed: a success flips the label to "Saved", disables both buttons and posts the right
  form-encoded body; a 400 re-enables them and shows the server's message. No console errors.

### Still to do in M3

The For You feed (TC-012, TC-014). It depends on these categories existing.

---

## 2026-09-20 — A verification suite that can catch a live-API change

Both defects found today were invisible to `verify_agent.py`, which passed 57/57 throughout
because it is offline by design and stubs the fetch. A green suite said nothing about whether
a live source was behaving. Two scripts close that gap and make the whole thing one command.

### Added
- `verify_live.py` — 28 checks against the **real** Adzuna, Remotive, Groq and Atlas, using
  Flask's test client so it needs no running server and no new dependency, but renders the real
  templates. It asserts the two API contracts the project now depends on (Adzuna returns results
  for a work-type-laden query; Remotive still ignores `search`), then the behaviours that broke:
  a beginner query returns no senior titles, a senior query still does, gibberish reaches
  `MSG_NO_RESULTS`, and no cached pool was built from Remotive alone. If Remotive ever starts
  honouring `search` again, the check fails loudly and says to revisit the local filter.
- `verify_all.py` — runs all five in cost order, cheapest first, and prints one table and one
  verdict. `--offline` skips `verify_live.py`, the only script that spends Adzuna quota. It
  distinguishes a **crash** from a failed check and prints the traceback, because a script that
  never reaches its summary would otherwise be counted as zero failures.
- Both reconfigure stdout to UTF-8. The Windows console is cp1252 and cannot encode the em
  dashes these scripts print; an encoding crash halfway through a check run is a uniquely
  unhelpful failure.

### Totals
**249 assertions green**, in about 100 seconds: verify_db 27, verify_agent 87, verify_auth 31,
verify_intent 76, verify_live 28.

### Note
One check in `verify_live.py` was wrong on first run and is worth remembering: it tried to prove
Adzuna's raw AND behaviour by calling `_fetch_adzuna_raw`, which is the function that applies the
work-type stripping — so it was testing the fix with the fix applied. Re-measuring that raw
behaviour needs an unmodified HTTP call, and `adapters/api_client.py` is the only module allowed
to import `requests`, so the check now asserts the fix's effect instead and the raw measurement
stays recorded here.

---

## 2026-09-20 — Search accuracy: candidate generation, not ranking

Reported symptom: a beginner/entry-level software query, from a profile set to **mid level**,
returned **senior** jobs. The ranker was not at fault — it ordered correctly a pool that
contained nothing else. Diagnosed from the user's own six cached `job_cache` entries.

Root cause chain, all four links now covered by checks:

1. Groq expanded the query into three variants and **all three kept the word "remote"**.
2. Adzuna's `what=` is an AND keyword match. Measured: `junior software engineer` → 77 results;
   `remote junior software engineer` → **0**. One work-type word empties the search.
3. Adzuna reports that as **HTTP 200 with zero results** — not a failure — so `failed_sources`
   stayed empty and **no warning banner was shown**. The page looked healthy.
4. Remotive ignores `search` and contributed its constant ~20-job feed, 11 of them senior. The
   pool was therefore 100% Remotive senior jobs, and was then **cached for 60 minutes**.

`verify_agent.py` goes 57 → 87 checks; the suite total is **221/221**, plus 20 live checks
against the running server.

### Added
- `config.WORK_TYPE_HINTS` and `config.QUERY_STOPWORDS`. `WORK_TYPE_HINTS` moved out of
  `_parse_intent_keywords`, because `adapters/api_client.py` now strips the same terms and the
  two must not drift. Same precedent as `WORK_TYPES`/`EXPERIENCE_LEVELS` on 2026-09-19:
  `config.py` imports nothing from the project, so an adapter reading it cannot cycle.
- `api_client._adzuna_keywords` — strips work-type words from the keyword string, longest term
  first so "work from home" goes before "from". Falls back to the original if stripping empties
  it, so "remote work" cannot become an empty search.
- `api_client.ADZUNA_WORK_TYPE_PARAMS` — `full-time → full_time=1`, `part-time → part_time=1`,
  `freelance → contract=1`, all verified live against a control: a made-up parameter returns
  HTTP 400, which is what proves these three are honoured rather than ignored. **"remote" maps
  to nothing on purpose** — Adzuna has no remote filter (`where=remote` returns 0), so remote
  intent is served by removing the word and by Remotive, which is an all-remote board.
- `api_client._filter_remotive` — Remotive is now **fetched then filtered locally**. A job is
  kept only if a query word matches its **title**, allowing an inflected ending so "engineer"
  matches "Engineering" while "car" does not match "Cardiac" (a bare prefix match was tried
  first and did exactly that). Title only, not description: it scored the same (7 kept vs 8)
  and a description is a long HTML advert whose boilerplate matches nearly anything.
- `api_client._wrong_level` — when `parse_intent` found a level, Remotive titles contradicting
  it are dropped in both directions. Needed on top of the title filter because "Senior Golang
  Developer" matches the token "developer" from an expanded variant, so it passes the topic
  test at exactly the wrong level. **Keyword-based because the embedding cannot do this**:
  cosine similarity rates "junior developer" against "senior developer" at **0.806**.
  Applied to Remotive only — Adzuna ran a real search, so its results are earned.
- `empty_sources` in `fetch_variant`'s return. A source that **failed** and one that succeeded
  but returned **nothing** are different events, and collapsing them is what hid this bug.

### Changed
- `JobSearchAgent` passes `intent["work_type"]` and `intent["experience"]` down to the fetch.
  Groq has been extracting both correctly and the pipeline discarded them.
- `enrich_query(query, context, experience=None)` — a level stated in the query overrides the
  profile's. A profile saying "mid level" against a query saying "beginner" put two conflicting
  levels in one vector; measured, that narrowed the junior-vs-senior similarity gap by about a
  third. The **two-argument call is byte-identical**, so the TC-016 wording is untouched.
- **A pool built without Adzuna is no longer cached.** Adzuna is the only source that genuinely
  searches, so a pool without it is the degraded state, and pinning it for an hour is what made
  this bug survive every retry. A Remotive-filtered-to-zero pool *is* still cached — that is the
  filter working, and refusing it would spend Adzuna quota needlessly.
- `FetchRecorder` in `verify_agent.py` tracks the real `fetch_variant` signature and return
  shape. A double that keeps an older interface than the code it stands in for stops testing
  anything and starts hiding the difference.

### Fixed
- **`MSG_NO_RESULTS` is reachable again.** "No jobs matched that search." had been dead code in
  production since Remotive broke, because the pool was never empty. A gibberish query now
  renders zero cards and the message; it previously rendered 17 senior jobs.
- The six poisoned `job_cache` entries were cleared. They held Remotive-only pools for the
  user's variants and would have outlived the fix by an hour.

### Measured after
- `beginner level software engineer` → top 5 all *Junior Software Engineer / Software Developer
  (Entry Level)*, **0/5 senior**, through the real rendered page.
- `senior python developer` → **5/5 senior**, so this is a level filter and not a junior bias.
- An entry-level query keeps **0 of the 11** senior-titled jobs in the live Remotive feed.
- `nurse` and `graphic designer` keep **0** Remotive jobs; `freelance copywriter` keeps exactly
  "Freelance Copywriter".

### Honest limitations
- Remotive is **fetched then filtered locally**. It is not an API keyword search any more, and
  the report and any viva answer must say so.
- This improves the candidate pool; it does not improve *retrieval*. The recall ceiling in
  `README.md` is unchanged.
- Experience-level accuracy is **not solved**. It rests on title keywords, not on the embedding,
  which cannot separate the levels. FR-021's Entry/Mid filter chips (TC-015, M4) remain the
  spec'd mechanism for explicit control.
- The spec'd scoring formula `similarity + category_score × 0.02` is **untouched**. No new
  coefficient was introduced, deliberately — there is already one hand-picked number to justify.

---

## 2026-09-20 — M2 route move: the app finally runs the agent

`JobSearchAgent` was proven on 2026-09-19 but nothing called it — the live route still ran the
old inline pipeline, so query expansion (TC-021) and the partial-source banner (TC-018) passed
in `verify_agent.py` and did not happen in the running app. `ui_controller.search` now serves
`/` and calls `agent.run()`. This closes the inline-route deferral recorded in
`docs/ARCHITECTURE.md` § Module layout and is the last build work in M2.

**Verified.** All four verify scripts pass — `verify_db.py` 27, `verify_auth.py` 31,
`verify_intent.py` 76 (live Groq call), `verify_agent.py` 57 — **191/191**. Then a live run
against the running dev server with real Adzuna, Remotive, Groq and Atlas: 32 ranked cards with
match badges and a populated AI panel, `GET /` with no error banner, TC-017 on an empty submit,
no raw dicts in the page, and `job_cache` holding one document per query *variant*, which is the
first direct evidence that query expansion runs in the live app.

### Added
- `controllers/ui_controller.search` — serves `/` for GET and POST. Thin by construction: check
  CSRF, call `_agent().run(current_username(), query)`, render the dict. It does not read the
  profile, strip the query or decide what an empty result means — the agent owns all three.
- `_agent()` beside the existing `_db()`, reading `current_app.config["AGENT"]`. Same
  indirection, same reason: a controller importing `app` is a circular import.
- `_blank_page()` — returns the identical key set `JobSearchAgent.run()` returns, so a GET and
  a CSRF-rejected POST hand the template exactly the variables a completed search does.
- `app.config["AGENT"] = JobSearchAgent(db, engine, rag)` in `app.py`. The one place the three
  collaborators are assembled, which is the point of taking them as constructor arguments.
- `index.html` renders `error` and `warning`. The agent has returned both on every exit path
  since 2026-09-19 and the template rendered neither. `warning` sits **above the result list,
  not instead of it** — that is the TC-018 distinction between "come back later" and "search
  for something else". They are template variables rather than flashed messages because
  `flash()` exists to carry a message across a redirect and this renders in the same request;
  it also avoids the flash block's category mapping, which renders anything that is not
  `error` as `alert-success` and would have shown a warning in green.

### Changed
- `GET /` deliberately does **not** call `agent.run()`. With an empty query the agent returns
  TC-017's "Please enter a search term", so calling it on arrival would open the search page
  with an error banner on every visit. That message belongs to an empty *submit*.
- The search route stays on `/` rather than moving to `/search`. `verify_auth.py` measures
  TC-003 and TC-005 on that URL — 200 logged in, 302 anonymous — and a redirect hop would turn
  those 200s into 302s.
- The endpoint is now `ui.search`, so the six `url_for("home")` call sites moved with it:
  `controllers/auth_controller.py` (register x2, login x2) and the nav bars in `feed.html` and
  `profile.html`. Missing one would be a `BuildError`, i.e. a 500 on a page that renders today.
- `app.py` is wiring only — no routes, and the unused `flash`, `render_template`, `request`,
  `require_auth`, `current_username` and `fetch_all_jobs` imports are gone.
- `requirements.txt` — the `requests` comment named `job_fetcher`, a module renamed to
  `adapters/api_client.py` on 2026-09-13.

### Removed
- `fetch_all_jobs`, `fetch_adzuna_jobs` and `fetch_remotive_jobs` from
  `adapters/api_client.py`. The inline route was their only caller. All three returned `[]` for
  a rate limit and `[]` for a genuine zero-result search alike, which is exactly the ambiguity
  `fetch_variant`'s `failed_sources` was added to resolve, and they still carried the
  pre-`JobCard` inline normalising — the code that once rendered Python dicts into the page.
  Preserved in git history.
- The inline `home()` route from `app.py`.

### Known gaps
- **Remotive has stopped honouring `search`.** Found by the live run, which is exactly what an
  offline verify script cannot find. The endpoint returns the same fixed 17-job list for every
  query — confirmed with `nurse`, `accountant`, `qwertyuiop` and with no parameters at all — and
  ignores `limit` too. Consequences: one of the two sources contributes a constant,
  query-independent 17 jobs to every search; `MSG_NO_RESULTS` is unreachable in production
  because the pool is never empty; a gibberish query renders 17 irrelevant cards with high match
  badges; and M4's precision@5 would be measured over polluted candidate pools. Not fixed — the
  SRS names Remotive as a source and the options are design decisions. Written up with three
  options in `docs/PROJECT_STATUS.md`.
- The old route flashed *"Could not load your profile; showing unpersonalised results."* when
  `get_user_context` failed. `JobSearchAgent.run` catches that, prints, and continues
  unpersonalised — correct, but now silent to the user. Surfacing it means adding a key to the
  agent's return dict, which breaks the "same keys on every exit path" invariant
  `verify_agent.py` asserts. Left as a gap rather than widening M2.
- The agent logs with `print`, not `current_app.logger`, because `core/` must not import Flask.
  That is a layering consequence, not an oversight — be ready to say so.

---

## 2026-09-19 — M2 search pipeline (`JobSearchAgent` + `JobCard`)

The pipeline is assembled. `core/agent.py` and `models/job_card.py` are implemented and
`verify_agent.py` passes 57/57 with no live calls at all. TC-021 is now genuinely covered:
`parse_intent` has been producing query variants since the previous entry, and as of this one
something finally consumes them. `verify_intent.py` (76), `verify_auth.py` (31) and
`verify_db.py` (27) all still pass — 191 checks green in total.

The search route in `app.py` is deliberately untouched and still serves. Moving it into
`ui_controller.search` is the next task.

### Added
- `core/agent.py` — `JobSearchAgent`, the orchestrator. Reads the profile, parses intent,
  enriches and encodes the query, fetches once per variant, unions and deduplicates, re-ranks,
  and hands the top 5 to `RAGPipeline`. Returns one dict with the same keys on every exit
  path, so the route never has to work out which branch produced its result.
- `models/job_card.py` — one place where an Adzuna/Remotive field-shape difference is resolved.
  `make_job_id` is a SHA-256 of lowercased, stripped `title|company`, truncated to 16 hex
  characters. Lowercasing is what makes TC-022 work: a syndicated listing arrives at the two
  APIs with different casing, and a byte-exact comparison would call the copies different jobs.
  The `|` separator stops `("Data", "Xco")` and `("DataX", "co")` hashing alike.
- `adapters/api_client.fetch_variant` — returns `{"jobs": [...], "failed_sources": [...]}`.
  This is the signal TC-018 needed and did not have: every existing fetch function returns
  `[]` for a 429 and `[]` for a genuine zero-result search, so the caller could not tell
  "come back later" from "search for something else". The two now give different messages.
- The 60-minute job cache is in use for the first time. `cache_get`/`cache_put` existed and
  were dead code. Keyed on a SHA-256 of the **variant** string rather than the user's query,
  so two searches that expand onto a shared phrasing reuse one fetch. Three variants against a
  250/day Adzuna budget is the quota risk `PROJECT_STATUS.md` has been flagging. A *partial*
  fetch is never cached, or an outage would outlive the API's recovery by an hour.
- `verify_agent.py` — 57 checks, entirely offline. Every collaborator is a double, which is
  the whole reason `JobSearchAgent.__init__` takes them as arguments. Covers TC-006, TC-016,
  TC-017, TC-018, TC-021, TC-022, the RAG fallback, both cache paths, and JobCard against
  missing nested objects. Three of the cases are only provable with doubles: TC-017 asserts
  that **no** call happened, which needs a counter rather than a return value; TC-018 needs
  Adzuna to fail on demand; TC-006 needs similarity scores fixed in advance so the expected
  order is known.

### Changed
- Deduplication now keys on `job_id` instead of a concatenated `title + company` string, and
  keeps the **first** occurrence. That is a decision, not an accident: `parse_intent`
  guarantees the user's own phrasing is `variants[0]`, so query expansion can only ever add to
  the candidate pool and never reorder what the user would have seen without it.
- Ranking sorts on a new `final_score` (similarity + category boost) rather than on
  `similarity_score`, which is retained for display and for the M4 evaluation. `normalized_score`
  is unchanged in meaning — a percentage relative to the best match in that result set, not an
  absolute quality score.
- `docs/ARCHITECTURE.md` step 5 rewritten. The SDD's parallel fork is **not built**; fetching
  is sequential. Recorded as a deliberate deferral with its reasoning rather than left as a
  spec the code silently contradicts. The `Parallel fetch` row in `docs/LEARNING_LOG.md` now
  says the same thing — claiming it works in a viva when the code loops is the worst answer.
- `docs/LEARNING_LOG.md` — two rows added: **dependency injection / test doubles**, and
  **hashing as an identity, not as a secret** (SHA-256 does two unrelated jobs in this project
  and neither is security, which is the contrast with the password-hashing row).

### Fixed
- `JobCard.from_adzuna` tolerates a missing `company` or `location` object. The old inline
  normalising chained `.get` on the nested object and would raise when Adzuna omitted it —
  this is the descendant of the bug that once rendered Python dicts into the page.

---

## 2026-09-19 — M2 intent parsing (first M2 component)

`core/intent_parser.py` implemented. TC-019 and TC-020 pass; `verify_intent.py` runs 76 checks
with 0 failures, including a live Groq call. TC-021 (query expansion) is **not** covered yet —
`parse_intent` produces the variants but nothing consumes them until `JobSearchAgent` lands.

### Added
- `core/intent_parser.py` — `parse_intent` asks Groq for work type, experience, category and
  2–3 query variants as JSON; `_parse_intent_keywords` is the FR-018 fallback. Both paths
  return the identical dict shape, so `JobSearchAgent` never branches on which one ran; the
  `source` field records it for the report only.
- Validation separated from parsing. Groq's reply is treated as untrusted input: every field is
  checked for membership in a closed set on the way out, unrecognised values become `None` and
  an unrecognised category becomes `"other"`. The prompt steers the model; the membership test
  is what actually guarantees the closed set.
- `enrich_query` relocated from the inline search route in `app.py`, wording unchanged — that
  route is the code path already demonstrated to satisfy TC-016, so a rewrite would have
  invalidated the evidence.
- `verify_intent.py` — 76 standalone checks: canonical shape on both paths, TC-020 with the
  Groq client stubbed to raise, non-JSON and markdown-fenced replies, four hostile categories
  (`technology.$ne`, `$where`, `technology.admin`, `a.b.c`) all collapsing to `"other"`,
  variant capping and deduplication, TC-017's no-call-on-empty-query, and a live TC-019 call.
- `config.WORK_TYPES` and `config.EXPERIENCE_LEVELS`.

### Changed
- `WORK_TYPES` and `EXPERIENCE_LEVELS` moved from `controllers/ui_controller.py` to `config.py`;
  the controller now imports them. `intent_parser` must validate against the same sets, and an
  AI-layer module importing from a controller both inverts the SDD layering and deadlocks:
  `ui_controller` → `core.agent` → `core.intent_parser` → `ui_controller` fails with
  "partially initialized module". Reproduced before fixing. **The cycle was order-dependent** —
  it passed with the import at the bottom of the file and failed at the top, where PEP 8 puts
  it, which is why it needed fixing rather than avoiding. No behaviour change; `verify_auth.py`
  still passes 31/31.
- `docs/LEARNING_LOG.md` — two rows added: circular imports / partially initialized modules,
  and validating LLM output against a closed set.

### Known gaps
- TC-019's expected category is "creative", which is not in `CATEGORIES`. The prompt asks for
  the single closest member instead, and the check accepts `writing` or `design`; the live run
  returned `design`. Recorded here rather than widening the vocabulary, which is shared with
  the M3 scoring loop.
- The keyword fallback's synonym lists are hand-written and English-only. They are the crude
  path by design, but the coverage is not measured.

---

## 2026-09-19 — M1 auth, session and profile

The Atlas blocker cleared: `verify_db.py` now reaches the cluster and passes 27/27, so the
routes above the data layer could finally be built. TC-001 to TC-005 pass.

### Added
- `controllers/auth_controller.py` — `auth` blueprint: `/register`, `/login`, `/logout`,
  the `require_auth` decorator, and hand-rolled CSRF (`csrf_token`, `check_csrf`). The only
  module importing `werkzeug.security`. Passwords are hashed here; the database layer only
  ever receives a hash.
- `controllers/ui_controller.py` — `ui` blueprint with `/profile` (view **and** edit) and
  `/feed`. The feed is registered and protected now so TC-005 is testable; its ranking is
  still M3 and says so on the page rather than rendering a plausible-looking empty feed.
- `templates/login.html` — **it never existed.** The version at `5519a22` rendered it, so
  TC-003 and TC-004 would both have raised `TemplateNotFound`.
- `verify_auth.py` — 31 pass/fail checks over the real routes, real session cookie and real
  Atlas, via Flask's test client. No new dependency; mirrors `verify_db.py`.
- Profile edit form, and a nav bar plus flash-message block on `index.html`, which the other
  templates already assumed existed.
- `models/user.py` — `from_document` / `to_document` implemented.

### Changed
- CSRF is a per-session random token compared with `hmac.compare_digest`, not Flask-WTF.
  No new dependency, and the mechanism is explainable line by line.
- Login reports one message for an unknown username and for a wrong password, so the form is
  not a username oracle. `session.clear()` precedes granting a session, against fixation.
- The search route is now `@require_auth` and re-injects the user's skills and experience
  into the query text before encoding — restoring the TC-016 behaviour the simplified demo
  `app.py` had dropped.
- Minimum password length set at 8, enforced server-side and hinted in the form. The SRS says
  "strong password" without quantifying it; this is the quantification.
- `/profile` whitelists submitted **values** (experience level, work type) as well as the
  fields `update_profile` already whitelisted.

### Fixed
- **No fallback secret key.** `5519a22` used `os.getenv("SECRET_KEY", "fallback_secret_key")`;
  a known signing key lets anyone forge a session cookie for any username. A missing
  `FLASK_SECRET_KEY` is now fatal at startup.
- The env var name is `FLASK_SECRET_KEY`, matching `config.py` and `.env.example`. The old
  code read `SECRET_KEY`, which was never defined anywhere.
- `index.html` credited "Gemini AI" for the recommendations. It is Groq.
- Template `url_for` targets now name blueprint endpoints (`auth.login`, `ui.profile`, …).

---

## 2026-09-13 — M1 database layer built

### Added
- `adapters/db_manager.py` — `DatabaseManager`, the only PyMongo consumer in the project.
  Lazy connection (an Atlas outage no longer crashes startup), unique `username` index,
  `job_cache` TTL index, save/reject scoring, search history, top-category feed input.
- `verify_db.py` — standalone pass/fail check of every method against a throwaway user,
  asserting TC-001, TC-002, TC-010, TC-011, TC-012 and TC-013. Cleans up after itself.
  Includes `diagnose_connection()`, which reports which layer a failed connection stops at
  (DNS / TCP / TLS / auth) instead of blaming the credential by default.
- `config.CATEGORIES` — one closed category vocabulary, shared by intent parsing and the
  scoring loop, and the whitelist that makes the field-path injection impossible.
- `config.JOB_CACHE_TTL_MINUTES = 60` — spec value, configurable without a code edit.
- `docs/PROJECT_SPEC.md` now records TC-001 to TC-018 verbatim, extracted from
  `SRS_FORMATTED.docx`. They were previously only in the Word document.

### Changed
- **Deviation 5** — `rejected_jobs` stores `job_id` rather than job titles. Titles are not
  unique across employers, so title-keyed rejection would hide every job sharing a title.
  Field type is unchanged (still `Array<String>`). **Needs supervisor sign-off.**
- `save_job` / `reject_job` are a single atomic conditional update rather than read-then-write.
  The filter requires the job not already be in the list, so a repeat click matches no
  document and the score cannot move twice — TC-013 holds by construction, with no race.
- `core/intent_parser.py` imports `CATEGORIES` from config instead of defining an empty tuple.

### Fixed
- **Test-case ids in the stubs were wrong.** They were written from memory last session rather
  than from the SRS: save/reject were labelled TC-009/TC-011 when the real ids are TC-010/TC-011,
  duplicate-save is TC-013, dedupe is TC-022 not TC-017, and TC-008 is the RAG response, not the
  profile page. Corrected across `controllers/`, `core/agent.py` and `models/job_card.py`.
- **The recorded M1 blocker was misdiagnosed.** `PROJECT_STATUS` said the Atlas password needed
  resetting. A layer-by-layer probe shows DNS resolves, TCP connects in 0.1 s, but the TLS
  handshake on port 27017 times out and resets on all three shards, while TLS on :443 completes
  normally. Authentication happens after the handshake, so the credential was never reached.

### Known blocker
- No connection to Atlas from this machine on port 27017. The data layer is complete and every
  offline check passes; nothing past the ping can be verified until the port is reachable.

---


## 2026-09-13 — Restructured into the SDD Appendix B module layout

### Added
- `controllers/`, `core/`, `adapters/`, `models/`, `static/`, `tests/` packages. Every file
  named in SDD Appendix B now exists. Unimplemented ones are stubs that
  `raise NotImplementedError("M1"/"M2"/"M3")` with the covering TC ids in the docstring —
  not `pass`, which returns `None` silently and is how a stub reaches a demo unnoticed.
- `config.py` — all secrets read from `.env`, plus `validate()` which raises `ConfigError`
  naming every missing required variable at startup. A missing key now fails with its own
  name rather than as an opaque 401 from a provider later.
- `README.md` — setup, run, layout, and an honest statement of what the system does
  (re-ranks the keyword-search pool; does not retrieve past it).
- `adapters/db_manager.py` stub records the three defects in the deleted `models.py` that
  must not be reintroduced, and notes `datetime.utcnow()` is deprecated from Python 3.12.

### Changed
- `semantic_engine.py` → `core/semantic_engine.py`, `rag_pipeline.py` → `core/rag_pipeline.py`,
  `job_fetcher.py` → `adapters/api_client.py`, all via `git mv` so `git log --follow` keeps
  the debugging history these files carry. Contents unchanged.
- `app.py` — import paths only. The search route stays inline rather than moving to
  `controllers/ui_controller.py`; it is the one working code path, and the restructure was
  done as a pure move so identical behaviour could be verified. Deferred to M2 and recorded
  in `docs/ARCHITECTURE.md` § Module layout (as built).
- `MONGODB_URI` settled as the single spelling across code and docs; `MONGO_URI` retired.

### Removed
- `models.py`. It could not coexist with the `models/` package — Python resolves the name to
  one and the other silently vanishes — and was already dead code, imported by nothing. Its
  functions are carried forward as named stubs in `adapters/db_manager.py`. Preserved in git
  history at `5519a22` together with the auth routes M1 restores.
- Stale `__pycache__/`, compiled by Python 3.14.6 for modules that have since moved.

### Verified
- Baseline query "remote python developer" returns **24 deduplicated jobs from both Adzuna
  and Remotive**, ranks them (top: Python Developer / IB Talent Search, 0.674), and Groq
  returns a populated recommendation panel — identical to the 2026-09-13 pre-move baseline.

---

## 2026-09-13 — Search demo runs end to end

### Added
- `RAGPipeline` rebuilt against Groq, with `fallback()` satisfying FR-018: a Groq failure is
  caught and logged, the AI Recommendations panel hides, and the ranked results still render.
- `requirements.txt` — curated direct dependencies with pinned versions.

### Changed
- LLM model is now `groq/compound-mini`. Groq decommissioned Llama 3 mid-project; this is a
  forced substitution recorded in `docs/PROJECT_SPEC.md` § Deviations and **needs supervisor
  sign-off**. The model id is isolated in one constant, so a revert is one line.
- `app.py` calls `fetch_all_jobs()` instead of hitting Adzuna inline. This restores Remotive
  as a source, restores title+company deduplication, and keeps `requests` out of the route
  layer as the SDD requires.

### Fixed
- `rag_pipeline.py` had been overwritten with a byte-identical copy of `app.py`, so it imported
  `RAGPipeline` from itself and the app could not start at all.
- Adzuna returns `company` and `location` as nested objects. The inline fetch passed them to
  the template raw, which rendered them as Python dicts and left job links empty.
- Normalised-score divide is guarded — a zero or negative top similarity raised
  `ZeroDivisionError`, which would have shown a stack trace.
- `.gitignore` listed `models/`, which would have silently ignored the SDD's `models/` package.
- MongoDB URI username contained a Cyrillic `а` (U+0430) instead of Latin `a`, causing Atlas
  `bad auth`. Fixed; the DB user password is still outstanding.

### Removed
- Stale prototype scripts: the Gemini `rag_pipeline.py`, `test_groq.py`, `test_semantic.py`.

---

## 2026-09-11 — Project initialised

### Added
- PSB scaffold: project spec, CLAUDE.md, docs, commands and subagents.
