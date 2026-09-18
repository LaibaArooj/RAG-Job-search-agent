"""Prove the search pipeline — TC-006, TC-016, TC-017, TC-018, TC-021, TC-022.

Run with:  python verify_agent.py

Unlike verify_intent.py, this script makes NO live calls at all. Every collaborator is a
double: the database, the semantic engine, the RAG pipeline and the two job APIs. That is
deliberate and it is the reason JobSearchAgent takes its collaborators as constructor
arguments — a pipeline that built its own SemanticEngine could not be tested without
loading 88 MB of model weights, and one that called the real Adzuna would spend demo quota
every time this script ran.

Three of these cases are only provable with doubles:
  - TC-017 asserts that NO api call happens, which needs a call counter, not a return value.
  - TC-018 needs Adzuna to fail on demand, which needs a stub, not a real outage.
  - TC-006 needs similarity scores chosen in advance, so the expected order is known.

Deliberately not pytest: pytest is not in requirements.txt and adding a dependency needs
sign-off. This mirrors verify_db.py, verify_auth.py and verify_intent.py.
"""

import sys

from core import agent as agent_module
from core import intent_parser
from core.agent import CATEGORY_BOOST, JobSearchAgent
from models.job_card import JobCard

PASSED = []
FAILED = []


def check(label, condition):
    """Record one assertion and print it as it happens."""
    (PASSED if condition else FAILED).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")


# --- doubles ----------------------------------------------------------------------


class StubDB:
    """Stand-in for DatabaseManager, recording calls and serving a canned profile."""

    def __init__(self, context=None, cached=None, raise_on_context=False):
        """Store the canned profile and cache contents this double should serve."""
        self.context = context if context is not None else {}
        self.cached = cached or {}
        self.raise_on_context = raise_on_context
        self.history = []
        self.cache_writes = {}

    def get_user_context(self, username):
        """Return the canned profile, or raise if this double is scripted to fail."""
        if self.raise_on_context:
            raise RuntimeError("Atlas unreachable")
        return self.context

    def cache_get(self, key):
        """Return the canned cache entry for this key, or None."""
        return self.cached.get(key)

    def cache_put(self, key, query_text, results):
        """Record a cache write."""
        self.cache_writes[key] = results

    def add_search_history(self, username, query):
        """Record a search-history write."""
        self.history.append((username, query))


class StubEngine:
    """Semantic engine double returning similarity scores decided in advance by job title."""

    def __init__(self, scores=None):
        """Store the title-to-similarity map this double should return."""
        self.scores = scores or {}
        self.encoded = []
        self.batches = []

    def encode(self, text):
        """Record the enriched query text and return it as the 'vector' (TC-016 asserts on it)."""
        self.encoded.append(text)
        return text

    def batch_encode(self, texts):
        """Record the job texts and return them unchanged as 'vectors'."""
        self.batches.append(texts)
        return texts

    def similarity(self, query_vector, job_vector):
        """Return the pre-decided score for whichever job title this text starts with."""
        for title, score in self.scores.items():
            if job_vector.startswith(title):
                return score
        return 0.0


class StubRAG:
    """RAG pipeline double returning canned prose, or None to simulate a Groq failure."""

    def __init__(self, reply="AI picks go here"):
        """Store the canned reply (None simulates the FR-018 fallback)."""
        self.reply = reply
        self.received = None

    def run(self, query, jobs):
        """Record the jobs it was handed and return the canned reply."""
        self.received = jobs
        return self.reply


class FetchRecorder:
    """Replaces api_client.fetch_variant, serving canned jobs per variant and counting calls."""

    def __init__(self, by_variant=None, failed_sources=None):
        """Store the per-variant canned job lists and any sources scripted to fail."""
        self.by_variant = by_variant or {}
        self.failed_sources = failed_sources or []
        self.calls = []

    def __call__(self, query, app_id, app_key):
        """Mimic fetch_variant, recording the variant asked for."""
        self.calls.append(query)
        return {
            "jobs": list(self.by_variant.get(query, [])),
            "failed_sources": list(self.failed_sources),
        }


def card(title, company="Acme", description="a job", source="Remotive", category=""):
    """Build one JobCard with a real job_id, so dedupe is tested against the real hash."""
    return JobCard(
        job_id=JobCard.make_job_id(title, company),
        title=title,
        company=company,
        description=description,
        source=source,
        category=category,
    )


def install(monkey_fetch=None, monkey_intent=None):
    """Swap fetch_variant and parse_intent inside core.agent for the duration of one case."""
    # Patched on the agent module, not on their home modules: the agent imported the names
    # directly, so rebinding them where they are USED is what takes effect.
    if monkey_fetch is not None:
        agent_module.fetch_variant = monkey_fetch
    if monkey_intent is not None:
        agent_module.parse_intent = monkey_intent


def fixed_intent(*variants):
    """Return a parse_intent double that always yields the given variants, counting calls."""

    def _parse(query):
        _parse.calls += 1
        return {
            "work_type": None,
            "experience": None,
            "category": "other",
            "variants": list(variants) or [query],
            "source": "stub",
        }

    _parse.calls = 0
    return _parse


# --- TC-017: empty query makes no external call -----------------------------------


def test_empty_query():
    """TC-017: an empty search returns the prompt message and calls nothing external."""
    print("\nTC-017 — empty query")
    fetch = FetchRecorder()
    intent = fixed_intent("x")
    install(fetch, intent)
    db = StubDB()

    result = JobSearchAgent(db, StubEngine(), StubRAG()).run("laiba", "")

    check("empty query returns the SRS message", result["error"] == "Please enter a search term")
    check("empty query returns no jobs", result["jobs"] == [])
    # The point of the whole case: proving an absence needs a counter.
    check("no API call was made", fetch.calls == [])
    check("no Groq intent call was made", intent.calls == 0)
    check("no search history was written", db.history == [])

    result = JobSearchAgent(db, StubEngine(), StubRAG()).run("laiba", "    ")
    check("whitespace-only query is treated as empty", result["error"] == "Please enter a search term")
    check("whitespace-only query made no API call", fetch.calls == [])


# --- TC-018: a failed source is not the same as no results ------------------------


def test_source_failure():
    """TC-018: Adzuna failing with no jobs shows the outage banner, not 'no results'."""
    print("\nTC-018 — rate-limited source")
    install(FetchRecorder(by_variant={}, failed_sources=["Adzuna"]), fixed_intent("q"))
    down = JobSearchAgent(StubDB(), StubEngine(), StubRAG()).run("laiba", "q")
    check("no jobs + failed source -> outage banner",
          down["error"] == "Job data temporarily unavailable")

    install(FetchRecorder(by_variant={}, failed_sources=[]), fixed_intent("q"))
    empty = JobSearchAgent(StubDB(), StubEngine(), StubRAG()).run("laiba", "q")
    check("no jobs + healthy sources -> no-results message",
          empty["error"].startswith("No jobs matched"))
    check("the two causes give different messages", down["error"] != empty["error"])

    # Partial failure: some results arrived, so they must still be shown.
    install(
        FetchRecorder(by_variant={"q": [card("Writer")]}, failed_sources=["Adzuna"]),
        fixed_intent("q"),
    )
    partial = JobSearchAgent(StubDB(), StubEngine({"Writer": 0.5}), StubRAG()).run("laiba", "q")
    check("partial failure still returns the jobs that arrived", len(partial["jobs"]) == 1)
    check("partial failure sets a warning, not an error",
          partial["error"] is None and partial["warning"] is not None)


# --- TC-021: query expansion widens the pool --------------------------------------


def test_query_expansion():
    """TC-021: the union across variants is strictly larger than any single variant."""
    print("\nTC-021 — query expansion")
    by_variant = {
        "remote writing job no experience": [card("Content Writer"), card("Copywriter")],
        "junior copywriter remote": [card("Copywriter"), card("Junior Copywriter")],
        "entry level content writer": [card("Content Associate")],
    }
    variants = list(by_variant)
    fetch = FetchRecorder(by_variant=by_variant)
    install(fetch, fixed_intent(*variants))

    scores = {"Content Writer": 0.9, "Copywriter": 0.8, "Junior Copywriter": 0.7,
              "Content Associate": 0.6}
    result = JobSearchAgent(StubDB(), StubEngine(scores), StubRAG()).run(
        "laiba", "remote writing job no experience"
    )

    check("the API was called once per variant", fetch.calls == variants)
    biggest_single = max(len(v) for v in by_variant.values())
    check(f"union ({len(result['jobs'])}) is larger than the biggest single variant ({biggest_single})",
          len(result["jobs"]) > biggest_single)
    check("union is exactly the 4 distinct jobs", len(result["jobs"]) == 4)
    check("the original query is fetched first", fetch.calls[0] == variants[0])


# --- TC-022: cross-source deduplication -------------------------------------------


def test_deduplication():
    """TC-022: the same listing from both APIs appears exactly once."""
    print("\nTC-022 — cross-source dedupe")
    same_from_remotive = card("Content Writer", "Acme Ltd", source="Remotive")
    # Same listing as Adzuna syndicates it: different case, padded, different description.
    same_from_adzuna = card("  content WRITER ", "acme ltd", description="other text",
                            source="Adzuna")

    check("differing case and padding hash to the same job_id",
          same_from_remotive.job_id == same_from_adzuna.job_id)
    check("a different company hashes differently",
          card("Content Writer", "Other Ltd").job_id != same_from_remotive.job_id)
    # The separator case: without "|", these two would collide.
    check("('Data','Xco') and ('DataX','co') do not collide",
          JobCard.make_job_id("Data", "Xco") != JobCard.make_job_id("DataX", "co"))

    install(
        FetchRecorder(by_variant={"writer": [same_from_remotive, same_from_adzuna]}),
        fixed_intent("writer"),
    )
    result = JobSearchAgent(StubDB(), StubEngine({"Content Writer": 0.9}), StubRAG()).run(
        "laiba", "writer"
    )
    check("the syndicated job appears exactly once", len(result["jobs"]) == 1)
    check("the first occurrence is the one kept", result["jobs"][0]["source"] == "Remotive")

    dropped = JobSearchAgent.deduplicate([{"title": "no id"}, {"job_id": "abc"}])
    check("a job with no job_id is dropped rather than passed on", len(dropped) == 1)


# --- TC-006: results come back ranked ---------------------------------------------


def test_ranking():
    """TC-006: jobs are returned sorted by score, highest first, with display scores set."""
    print("\nTC-006 — semantic ranking")
    jobs = [card("Accountant"), card("Content Writer"), card("Warehouse Packer")]
    install(FetchRecorder(by_variant={"writing": jobs}), fixed_intent("writing"))
    scores = {"Content Writer": 0.91, "Accountant": 0.22, "Warehouse Packer": 0.05}

    result = JobSearchAgent(StubDB(), StubEngine(scores), StubRAG()).run("laiba", "writing")
    titles = [j["title"] for j in result["jobs"]]

    check("the most similar job ranks first", titles[0] == "Content Writer")
    check("results are sorted by score descending",
          all(result["jobs"][i]["final_score"] >= result["jobs"][i + 1]["final_score"]
              for i in range(len(result["jobs"]) - 1)))
    check("the top result normalises to 100%", round(result["jobs"][0]["normalized_score"], 6) == 100.0)
    check("every job carries a similarity score",
          all("similarity_score" in j for j in result["jobs"]))

    # A negative top score must not produce a negative or exploded percentage.
    install(FetchRecorder(by_variant={"x": [card("Accountant")]}), fixed_intent("x"))
    negative = JobSearchAgent(StubDB(), StubEngine({"Accountant": -0.4}), StubRAG()).run("laiba", "x")
    check("a negative top score gives 0% rather than a broken divide",
          negative["jobs"][0]["normalized_score"] == 0.0)


# --- TC-016: the profile reaches the query vector ---------------------------------


def test_context_injection():
    """TC-016: profile skills are folded into the encoded query, not into the job text."""
    print("\nTC-016 — context injection")
    engine = StubEngine({"Developer": 0.8})
    install(FetchRecorder(by_variant={"developer job": [card("Developer")]}),
            fixed_intent("developer job"))
    db = StubDB(context={"skills": ["Python", "Flask"], "experience": "entry level"})

    JobSearchAgent(db, engine, StubRAG()).run("laiba", "developer job")

    encoded = engine.encoded[0]
    check("the encoded query contains the profile skill", "Python" in encoded)
    check("the encoded query contains the experience level", "entry level" in encoded)
    check("the encoded query still contains the search term", "developer job" in encoded)
    # The other half of the claim: the JOB text is untouched, so this personalisation
    # changes what THIS user sees, not what every user sees.
    check("the job text is not modified by the profile",
          all("Python" not in text for text in engine.batches[0]))

    # A database outage degrades to unpersonalised rather than failing the search.
    engine2 = StubEngine({"Developer": 0.8})
    install(FetchRecorder(by_variant={"developer job": [card("Developer")]}),
            fixed_intent("developer job"))
    result = JobSearchAgent(StubDB(raise_on_context=True), engine2, StubRAG()).run(
        "laiba", "developer job"
    )
    check("a profile read failure still returns results", len(result["jobs"]) == 1)


# --- category boost ----------------------------------------------------------------


def test_category_boost():
    """The learned category score reorders near-equal jobs, and provably would not at 0.0."""
    print("\nCategory boost")
    jobs = [card("Design Role", category="design"), card("Tech Role", category="technology")]
    scores = {"Design Role": 0.50, "Tech Role": 0.51}
    # Tech leads on raw similarity by 0.01. A design score of 10 adds 10 x 0.02 = 0.2,
    # which is enough to overturn it; that is the boost doing its job.
    category_scores = {"design": 10, "technology": 0}

    engine = StubEngine(scores)
    ranked = JobSearchAgent(StubDB(), engine, StubRAG()).rank("q", list(jobs_as_dicts(jobs)), category_scores)
    check("a strong learned preference reorders near-equal jobs",
          ranked[0]["title"] == "Design Role")

    unboosted = JobSearchAgent(StubDB(), StubEngine(scores), StubRAG()).rank(
        "q", list(jobs_as_dicts(jobs)), {}
    )
    check("without the boost, raw similarity wins", unboosted[0]["title"] == "Tech Role")
    check("CATEGORY_BOOST is still the documented 0.02", CATEGORY_BOOST == 0.02)

    # It must remain a nudge: it cannot lift an irrelevant job over a relevant one.
    far_apart = [card("Design Role", category="design"), card("Tech Role", category="technology")]
    ranked_far = JobSearchAgent(StubDB(), StubEngine({"Design Role": 0.10, "Tech Role": 0.90}),
                                StubRAG()).rank("q", list(jobs_as_dicts(far_apart)),
                                                {"design": 10})
    check("the boost cannot overturn a large similarity gap",
          ranked_far[0]["title"] == "Tech Role")


def jobs_as_dicts(cards):
    """Convert JobCards to the dict shape rank() operates on."""
    return [c.to_dict() for c in cards]


# --- RAG failure and caching --------------------------------------------------------


def test_rag_fallback():
    """FR-018: a Groq failure hides the AI band but still returns the full ranked list."""
    print("\nFR-018 — RAG fallback")
    jobs = [card(f"Job {i}") for i in range(8)]
    scores = {f"Job {i}": 0.9 - i / 100 for i in range(8)}
    install(FetchRecorder(by_variant={"q": jobs}), fixed_intent("q"))

    rag = StubRAG(reply=None)
    result = JobSearchAgent(StubDB(), StubEngine(scores), rag).run("laiba", "q")
    check("a RAG failure returns no recommendations", result["ai_recommendations"] is None)
    check("a RAG failure does not set an error", result["error"] is None)
    check("the full ranked list is still returned", len(result["jobs"]) == 8)
    check("only the top 5 were sent to the LLM", len(rag.received) == 5)


def test_cache():
    """The job cache is read before fetching and written after a clean fetch."""
    print("\nJob cache")
    fetch = FetchRecorder(by_variant={"q": [card("Writer")]})
    install(fetch, fixed_intent("q"))
    db = StubDB()

    JobSearchAgent(db, StubEngine({"Writer": 0.5}), StubRAG()).run("laiba", "q")
    check("a cache miss fetches and then writes one entry", len(db.cache_writes) == 1)
    check("the fetch actually happened on a miss", fetch.calls == ["q"])

    # Feed what was just written back in as the cache contents.
    key, results = next(iter(db.cache_writes.items()))
    warm_fetch = FetchRecorder(by_variant={"q": [card("Writer")]})
    install(warm_fetch, fixed_intent("q"))
    warm = JobSearchAgent(StubDB(cached={key: {"results": results}}),
                          StubEngine({"Writer": 0.5}), StubRAG()).run("laiba", "q")
    check("a cache hit skips the API call entirely", warm_fetch.calls == [])
    check("a cache hit still returns the jobs", len(warm["jobs"]) == 1)

    # A failed fetch must not be cached, or the outage outlives the API's recovery.
    failing = FetchRecorder(by_variant={"q": [card("Writer")]}, failed_sources=["Adzuna"])
    install(failing, fixed_intent("q"))
    db3 = StubDB()
    JobSearchAgent(db3, StubEngine({"Writer": 0.5}), StubRAG()).run("laiba", "q")
    check("a partial fetch is not cached", db3.cache_writes == {})


# --- JobCard normalisation ----------------------------------------------------------


def test_job_card():
    """JobCard flattens both API shapes and survives missing fields."""
    print("\nJobCard normalisation")
    adzuna = JobCard.from_adzuna({
        "title": "Data Analyst",
        "company": {"display_name": "Acme"},
        "location": {"display_name": "London"},
        "description": "work with data",
        "redirect_url": "https://example.com/1",
        "salary_min": 30000,
    })
    check("Adzuna company is flattened to a string", adzuna.company == "Acme")
    check("Adzuna location is flattened to a string", adzuna.location == "London")
    check("Adzuna source is labelled", adzuna.source == "Adzuna")

    # The bug this class exists to prevent: nested objects absent entirely.
    bare = JobCard.from_adzuna({"title": "Analyst"})
    check("a missing company object does not raise", bare.company == "Unknown")
    check("a missing location object does not raise", bare.location == "Unknown")
    check("an empty raw result does not raise", JobCard.from_adzuna({}).title == "Unknown Title")

    remotive = JobCard.from_remotive({
        "title": "Writer",
        "company_name": "Beta",
        "candidate_required_location": "",
        "description": "x" * 900,
        "url": "https://example.com/2",
    })
    check("Remotive blank location falls back to a readable string",
          remotive.location.startswith("Remote"))
    check("Remotive description is truncated to 500 chars", len(remotive.description) == 500)
    check("to_dict gives the dict shape the templates read",
          remotive.to_dict()["title"] == "Writer")
    check("every card carries a job_id", bool(adzuna.job_id) and bool(remotive.job_id))


# --- intent parser still intact ------------------------------------------------------


def test_enrich_query_unchanged():
    """enrich_query is reused, not reimplemented — the wording TC-016 was proven against."""
    print("\nenrich_query reuse")
    text = intent_parser.enrich_query("developer job", {"skills": ["Python"], "experience": "entry level"})
    check("the wording is still the TC-016 phrasing",
          text == "job search: developer job. Skills: Python. Level: entry level.")
    check("a missing profile does not raise", "job search: x." in intent_parser.enrich_query("x", None))


def main():
    """Run every case and exit non-zero if any assertion failed."""
    print("=" * 70)
    print("verify_agent.py — JobSearchAgent and JobCard (offline, no live calls)")
    print("=" * 70)

    original_fetch = agent_module.fetch_variant
    original_parse = agent_module.parse_intent
    try:
        test_job_card()
        test_empty_query()
        test_source_failure()
        test_query_expansion()
        test_deduplication()
        test_ranking()
        test_context_injection()
        test_category_boost()
        test_rag_fallback()
        test_cache()
        test_enrich_query_unchanged()
    finally:
        # Restore the real functions, so importing this module cannot leave the agent
        # permanently stubbed for anything that imports it afterwards.
        agent_module.fetch_variant = original_fetch
        agent_module.parse_intent = original_parse

    print("\n" + "=" * 70)
    print(f"{len(PASSED)} passed, {len(FAILED)} failed  "
          f"({len(PASSED)}/{len(PASSED) + len(FAILED)})")
    if FAILED:
        for label in FAILED:
            print(f"  FAILED: {label}")
    print("=" * 70)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
