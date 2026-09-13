"""JobSearchAgent — orchestrates the search pipeline end to end.

STUB — filled in during M2. Covers TC-006, TC-016 to TC-018 and TC-019 to TC-022.

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
intent-parse failure, no jobs returned from any variant, and RAG failure.
"""

# Hand-picked coefficient weighting learned category preference against raw similarity.
# TODO(M4): this number has no justification yet. Either tune it during the precision@5
# evaluation or state it plainly in the report as a heuristic. Do not leave it unexplained.
CATEGORY_BOOST = 0.02

TOP_K = 5


class JobSearchAgent:
    """Runs the full search pipeline: parse intent, fetch, re-rank, then generate."""

    def __init__(self, db, semantic_engine, rag_pipeline):
        """Take the collaborators as arguments so each layer stays independently testable."""
        raise NotImplementedError("M2")

    def run(self, user_id, query):
        """Execute the pipeline and return ranked jobs plus AI recommendations, or a fallback."""
        raise NotImplementedError("M2")

    def rank(self, query_vector, jobs, category_scores):
        """Re-rank an already-fetched job list by cosine similarity plus the category boost."""
        raise NotImplementedError("M2")

    @staticmethod
    def deduplicate(jobs):
        """Collapse listings syndicated across both APIs, keyed on job_id (TC-022)."""
        raise NotImplementedError("M2")
