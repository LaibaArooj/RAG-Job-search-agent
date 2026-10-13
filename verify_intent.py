"""Prove intent parsing and its fallback — TC-019 and TC-020.

Run with:  python verify_intent.py

TC-019 needs a live Groq call, so this script does make one. TC-020 and the validation
checks do not: they replace the Groq client with a stub, which is the only way to prove the
fallback without waiting for a real outage.

Deliberately not pytest: pytest is not in requirements.txt and adding a dependency needs
sign-off. This mirrors verify_db.py and verify_auth.py.
"""

from config import CATEGORIES, EXPERIENCE_LEVELS, WORK_TYPES
from core import intent_parser

PASSED = []
FAILED = []


def check(label, condition):
    """Record one assertion and print it as it happens."""
    (PASSED if condition else FAILED).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")


class StubGroq:
    """Stand-in for the Groq client returning a canned reply, or raising, on demand."""

    def __init__(self, reply=None, error=None):
        """Store the scripted reply or the exception this stub should raise."""
        self.reply = reply
        self.error = error
        self.calls = 0
        self.chat = self

    @property
    def completions(self):
        """Expose self so client.chat.completions.create resolves to this object."""
        return self

    def create(self, **kwargs):
        """Mimic Groq's create(), counting calls and returning the scripted reply."""
        self.calls += 1
        if self.error:
            raise self.error

        # The three shims below reproduce the shape parse_intent reads:
        # response.choices[0].message.content
        class _Message:
            """Carries the scripted reply text."""

            content = self.reply

        class _Choice:
            """One completion choice, as the Groq SDK returns it."""

            message = _Message()

        class _Response:
            """The create() return value, holding a single choice."""

            choices = [_Choice()]

        return _Response()


def use_stub(stub):
    """Swap the module's lazily built Groq client for a stub, and return it."""
    intent_parser._client = stub
    return stub


def shape_is_canonical(intent):
    """True when the intent dict has exactly the five keys every caller relies on."""
    return set(intent) == {"work_type", "experience", "category", "variants", "source"}


def main():
    """Run every intent-parsing check in order and print a summary."""
    try:
        print("\n1. Canonical shape, both paths")
        stub = use_stub(StubGroq(reply='{"work_type": "remote", "experience": '
                                       '"entry level", "category": "writing", '
                                       '"variants": ["remote content writer", '
                                       '"junior copywriter"]}'))
        llm = intent_parser.parse_intent("remote writing job no experience")
        check("LLM path returns the five canonical keys", shape_is_canonical(llm))
        check("LLM path is labelled source=llm", llm["source"] == "llm")

        kw = intent_parser._parse_intent_keywords("remote writing job no experience")
        check("keyword path returns the same five keys", shape_is_canonical(kw))
        check("keyword path is labelled source=keywords", kw["source"] == "keywords")
        check("both paths agree on key set", set(llm) == set(kw))

        print("\n2. TC-020  fallback when Groq is unavailable")
        stub = use_stub(StubGroq(error=RuntimeError("connection refused")))
        intent = intent_parser.parse_intent("remote writing job no experience")
        check("TC-020  no exception escapes parse_intent", True)
        check("TC-020  Groq was actually attempted", stub.calls == 1)
        check("TC-020  fell back to keywords", intent["source"] == "keywords")
        check("TC-020  intent still usable: work_type", intent["work_type"] == "remote")
        check("TC-020  intent still usable: experience",
              intent["experience"] == "entry level")
        check("TC-020  intent still usable: category", intent["category"] == "writing")
        check("TC-020  original query survives as a variant",
              intent["variants"] == ["remote writing job no experience"])
        # Added 2026-10-13: "no degree" means no experience on BOTH paths, so the fallback
        # agrees with what the LLM prompt now states.
        check("the fallback reads 'no degree' as entry level",
              intent_parser._parse_intent_keywords(
                  "I want to get into tech but I have no degree")["experience"] == "entry level")

        print("\n3. Fallback when the reply is not JSON")
        stub = use_stub(StubGroq(reply="Sure! Here are some thoughts about your search."))
        intent = intent_parser.parse_intent("senior python developer")
        check("unparseable reply falls back, does not raise",
              intent["source"] == "keywords")
        check("keyword path still found the category",
              intent["category"] == "technology")

        print("\n4. Markdown fences are tolerated")
        use_stub(StubGroq(reply='```json\n{"work_type": "freelance", "experience": null,'
                                ' "category": "design", "variants": ["ux contractor"]}\n```'))
        intent = intent_parser.parse_intent("freelance ux work")
        check("fenced JSON still parses as the LLM path", intent["source"] == "llm")
        check("fenced JSON yields the work type", intent["work_type"] == "freelance")
        check("null experience becomes None", intent["experience"] is None)

        print("\n5. Validation - values outside the closed sets are dropped")
        use_stub(StubGroq(reply='{"work_type": "four-day-week", "experience": "wizard",'
                                ' "category": "creative", "variants": []}'))
        intent = intent_parser.parse_intent("something creative")
        check("unknown work_type dropped to None", intent["work_type"] is None)
        check("unknown experience dropped to None", intent["experience"] is None)
        check("unknown category falls back to 'other'", intent["category"] == "other")
        check("category is always a member of CATEGORIES",
              intent["category"] in CATEGORIES)

        print("\n6. Validation - the injection case that matters in M3")
        # config.py documents why: category becomes part of a MongoDB field path
        # (category_scores.<category>), so a "." or a "$" would write to an arbitrary
        # field or run an operator. The model must not be able to supply one.
        for hostile in ("technology.$ne", "$where", "technology.admin", "a.b.c"):
            use_stub(StubGroq(reply='{"work_type": null, "experience": null,'
                                    ' "category": "%s", "variants": []}' % hostile))
            intent = intent_parser.parse_intent("developer job")
            check(f"hostile category {hostile!r} rejected",
                  intent["category"] == "other")
            check(f"no '.' or '$' reaches a field path from {hostile!r}",
                  "." not in intent["category"] and "$" not in intent["category"])

        print("\n7. Validation - variants")
        use_stub(StubGroq(reply='{"work_type": null, "experience": null,'
                                ' "category": "other",'
                                ' "variants": ["a", "b", "c", "d", "e"]}'))
        intent = intent_parser.parse_intent("some query")
        check("variants capped at MAX_VARIANTS",
              len(intent["variants"]) == intent_parser.MAX_VARIANTS)
        check("original query is always variants[0]",
              intent["variants"][0] == "some query")

        use_stub(StubGroq(reply='{"work_type": null, "experience": null,'
                                ' "category": "other",'
                                ' "variants": ["some query", "SOME QUERY", 42, "", "real"]}'))
        intent = intent_parser.parse_intent("some query")
        check("duplicate variants removed case-insensitively",
              intent["variants"] == ["some query", "real"])
        check("non-string and empty variants dropped",
              all(isinstance(v, str) and v for v in intent["variants"]))

        use_stub(StubGroq(reply='{"work_type": null, "experience": null,'
                                ' "category": "other", "variants": "not a list"}'))
        intent = intent_parser.parse_intent("some query")
        check("non-list variants degrade to the query alone",
              intent["variants"] == ["some query"])

        print("\n8. TC-017  an empty query makes no external call")
        stub = use_stub(StubGroq(reply='{"category": "technology"}'))
        for empty in ("", "   ", None):
            intent = intent_parser.parse_intent(empty)
            check(f"empty query {empty!r} returns the canonical shape",
                  shape_is_canonical(intent))
        check("TC-017  Groq was never called for an empty query", stub.calls == 0)

        print("\n9. enrich_query folds the profile into the query text")
        enriched = intent_parser.enrich_query(
            "developer job", {"skills": ["Python", "SQL"], "experience": "senior"}
        )
        check("TC-016  skills appear in the enriched query", "Python" in enriched)
        check("TC-016  experience appears in the enriched query", "senior" in enriched)
        check("TC-016  the original query survives", "developer job" in enriched)
        check("a missing profile does not raise",
              "developer job" in intent_parser.enrich_query("developer job", None))
        check("an empty profile does not raise",
              "developer job" in intent_parser.enrich_query("developer job", {}))

        print("\n10. Keyword fallback coverage")
        cases = [
            ("work from home writing gig", "work_type", "remote"),
            ("graduate software engineer", "experience", "entry level"),
            ("senior nurse position", "experience", "senior"),
            ("part time teaching assistant", "work_type", "part-time"),
            ("copywriter needed", "category", "writing"),
            ("paralegal vacancy", "category", "legal"),
            ("zzzz qqqq", "category", "other"),
        ]
        for query, field, expected in cases:
            got = intent_parser._parse_intent_keywords(query)[field]
            check(f"{query!r} -> {field}={expected}", got == expected)

        print("\n11. Every produced value is a member of its closed set")
        # The guarantee the rest of the pipeline depends on, asserted directly rather
        # than inferred from the cases above.
        for query, _, _ in cases:
            intent = intent_parser._parse_intent_keywords(query)
            check(f"{query!r} category is in CATEGORIES",
                  intent["category"] in CATEGORIES)
            check(f"{query!r} work_type is valid or None",
                  intent["work_type"] is None or intent["work_type"] in WORK_TYPES)
            check(f"{query!r} experience is valid or None",
                  intent["experience"] is None or intent["experience"] in EXPERIENCE_LEVELS)

        print("\n12. TC-019  live Groq call")
        # The one check that needs the network. The SRS query names no category in
        # CATEGORIES -- it says "creative" -- so the pass condition is that the model
        # picks the single closest member, which is writing or design.
        intent_parser._client = None  # drop the stub, use the real client
        srs_query = "something creative I can do from home, I'm just starting out"
        intent = intent_parser.parse_intent(srs_query)

        if intent["source"] != "llm":
            check("TC-019  SKIPPED - Groq unreachable, see the message above", False)
        else:
            check("TC-019  work_type=remote", intent["work_type"] == "remote")
            check("TC-019  experience=entry level",
                  intent["experience"] == "entry level")
            check("TC-019  category is the closest member (writing/design)",
                  intent["category"] in ("writing", "design"))
            check("TC-019  2-3 variants generated for expansion",
                  2 <= len(intent["variants"]) <= intent_parser.MAX_VARIANTS)
            check("TC-019  original query leads the variants",
                  intent["variants"][0] == srs_query)
            print(f"\n     intent: {intent}")

            # Added 2026-10-13. Variants are now job titles and conditions go in the closed-set
            # keys. Before the change this query's variants were "tech jobs no degree" and
            # "entry level tech positions", and every source's AND match came back near-empty.
            no_degree = "I want to get into tech but I have no degree"
            nd = intent_parser.parse_intent(no_degree)
            if nd["source"] == "llm":
                check("'no degree' is read as entry level", nd["experience"] == "entry level")
                check("'tech' is read as the technology category",
                      nd["category"] == "technology")
                check("no generated variant carries the condition 'degree'",
                      all("degree" not in v.lower() for v in nd["variants"][1:]))
                check("the generated variants are short, like advert titles",
                      all(len(v.split()) <= 4 for v in nd["variants"][1:]))
                print(f"     no-degree variants: {nd['variants'][1:]}")

            # The guard on that change. Told to translate vague wishes into titles, the model
            # also "translated" gibberish into "Data entry clerk", which made TC-018's
            # no-results message unreachable. Nonsense must get no invented titles.
            gib = intent_parser.parse_intent("qwertyuiop zxcvbnm asdfgh")
            if gib["source"] == "llm":
                check("gibberish gets no invented job titles",
                      gib["variants"] == ["qwertyuiop zxcvbnm asdfgh"])

    finally:
        intent_parser._client = None

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for label in FAILED:
        print(f"  FAILED: {label}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
