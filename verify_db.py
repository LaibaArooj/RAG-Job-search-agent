"""Standalone check that the database layer works end to end against MongoDB Atlas.

Run it the moment the Atlas credential is fixed, and again in front of the examiner:

    venv\\Scripts\\python.exe verify_db.py

It creates a throwaway user, exercises every DatabaseManager method, asserts the behaviour
TC-001, TC-002, TC-010, TC-011, TC-012 and TC-013 require, and deletes the user afterwards.
Safe to re-run.

Not a pytest suite: pytest is not a project dependency and adding one needs asking first.
"""

import sys

from pymongo.errors import PyMongoError
from werkzeug.security import check_password_hash, generate_password_hash

import config
from adapters.db_manager import DatabaseManager

TEST_USER = "__verify_db_throwaway__"

JOB = {
    "job_id": "verify-job-0001",
    "title": "Technical Writer",
    "company": "Example Ltd",
    "location": "Remote",
    "source": "Remotive",
    "url": "https://example.com/job/1",
}

passed = failed = 0


def check(label, condition, detail=""):
    """Print one pass/fail line and tally the result."""
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}" + (f" -- {detail}" if detail else ""))
    return bool(condition)


def diagnose_connection():
    """Locate which layer a failed connection stops at: DNS, TCP, TLS or authentication."""
    import re
    import socket
    import ssl

    hosts = re.findall(r"@([^/?,]+)", config.MONGODB_URI or "")
    seed = hosts[0].split(",")[0].split(":")[0] if hosts else None
    if not seed:
        print("\n  Could not read a hostname out of MONGODB_URI.")
        return

    # A mongodb+srv:// URI names a lookup record, not a server. Resolve it to real shards.
    shards = []
    try:
        import dns.resolver  # bundled with pymongo[srv]

        answers = dns.resolver.resolve(f"_mongodb._tcp.{seed}", "SRV")
        shards = [str(r.target).rstrip(".") for r in answers]
        print(f"\n  DNS   SRV record resolves to {len(shards)} shard(s)")
    except Exception as e:
        print(f"\n  DNS   SRV lookup failed: {type(e).__name__}: {e}")
        shards = [seed]

    ctx = ssl.create_default_context()
    for host in shards:
        s = socket.socket()
        s.settimeout(15)
        try:
            s.connect((host, 27017))
            print(f"  TCP   {host}:27017 reachable")
        except Exception as e:
            print(f"  TCP   {host}:27017 unreachable -- {type(e).__name__}")
            s.close()
            continue
        try:
            ctx.wrap_socket(s, server_hostname=host)
            print(f"  TLS   {host}:27017 handshake OK -- fault is authentication, not network")
        except Exception as e:
            print(f"  TLS   {host}:27017 handshake FAILED -- {type(e).__name__}")
            print(
                "        TCP connects but TLS does not complete. Something between this\n"
                "        machine and Atlas is interfering with port 27017 -- commonly a\n"
                "        campus/ISP firewall or a TLS-inspecting antivirus. The credential\n"
                "        is not involved: authentication happens after this handshake.\n"
                "        Test by re-running on a phone hotspot."
            )
        finally:
            s.close()


def main():
    """Run every check in order, stopping early only if the connection itself fails."""
    print("\n1. Configuration")
    try:
        config.validate()
        check("all required environment variables present", True)
    except config.ConfigError as e:
        check("all required environment variables present", False, str(e))
        print("\nBlocked on configuration. Fix .env and re-run.")
        return 1
    check(f"category vocabulary loaded ({len(config.CATEGORIES)} categories)",
          len(config.CATEGORIES) > 0)
    check(f"job_cache TTL is {config.JOB_CACHE_TTL_MINUTES} min",
          config.JOB_CACHE_TTL_MINUTES == 60)

    db = DatabaseManager()

    print("\n2. Connection")
    if not check("Atlas answers ping", db.ping()):
        print(
            "\nBlocked before the database layer can be tested. Read the error above:\n"
            "  'bad auth' / AuthenticationFailed\n"
            "      The connection reached Atlas and Atlas rejected the credential. DNS,\n"
            "      TLS, the cluster and the IP allowlist are all therefore fine. Reset the\n"
            "      password: Atlas -> Database Access -> Edit -> Autogenerate Secure\n"
            "      Password, then paste it into MONGODB_URI in .env.\n"
            "  ServerSelectionTimeout / 'No replica set members found'\n"
            "      The connection never got far enough to authenticate, so the password is\n"
            "      NOT implicated. Run diagnose_connection() below to find out where it\n"
            "      stops."
        )
        diagnose_connection()
        return 1

    print("\n3. Indexes")
    db.ensure_indexes()
    idx = db.users.index_information()
    check("users.username index exists", "username_unique" in idx)
    check("users.username index is unique", bool(idx.get("username_unique", {}).get("unique")))
    cache_idx = db.job_cache.index_information()
    check("job_cache TTL index exists", "job_cache_ttl" in cache_idx)
    check(
        f"job_cache TTL is {config.JOB_CACHE_TTL_MINUTES * 60}s",
        cache_idx.get("job_cache_ttl", {}).get("expireAfterSeconds")
        == config.JOB_CACHE_TTL_MINUTES * 60,
    )

    print("\n4. User round trip")
    db.users.delete_one({"username": TEST_USER})  # clean any earlier aborted run

    pw_hash = generate_password_hash("correct-horse-battery-staple")
    ok, msg = db.create_user(TEST_USER, pw_hash, {"skills": ["Python"], "experience": "entry"})
    check("TC-001  user created", ok, msg)

    ok2, msg2 = db.create_user(TEST_USER, pw_hash)
    check("TC-002  duplicate username rejected", not ok2 and msg2 == "Username taken", msg2)

    user = db.get_user(TEST_USER)
    check("user fetched by username", user is not None)
    check("password stored as a hash, not plain text",
          user["password"] != "correct-horse-battery-staple")
    check("stored hash verifies", check_password_hash(user["password"], "correct-horse-battery-staple"))

    ctx = db.get_user_context(TEST_USER)
    check("get_user_context omits the password", ctx is not None and "password" not in ctx)

    print("\n5. Save / reject scoring")
    check("TC-010  save returns True first time", db.save_job(TEST_USER, JOB, "writing"))
    u = db.get_user(TEST_USER)
    check("TC-010  writing score is +1", u["category_scores"].get("writing") == 1,
          str(u["category_scores"]))

    second = db.save_job(TEST_USER, JOB, "writing")
    u = db.get_user(TEST_USER)
    check("TC-013  second save returns False", second is False)
    check("TC-013  score still +1, not +2", u["category_scores"].get("writing") == 1,
          str(u["category_scores"]))
    check("TC-013  saved_jobs holds one entry", len(u["saved_jobs"]) == 1, str(len(u["saved_jobs"])))

    other = dict(JOB, job_id="verify-job-0002", title="Backend Engineer")
    db.reject_job(TEST_USER, other, "technology")
    u = db.get_user(TEST_USER)
    check("TC-011  technology score is -1", u["category_scores"].get("technology") == -1,
          str(u["category_scores"]))
    check("rejected_jobs stores job_id (Deviation 4)", u["rejected_jobs"] == ["verify-job-0002"],
          str(u["rejected_jobs"]))

    print("\n6. Injection guard")
    try:
        db.save_job(TEST_USER, JOB, "writing.$ne")
        check("field-path injection rejected", False, "no exception raised")
    except ValueError:
        check("field-path injection rejected", True)

    print("\n7. Feed and history")
    tops = db.get_top_categories(TEST_USER)
    check("TC-012  top categories include writing", "writing" in tops, str(tops))
    check("TC-012  negatively scored technology excluded", "technology" not in tops, str(tops))

    db.add_search_history(TEST_USER, "remote writing job")
    u = db.get_user(TEST_USER)
    check("search history recorded", u["search_history"] == ["remote writing job"])

    print("\n8. Job cache")
    db.cache_put("verify-hash", "remote python developer", [{"title": "x"}])
    entry = db.cache_get("verify-hash")
    check("cache round trip", entry is not None and entry["query_text"] == "remote python developer")
    db.job_cache.delete_one({"_id": "verify-hash"})

    print("\n9. Cleanup")
    db.users.delete_one({"username": TEST_USER})
    check("throwaway user removed", db.get_user(TEST_USER) is None)

    db.close()
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except PyMongoError as e:
        print(f"\nMongoDB error: {e}")
        sys.exit(1)
