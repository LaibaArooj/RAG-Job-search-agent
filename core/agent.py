"""JobSearchAgent — orchestrates the search pipeline end to end.

Covers TC-006, TC-016 to TC-018 and TC-019 to TC-022.

The steps, per docs/ARCHITECTURE.md § Search request flow:

    1. get_user_context          - profile read before any API call
    2. parse_intent              - Groq call #1, keyword fallback
    3. enrich_query              - profile folded into the query text
    4. fetch, once per variant   - Adzuna + Remotive via adapters.api_client
    5. union and deduplicate     - on job_id (SHA of title + company)
    6. batch_encode + similarity - core.semantic_engine
    7. score and sort            - similarity + (category_score x 0.02)
    8. top 5 -> RAGPipeline.run  - Groq call #2, hides the AI panel on failure

Honest description of what this does: it RE-RANKS the candidate pool that keyword search
returned. It cannot surface a job the APIs never fetched. Query expansion at step 4 widens
that pool but does not remove the ceiling. Do not describe step 6 as "semantic retrieval".

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
from adapters.api_client import fetch_variant
from core.intent_parser import enrich_query, parse_intent

# Hand-picked coefficient weighting learned category preference against raw similarity.
# TODO(M4): this number has no justification yet. Either tune it during the precision@5
# evaluation or state it plainly in the report as a heuristic. Do not leave it unexplained.
CATEGORY_BOOST = 0.02

TOP_K = 5

# The five messages the route can render. Kept here as constants because the verify script
# asserts on them and TC-017/TC-018 quote them; a typo in one place would pass a test that
# quoted the same typo.
MSG_EMPTY_QUERY = "Please enter a search term"
MSG_SOURCE_DOWN = "Job data temporarily unavailable"
MSG_NO_RESULTS = "No jobs matched that search. Try different wording."
MSG_PARTIAL = "Some job sources are unavailable, so these results are incomplete."


def _cache_key(variant):
    """Hash one query variant into the _id used by the job cache collection."""
    # Hashed rather than used raw because the variant is user-influenced text and it becomes
    # a MongoDB _id. A hash is a fixed-length value from a fixed alphabet, so no query string
    # can collide with an operator or blow the key-length limit.
    return hashlib.sha256(variant.strip().lower().encode("utf-8")).hexdigest()


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

    def _fetch_cached_variant(self, variant, work_type=None, experience=None):
        """Fetch one variant, reading and writing the 60-minute job cache around the call."""
        key = _cache_key(variant)

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
            variant, config.ADZUNA_APP_ID, config.ADZUNA_APP_KEY, work_type, experience
        )
        jobs = [card.to_dict() for card in result["jobs"]]
        empty_sources = result.get("empty_sources", [])

        # Only cache a clean fetch. Caching a partial result set would pin an outage in
        # place for an hour after the API recovered.
        #
        # An Adzuna that returned NOTHING counts as degraded here, even though it did not
        # fail. Adzuna is the only source that genuinely searches -- Remotive ignores its
        # search parameter and is filtered locally -- so a pool built without it is the
        # weak state, and pinning it for an hour is exactly what made the senior-results
        # bug persist across retries on 2026-09-20.
        #
        # Remotive filtering down to nothing is NOT degraded; it is the filter working, and
        # it must stay cacheable or every such search costs Adzuna quota it need not.
        degraded = bool(result["failed_sources"]) or "Adzuna" in empty_sources
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

    def _fetch_all_variants(self, variants, work_type=None, experience=None):
        """Fetch every variant in turn and return the un-deduplicated union plus failed sources."""
        jobs = []
        failed_sources = []
        for variant in variants:
            result = self._fetch_cached_variant(variant, work_type, experience)
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
        raw_jobs, failed_sources = self._fetch_all_variants(
            intent["variants"], intent.get("work_type"), intent.get("experience")
        )
        jobs = self.deduplicate(raw_jobs)

        if not jobs:
            # TC-018. A rate-limited source and a genuinely empty result set are different
            # events and must not share a message — one is "come back later", the other is
            # "search for something else".
            error = MSG_SOURCE_DOWN if failed_sources else MSG_NO_RESULTS
            return self._empty_result(query, error, intent)

        jobs = self.rank(query_vector, jobs, context.get("category_scores"))

        # Groq call #2. RAGPipeline.run returns None on failure, and the template hides the
        # AI band when ai_recommendations is falsy, so a Groq outage costs the explanation
        # and nothing else. The ranked list is still rendered in full (FR-018).
        ai_recommendations = self.rag_pipeline.run(query, jobs[:TOP_K])

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
