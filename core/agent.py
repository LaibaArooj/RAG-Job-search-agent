"""JobSearchAgent — orchestrates the search pipeline end to end.

Covers TC-006, TC-012, TC-014, TC-016 to TC-018 and TC-019 to TC-022.

The steps, per docs/ARCHITECTURE.md § Search request flow:

    1. get_user_context          - profile read before any API call
    2. parse_intent              - Groq call #1, keyword fallback
    3. enrich_query              - profile folded into the query text
    4. fetch, once per variant   - Adzuna + Himalayas via adapters.api_client
    5. union and deduplicate     - on job_id (SHA of title + company)
    6. classify                  - one category per job, core.intent_parser
    7. batch_encode + similarity - core.semantic_engine
    8. score and sort            - similarity + (category_score x 0.02)
    9. top 5 -> RAGPipeline.run  - Groq call #2, hides the AI panel on failure

Honest description of what this does: it RE-RANKS the candidate pool that keyword search
returned. It cannot surface a job the APIs never fetched. Query expansion at step 4 widens
that pool but does not remove the ceiling. Do not describe step 7 as "semantic retrieval",
and do not describe step 6 as anything more than keyword matching over the job text.

build_feed() is the second entry point, added 2026-09-21 for the For You feed. It shares
every step above except intent parsing and the RAG call: the user's top-scoring categories
stand in for the query, and there is no LLM call at all. See its own docstring for the
honest description of what it does and does not do.

Five decision points the implementation must handle: empty query, unauthenticated user,
intent-parse failure, no jobs returned from any variant, and RAG failure. The
unauthenticated case is handled one layer up by @require_auth, before the agent is reached;
the other four are handled here.

Two deliberate departures from the SDD, both recorded in docs/ARCHITECTURE.md:

1. **Fetching is sequential, not the SDD's parallel fork.** Three variants across two APIs
   is six sequential HTTP calls and the demo is correspondingly slow. Accepted for now: a
   threading bug that drops a variant's results intermittently would be far harder to
   notice, and far harder to defend, than a search that takes a few seconds.
2. **The 60-minute job cache is now used, keyed per VARIANT rather than per user query.**
   Three variants is three Adzuna calls against a 250/day budget. Keying on the variant
   means two different searches that expand onto a shared phrasing reuse one fetch.
"""

import hashlib

import config
from adapters.api_client import adzuna_market, fetch_variant
from core.intent_parser import classify_category, enrich_query, parse_intent

# Hand-picked coefficient weighting learned category preference against raw similarity.
# TODO(M4): this number has no justification yet. Either tune it during the precision@5
# evaluation or state it plainly in the report as a heuristic. Do not leave it unexplained.
CATEGORY_BOOST = 0.02

TOP_K = 5

# The sources that actually run a keyword search against the query, as opposed to returning a
# fixed list we filter ourselves. Since Remotive was removed on 2026-10-13 that is every source,
# but the set is kept: it is what stops a future fixed-list source from being cached as if it
# had answered the query (see _fetch_cached_variant).
#
# Used to decide whether a fetch is worth caching. Keep it in step with adapters/api_client.py
# -- a new source that genuinely searches belongs here, or its results will never be cached.
SEARCHING_SOURCES = frozenset({"Adzuna", "Himalayas"})

# --- For You feed -----------------------------------------------------------------
#
# How many of the user's highest-scoring categories the feed is built from, and how many
# cards it shows. Three categories is three fetches per COLD feed, but the variant strings
# are category names -- a closed set of 13 -- so the 60-minute job cache is shared by every
# user and every visit. All feed traffic in the whole app therefore costs at most ~13 Adzuna
# calls per hour, which is what makes a live-fetching feed affordable against a 250/day
# budget. That reasoning is the answer to the quota question docs/PROJECT_STATUS.md carried
# as an open blocker.
FEED_CATEGORIES = 3
FEED_LIMIT = 12

MSG_FEED_EMPTY = (
    "No personalised feed yet. Search for some jobs and save the ones you like."
)
MSG_FEED_NONE_FOUND = "Nothing new in your categories right now. Try a search instead."

# Match-quality bands for the badge on each feed card (FR-019). These thresholds are
# HAND-PICKED and have no more justification than CATEGORY_BOOST does -- they are read off
# normalized_score, which is already relative to the best match in this feed rather than an
# absolute quality measure, so the top card is always a "Top Match" by construction. Say
# that plainly rather than letting an examiner find it. TODO(M4): either tune these during
# the precision@5 evaluation or state them in the report as presentation-only labels.
MATCH_BANDS = ((85.0, "Top Match"), (65.0, "Great Match"))
MATCH_BAND_DEFAULT = "Worth a Look"

# The five messages the route can render. Kept here as constants because the verify script
# asserts on them and TC-017/TC-018 quote them; a typo in one place would pass a test that
# quoted the same typo.
MSG_EMPTY_QUERY = "Please enter a search term"
MSG_SOURCE_DOWN = "Job data temporarily unavailable"
MSG_NO_RESULTS = "No jobs matched that search. Try different wording."
MSG_PARTIAL = "Some job sources are unavailable, so these results are incomplete."


def _cache_key(variant, market=None, experience=None, work_type=None):
    """Hash a variant plus every input that changes what the fetch returns, into the cache _id."""
    # Hashed rather than used raw because the variant is user-influenced text and it becomes
    # a MongoDB _id. A hash is a fixed-length value from a fixed alphabet, so no query string
    # can collide with an operator or blow the key-length limit.
    #
    # The MARKET is part of the key as of 2026-09-23, and leaving it out would have been a
    # real bug: two users searching the same words now get genuinely different result sets --
    # a user in Pakistan gets no Adzuna listings at all, a user in the UK gets jobs/gb ones --
    # so a key naming only the variant would serve whichever of them searched first to the
    # other. Sharing stays wide, because the market is a closed set of 19 plus "none" rather
    # than anything per-user.
    # EXPERIENCE and WORK_TYPE joined the key on 2026-09-26, and leaving them out was a live
    # bug that verify_live.py caught: fetch_variant filters out wrong-level titles and passes
    # work-type flags to Adzuna, but a CACHE HIT bypasses fetch_variant entirely. So a pool
    # cached by a user with no stated level was served, unfiltered, to an entry-level user --
    # senior roles reappearing for exactly the person the filter exists to protect.
    #
    # The rule this is an instance of: everything that changes WHAT THE FETCH RETURNS has to
    # be in the key. Market was added for the same reason three days earlier. The cost is
    # sharing -- a pool is now reused only by users who agree on all four -- and that is the
    # right trade, because serving one user's filtered pool to another is silently wrong
    # rather than merely slower.
    scoped = "|".join([
        market or "none",
        experience or "any",
        work_type or "any",
        variant.strip().lower(),
    ])
    return hashlib.sha256(scoped.encode("utf-8")).hexdigest()


def match_band(normalized_score):
    """Map a normalized score onto the feed's Top Match / Great Match / Worth a Look label."""
    # Lives here and not in the template so the thresholds are one constant the verify script
    # can assert against. Jinja holding them would mean the only record of the rule was in
    # markup, where nothing tests it.
    for threshold, label in MATCH_BANDS:
        if normalized_score >= threshold:
            return label
    return MATCH_BAND_DEFAULT


class JobSearchAgent:
    """Runs the full search pipeline: parse intent, fetch, re-rank, then generate."""

    def __init__(self, db, semantic_engine, rag_pipeline):
        """Take the collaborators as arguments so each layer stays independently testable."""
        # Injected rather than imported. SemanticEngine loads an 88 MB model and
        # DatabaseManager opens a network connection; if this class constructed them itself,
        # no test of the ranking logic could run without both. verify_agent.py passes
        # doubles here, which is the only reason it is offline and repeatable.
        self.db = db
        self.semantic_engine = semantic_engine
        self.rag_pipeline = rag_pipeline

    # --- fetching -----------------------------------------------------------------

    def _fetch_cached_variant(self, variant, work_type=None, experience=None, country=None):
        """Fetch one variant, reading and writing the 60-minute job cache around the call."""
        key = _cache_key(variant, adzuna_market(country), experience, work_type)

        try:
            cached = self.db.cache_get(key)
        except Exception as e:
            # A cache read failure must cost a quota unit, not the search.
            print(f"job cache read failed for {variant!r}: {e}")
            cached = None

        if cached and cached.get("results") is not None:
            # Cached entries are already plain dicts, having been through to_dict() before
            # storage. The TTL index on the collection is what expires them; nothing here
            # checks an age, because a document Mongo has deleted simply is not returned.
            return {"jobs": list(cached["results"]), "failed_sources": [], "empty_sources": []}

        result = fetch_variant(
            variant, config.ADZUNA_APP_ID, config.ADZUNA_APP_KEY, work_type, experience,
            country,
        )
        jobs = [card.to_dict() for card in result["jobs"]]
        empty_sources = result.get("empty_sources", [])

        # Only cache a clean fetch. Caching a partial result set would pin an outage in
        # place for an hour after the API recovered.
        #
        # Cache only a pool that at least one GENUINELY SEARCHING source contributed to.
        #
        # Rewritten 2026-09-25, and the old version had quietly stopped working. It read
        # `"Adzuna" in empty_sources`, from when Adzuna was the only source that really
        # searched. Once Adzuna became optional per country it is SKIPPED for a user it
        # cannot serve -- so it is never in empty_sources for them, the check could never
        # fire, and their searches cached happily with no searching source at all. Found by
        # verify_live.py: a cached entry for "froentend web developer" built from Remotive
        # alone. Remotive ignores its search parameter, so that entry is the "same 20 jobs
        # for every query" weak state, pinned for an hour -- exactly the failure the 2026-09-20
        # fix was about, returning through a door the country work left open.
        #
        # Naming the sources that search, rather than the one that used to, means adding a
        # new source cannot silently reopen this again.
        contributed = {job.get("source") for job in jobs}
        degraded = bool(result["failed_sources"]) or not (SEARCHING_SOURCES & contributed)
        if jobs and not degraded:
            try:
                self.db.cache_put(key, variant, jobs)
            except Exception as e:
                print(f"job cache write failed for {variant!r}: {e}")

        return {
            "jobs": jobs,
            "failed_sources": result["failed_sources"],
            "empty_sources": empty_sources,
        }

    def _fetch_all_variants(self, variants, work_type=None, experience=None, country=None):
        """Fetch every variant in turn and return the un-deduplicated union plus failed sources."""
        jobs = []
        failed_sources = []
        for variant in variants:
            result = self._fetch_cached_variant(variant, work_type, experience, country)
            jobs.extend(result["jobs"])
            for source in result["failed_sources"]:
                if source not in failed_sources:
                    failed_sources.append(source)
        return jobs, failed_sources

    @staticmethod
    def deduplicate(jobs):
        """Collapse listings syndicated across both APIs, keyed on job_id (TC-022)."""
        # First occurrence wins, and that is a decision, not an accident. parse_intent
        # guarantees the user's original query is variant[0], so a job found by the user's
        # own phrasing keeps its place and an LLM-invented variant can only ever ADD to the
        # pool. If the last occurrence won instead, expansion could reorder results the user
        # would have seen without it.
        seen = set()
        unique = []
        for job in jobs:
            job_id = job.get("job_id")
            if not job_id:
                # A job with no id cannot be deduplicated or saved later, so it is dropped
                # rather than passed on to fail somewhere less obvious.
                continue
            if job_id in seen:
                continue
            seen.add(job_id)
            unique.append(job)
        return unique

    # --- classification -----------------------------------------------------------

    @staticmethod
    def classify(jobs, intent_category=None):
        """Assign every job exactly one config.CATEGORIES value from its own title and text."""
        # This runs in the agent rather than in JobCard.from_adzuna / from_himalayas, and that
        # is the decision to be able to defend. JobCard's job is to normalise the SHAPE two
        # APIs disagree about -- it is a dumb dataclass with no policy in it. Which category a
        # job belongs to is policy: it decides what the save/reject loop increments and what
        # the boost in rank() reads. Putting it here also means it happens exactly once for
        # every job on every path, including jobs read back out of the 60-minute cache, which
        # were serialised with whatever category was assigned when they were first fetched.
        #
        # The job's OWN text decides, not the source's taxonomy and not the user's query. The
        # parsed intent is only the fallback for a job whose text names no category at all,
        # because "the category this person was searching for" is a better guess than "other"
        # -- but it is still a guess, and it must never override a job that classified itself.
        # TC-011 says rejecting a TECH job lowers the TECH score; if the query's category won,
        # a tech job found in a writing search would move the writing score instead.
        # Title and description are passed SEPARATELY, not concatenated. classify_category
        # reads the title first and only falls through to the description when the title
        # names no category at all -- see its docstring for why. Joining them into one string
        # here, as this did until 2026-09-22, threw that distinction away before the
        # classifier could use it, and the description is where the noise lives.
        for job in jobs:
            job["category"] = classify_category(
                job.get("title", ""), intent_category, job.get("description", "")
            )
        return jobs

    # --- ranking ------------------------------------------------------------------

    def rank(self, query_vector, jobs, category_scores):
        """Re-rank an already-fetched job list by cosine similarity plus the category boost."""
        if not jobs:
            return []

        category_scores = category_scores or {}

        # One batch_encode beats len(jobs) separate encode calls: the model runs on batched
        # tensors, so the per-call overhead is paid once rather than eighty times.
        job_texts = [
            f"{job.get('title', '')}. {job.get('description', '')}" for job in jobs
        ]
        job_vectors = self.semantic_engine.batch_encode(job_texts)

        for job, vector in zip(jobs, job_vectors):
            similarity = self.semantic_engine.similarity(query_vector, vector)
            job["similarity_score"] = similarity
            # The learned preference is a nudge on top of meaning, never a replacement for
            # it. At 0.02 a category the user has saved from repeatedly can reorder two
            # jobs of near-equal similarity, and cannot lift an irrelevant job over a
            # relevant one. TODO(M4) still applies to the coefficient itself.
            boost = category_scores.get(job.get("category") or "", 0) * CATEGORY_BOOST
            job["final_score"] = similarity + boost

        jobs.sort(key=lambda j: j["final_score"], reverse=True)

        # Displayed percentages are relative to the best match in THIS result set, not an
        # absolute quality score — raw cosine values cluster in a narrow band and read as
        # meaningless to a user. Cosine similarity can be zero or negative, so the divide
        # is guarded rather than assumed safe.
        top_score = jobs[0]["final_score"]
        for job in jobs:
            job["normalized_score"] = (
                (job["final_score"] / top_score) * 100 if top_score > 0 else 0.0
            )

        return jobs

    # --- For You feed -------------------------------------------------------------

    def _empty_feed(self, categories, message):
        """Return the canonical result dict for a feed with no cards to show."""
        # Same discipline as _empty_result: every exit from build_feed hands feed.html the
        # identical key set, so the template never has to test which branch produced it.
        return {
            "feed_jobs": [],
            "top_categories": categories,
            "error": message,
            "warning": None,
        }

    def build_feed(self, user_id):
        """Build the For You feed from the user's highest-scoring categories (TC-012, TC-014).

        Honest description, and it must stay in these words: this runs a keyword search for
        each of the user's top category NAMES and re-ranks what comes back against their
        profile. It does not discover jobs matching their taste, and it can only ever return
        what those three keyword searches happened to fetch.
        """
        try:
            context = self.db.get_user_context(user_id) or {}
        except Exception as e:
            # Unlike run(), a context failure is fatal to the feed rather than a degradation.
            # The search has a query to fall back on; the feed has nothing else — the scores
            # ARE the input. Returning an unpersonalised feed here would be a different
            # feature wearing this one's name.
            print(f"could not load user context for {user_id!r}: {e}")
            return self._empty_feed([], MSG_FEED_EMPTY)

        try:
            categories = self.db.get_top_categories(user_id, n=FEED_CATEGORIES)
        except Exception as e:
            print(f"could not load top categories for {user_id!r}: {e}")
            return self._empty_feed([], MSG_FEED_EMPTY)

        # get_top_categories already drops anything scoring <= 0, which is TC-012's "tech
        # jobs absent" enforced at the source rather than by a filter further down.
        #
        # No positive scores means the user has saved nothing, and there is no honest feed to
        # build. The alternative considered and rejected was falling back to the profile's
        # skills: it would never leave the feed empty, but it would give "why do two users
        # see different feeds?" two possible answers instead of one, which is exactly the
        # ambiguity TC-014 exists to rule out. Note this returns BEFORE any fetch, so a
        # scoreless user's visit costs no Adzuna quota, no embedding and no Groq call.
        if not categories:
            return self._empty_feed([], MSG_FEED_EMPTY)

        # The profile's stated preferences become the fetch parameters. work_type is a list on
        # the profile and fetch_variant takes one value, so the first is used — combining them
        # would mean one fetch per category per work type, which multiplies the quota cost for
        # a refinement the feed does not need.
        preferred_work = context.get("preferred_work") or []
        work_type = preferred_work[0] if preferred_work else None
        experience = context.get("experience") or None

        raw_jobs = []
        failed_sources = []
        for category in categories:
            # The category name IS the query. "customer_support" is a database key, not
            # something to send to a job API, so the underscore is undone first.
            variant = category.replace("_", " ")
            result = self._fetch_cached_variant(
                variant, work_type, experience, context.get("country")
            )
            raw_jobs.extend(result["jobs"])
            for source in result["failed_sources"]:
                if source not in failed_sources:
                    failed_sources.append(source)

        jobs = self.deduplicate(raw_jobs)

        # intent_category is deliberately None here. In a search, a job whose text names no
        # category borrows the one the user was searching for; the feed has no single query,
        # so there is nothing to borrow and such a job lands in "other" — where the filter
        # below then drops it. A job has to earn its way into the feed by its own text.
        jobs = self.classify(jobs, None)

        saved_ids = {s.get("job_id") for s in context.get("saved_jobs") or []}
        jobs = self._filter_feed(jobs, categories, context.get("rejected_jobs"), saved_ids)

        if not jobs:
            error = MSG_SOURCE_DOWN if failed_sources else MSG_FEED_NONE_FOUND
            return self._empty_feed(categories, error)

        # The feed has no query, so the user's own preferences are the query: the top
        # categories, enriched with the profile by the same enrich_query TC-016 was proven
        # against. rank() then applies CATEGORY_BOOST on top of the resulting similarity, so
        # within the feed a category scored 5 outranks one scored 1.
        query_vector = self.semantic_engine.encode(
            enrich_query(" ".join(categories), context)
        )
        jobs = self.rank(query_vector, jobs, context.get("category_scores"))[:FEED_LIMIT]

        for job in jobs:
            job["match_band"] = match_band(job.get("normalized_score", 0.0))

        # RAGPipeline is deliberately NOT called. The feed is a browse surface, not a
        # question — a second Groq call on every page load would buy an explanation of a
        # query the user never typed, and FR-016's AI Recommendations are specified against
        # a search. This is an omission on purpose, not one that was missed.
        return {
            "feed_jobs": jobs,
            "top_categories": categories,
            "error": None,
            "warning": MSG_PARTIAL if failed_sources else None,
        }

    @staticmethod
    def _filter_feed(jobs, categories, rejected_jobs, saved_ids=None):
        """Keep only jobs in the user's top categories that they have not rejected or saved."""
        # TC-012 says rejected categories are ABSENT from the feed, not merely ranked last —
        # and "last of twelve on one page" is still present. A fetch for "writing" routinely
        # returns jobs that classify as technology, so without this a user with tech = -2
        # still sees tech jobs and the test fails on a feed that looks fine.
        #
        # Matching on the category the job classified ITSELF into, not on which category's
        # fetch returned it: those differ often, and the self-assigned one is what save and
        # reject increment, so it is the one the filter has to agree with.
        allowed = set(categories)
        rejected = set(rejected_jobs or [])
        # Rejections are matched on job_id. That is what deviation 4 from SRS v1.0 bought —
        # rejected_jobs stores ids rather than titles, so rejecting one "Software Engineer"
        # hides that employer's listing and not every job sharing the title.
        #
        # Saved jobs are dropped too (added 2026-10-01, open item 3 from 09-23). The feed is
        # for finding jobs the user has NOT seen; a saved one already sits on their profile,
        # and its Save button would do nothing, because save_job is idempotent (TC-013).
        hidden = rejected | set(saved_ids or ())
        return [
            job
            for job in jobs
            if job.get("category") in allowed and job.get("job_id") not in hidden
        ]

    @staticmethod
    def rag_candidates(jobs, top_k=TOP_K, local_applicable=False):
        """Pick the jobs the AI panel explains: applicable ones first, then the rest."""
        # Added 2026-09-23, and it is a deliberate departure worth stating: the AI panel no
        # longer explains "the top 5 by score", it explains "the best 5 the seeker can
        # actually apply for, topped up by score".
        #
        # Why it was needed. Telling the prompt to prefer unrestricted roles fixed nothing
        # on its own, because the prompt can only choose from what it is handed. Measured
        # on "junior software engineer": all five top-ranked jobs were UK-local Adzuna
        # listings and the four worldwide ones ranked sixth and below, so every pick in the
        # most prominent panel on the page was a job the seeker could not apply for.
        #
        # Rank order is preserved WITHIN each group, so this re-partitions the top of the
        # list, it does not re-score anything. The semantic ranking claim is untouched --
        # the ranked list the user sees below the panel is still ordered purely by
        # similarity plus the category boost.
        #
        # "unknown" is grouped with applicable rather than excluded. A job whose terms are
        # unstated might well hire the seeker, and the prompt is instructed to say the terms
        # are unstated, so the user is told rather than misled.
        #
        # "country" (added 2026-10-13) is applicable by construction: it is only ever set when
        # a structured restriction list names the seeker's own country.
        #
        # "local" is applicable only when local_applicable is True, and run() passes that
        # only for a user whose profile HAS a country. Since 2026-09-23 sources are chosen
        # per country, so for that user every local job is in their own country -- a UK
        # seeker's Adzuna jobs were being demoted for nothing. A legacy account with no
        # country still falls back to the gb Adzuna market, and nothing says that user lives
        # in the UK, so for them local stays where it was.
        #
        # False is the default ON PURPOSE: evaluation/generate_rag_picks.py and
        # evaluation/fresh/picks_fresh.py call this to reproduce the system that was
        # evaluated, and a changed default would silently change what they reproduce.
        allowed = {"open", "unknown", "country"}
        if local_applicable:
            allowed.add("local")
        applicable = [j for j in jobs if j.get("eligibility") in allowed]
        rest = [j for j in jobs if j.get("eligibility") not in allowed]
        # Topped up rather than truncated: a seeker with only two applicable jobs still gets
        # a full panel, and the restricted ones arrive carrying their restriction in the
        # prompt. An empty panel would teach them nothing.
        return (applicable + rest)[:top_k]

    @staticmethod
    def join_picks(picks, candidates):
        """Attach each LLM reason to its real job dict; [] stays [] (declined), None stays None."""
        # THE boundary that makes the AI panel safe to render as live job cards. The model
        # returns an index and a sentence; every other field on the resulting card -- url,
        # job_id, category, eligibility -- comes from the dict WE passed it. A hallucinated
        # title or a fabricated link is therefore not possible, rather than merely unlikely.
        #
        # The index is 1-based because the prompt numbers the jobs "Job 1:" upward, and
        # RAGPipeline.validate_picks has already guaranteed it is in range.
        #
        # None and [] are kept apart on purpose (2026-10-11): None means Groq failed and the
        # band is hidden (TC-009); [] means the model declined and the band says so.
        if picks is None:
            return None
        joined = []
        for pick in picks:
            job = candidates[pick["index"] - 1]
            # Copied, not mutated: the same dict object is rendered again in the ranked list
            # below, and writing onto it would leak the AI reason onto a card that is not
            # supposed to carry one.
            joined.append(dict(job, ai_reason=pick["reason"]))
        return joined

    # --- pipeline -----------------------------------------------------------------

    def _empty_result(self, query, error, intent=None):
        """Return the canonical result dict for a search that produced no ranked jobs."""
        # Every exit from run() has the same keys, so the route never has to test which
        # branch produced the result before rendering it.
        return {
            "jobs": [],
            "query": query,
            "intent": intent,
            "ai_recommendations": None,
            "error": error,
            "warning": None,
        }

    def run(self, user_id, query):
        """Execute the pipeline and return ranked jobs plus AI recommendations, or a fallback."""
        query = (query or "").strip()

        # TC-017. Checked before anything else, so an empty submit costs no Groq call, no
        # Adzuna quota and no database read. The verify script proves the absence by
        # counting calls on the stubs, because "we did not call it" cannot be shown by
        # inspecting a return value.
        if not query:
            return self._empty_result("", MSG_EMPTY_QUERY)

        # Profile first, before any external call — docs/ARCHITECTURE.md step 2. A database
        # outage degrades the search to unpersonalised rather than failing it.
        try:
            context = self.db.get_user_context(user_id) or {}
        except Exception as e:
            print(f"could not load user context for {user_id!r}: {e}")
            context = {}

        # Groq call #1. parse_intent owns its own try/except and keyword fallback (FR-018),
        # so there is deliberately no second layer of handling here; both paths return the
        # identical dict shape and nothing below branches on which one ran.
        intent = parse_intent(query)

        # TC-016. The profile moves the QUERY vector, not the job vectors: a user whose
        # profile lists Python has their query pulled towards Python in embedding space, so
        # Python roles rank higher FOR THEM. Editing the job text instead would change what
        # every user sees.
        # The experience the user stated IN THE QUERY wins over the one on their profile.
        # Without this, a profile saying "mid level" is embedded alongside a query saying
        # "beginner" and the two fight: measured on 2026-09-20, that narrowed the gap
        # between a junior and a senior job by about a third.
        query_vector = self.semantic_engine.encode(
            enrich_query(query, context, intent.get("experience"))
        )

        # TC-021. This is where expansion actually happens — parse_intent has been returning
        # variants since the last milestone, and until now nothing consumed them.
        # work_type is passed down rather than left in the query text. Adzuna's `what` is an
        # AND keyword match, so a word like "remote" in it returns nothing at all; it becomes
        # one of Adzuna's own parameters instead. See adapters/api_client.py.
        # The PROFILE fills in what the query did not say. Added 2026-09-26 after measuring
        # the case the project exists for: a recent graduate typing "software engineer" --
        # which is exactly what someone who does not know the vocabulary types -- got 77 jobs
        # of which 51% were senior-titled, because intent["experience"] was None and the
        # level filter therefore never ran. Someone who already knew to type "junior software
        # developer" got a clean list. The people the system is for were getting the worst
        # results, which is backwards.
        #
        # The QUERY still wins when it states a level: someone who is entry-level on paper but
        # searching for senior roles means the search, not the profile. This is the same
        # precedence enrich_query already applies to the embedding -- the filter was simply
        # never given the fallback.
        experience = intent.get("experience") or context.get("experience")

        # Same reasoning for work type. preferred_work is a list on the profile and
        # fetch_variant takes one value, so the first is used -- the same choice build_feed
        # already makes.
        preferred_work = context.get("preferred_work") or []
        work_type = intent.get("work_type") or (preferred_work[0] if preferred_work else None)

        # country decides which SOURCES can serve this user at all -- Adzuna has no endpoint
        # for a country it does not cover, so it is skipped rather than called and filtered.
        raw_jobs, failed_sources = self._fetch_all_variants(
            intent["variants"], work_type, experience, context.get("country"),
        )
        jobs = self.deduplicate(raw_jobs)

        # One category per job, from the job's own text (see classify above). Until this
        # existed, JobCard.category was "" for every job, so the CATEGORY_BOOST term in rank()
        # scored 0 on every listing and the save/reject loop had nothing to increment.
        jobs = self.classify(jobs, intent.get("category"))

        if not jobs:
            # TC-018. A rate-limited source and a genuinely empty result set are different
            # events and must not share a message — one is "come back later", the other is
            # "search for something else".
            error = MSG_SOURCE_DOWN if failed_sources else MSG_NO_RESULTS
            return self._empty_result(query, error, intent)

        jobs = self.rank(query_vector, jobs, context.get("category_scores"))

        # Groq call #2. Three outcomes, each rendered differently by index.html:
        #   None  -- Groq failed. The AI band is hidden, so an outage costs the explanation
        #            and nothing else, and the ranked list is still rendered in full (FR-018).
        #   []    -- the model declined because nothing fitted. The band says "no strong match".
        #   list  -- up to three picks, rendered as real job cards.
        # The candidate list is held so the picks can be joined back onto it. RAGPipeline
        # returns indices INTO THIS LIST, so recomputing it here would risk the two drifting.
        rag_jobs = self.rag_candidates(jobs, local_applicable=bool(context.get("country")))
        ai_recommendations = self.join_picks(self.rag_pipeline.run(query, rag_jobs), rag_jobs)

        try:
            self.db.add_search_history(user_id, query)
        except Exception as e:
            # History feeds autocomplete later. Losing it must never cost the user results.
            print(f"could not record search history for {user_id!r}: {e}")

        return {
            "jobs": jobs,
            "query": query,
            "intent": intent,
            "ai_recommendations": ai_recommendations,
            "error": None,
            # Some results arrived, but not all of them. A banner alongside the results,
            # not instead of them.
            "warning": MSG_PARTIAL if failed_sources else None,
        }
