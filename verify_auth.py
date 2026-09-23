"""Prove the M1 auth routes against the live app and Atlas — TC-001 to TC-005.

Run with the dev server stopped:  python verify_auth.py

Uses Flask's test client rather than a browser, so it exercises the real routes, the real
session cookie and the real database, with no new dependency. Every user it creates is named
with a random suffix and deleted at the end, so it can be re-run safely.

Deliberately not pytest: pytest is not in requirements.txt and adding a dependency needs
sign-off. This mirrors verify_db.py.
"""

import os
import uuid

# The app refuses to start without a signing key. Supply one for this process only if .env
# has not set it, so the checks can run before that key is added.
os.environ.setdefault("FLASK_SECRET_KEY", "verify-auth-only-not-for-serving")

import app as flask_app  # noqa: E402  (must follow the env default above)

PASSED = []
FAILED = []


def check(label, condition):
    """Record one assertion and print it as it happens."""
    (PASSED if condition else FAILED).append(label)
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")


def csrf_from(client, path):
    """Fetch a page and pull the CSRF token out of its form."""
    html = client.get(path).get_data(as_text=True)
    marker = 'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    return html[start : html.index('"', start)]


def main():
    """Run every M1 check in order and print a summary."""
    client_app = flask_app.app
    client_app.config["TESTING"] = True
    db = client_app.config["DB"]

    username = f"verify_{uuid.uuid4().hex[:10]}"
    password = "correct-horse-battery"

    try:
        print("\n1. Unauthenticated access")
        with client_app.test_client() as c:
            r = c.get("/feed")
            check("TC-005  /feed redirects when logged out", r.status_code == 302)
            check("TC-005  redirect target is /login", "/login" in r.headers["Location"])

            r = c.get("/")
            check("search page also redirects when logged out", r.status_code == 302)

            r = c.get("/profile")
            check("/profile redirects when logged out", r.status_code == 302)

            check("GET /login renders", c.get("/login").status_code == 200)

        print("\n2. CSRF")
        with client_app.test_client() as c:
            c.get("/register")
            r = c.post("/register", data={"username": username, "password": password})
            body = r.get_data(as_text=True)
            check("POST without a CSRF token is rejected", "session expired" in body)
            check("no account was created", db.get_user(username) is None)

        print("\n3. Registration")
        with client_app.test_client() as c:
            token = csrf_from(c, "/register")
            r = c.post(
                "/register",
                data={
                    "csrf_token": token,
                    "username": username,
                    "password": "short",
                    "skills": "python",
                },
            )
            check(
                "short password rejected",
                "at least 8 characters" in r.get_data(as_text=True),
            )
            check("still no account", db.get_user(username) is None)

            token = csrf_from(c, "/register")
            r = c.post(
                "/register",
                data={
                    "csrf_token": token,
                    "username": username,
                    "password": password,
                    "country": "gb",
                    "skills": "Python, Flask",
                    "experience": "entry level",
                    "location": "Remote",
                    "preferred_work": ["remote"],
                },
            )
            check("TC-001  registration redirects home", r.status_code == 302)
            doc = db.get_user(username)
            check("TC-001  user document stored in Atlas", doc is not None)
            check("TC-001  profile captured", doc.get("skills") == ["Python", "Flask"])
            check(
                "password stored as a Werkzeug hash, not plain text",
                doc.get("password", "").startswith(("pbkdf2:", "scrypt:"))
                and password not in doc.get("password", ""),
            )
            check("session opened by registration", c.get("/").status_code == 200)

        print("\n4. Duplicate registration")
        with client_app.test_client() as c:
            token = csrf_from(c, "/register")
            r = c.post(
                "/register",
                data={
                    "csrf_token": token,
                    "username": username,
                    "password": password,
                    "country": "gb",
                },
            )
            check("TC-002  'Username taken' shown", "Username taken" in r.get_data(as_text=True))
            check("TC-002  no second document", db.users.count_documents({"username": username}) == 1)

        print("\n5. Login")
        with client_app.test_client() as c:
            token = csrf_from(c, "/login")
            r = c.post(
                "/login",
                data={"csrf_token": token, "username": username, "password": "wrong-password"},
            )
            body = r.get_data(as_text=True)
            check("TC-004  'Invalid username or password.' shown", "Invalid username or password." in body)
            check("TC-004  no session granted", c.get("/").status_code == 302)

            token = csrf_from(c, "/login")
            r = c.post(
                "/login",
                data={"csrf_token": token, "username": "no_such_user_" + username, "password": password},
            )
            check(
                "unknown user gets the same message (no username oracle)",
                "Invalid username or password." in r.get_data(as_text=True),
            )

            token = csrf_from(c, "/login")
            r = c.post(
                "/login",
                data={"csrf_token": token, "username": username, "password": password},
            )
            check("TC-003  correct credentials redirect home", r.status_code == 302)
            check("TC-003  session created", c.get("/").status_code == 200)

            print("\n6. Profile update")
            token = csrf_from(c, "/profile")
            c.post(
                "/profile",
                data={
                    "csrf_token": token,
                    "skills": "Django, SQL",
                    "experience": "senior",
                    "location": "London",
                    "preferred_work": ["remote", "full-time"],
                },
            )
            doc = db.get_user(username)
            check("skills updated", doc.get("skills") == ["Django", "SQL"])
            check("experience updated", doc.get("experience") == "senior")
            check("work types updated", doc.get("preferred_work") == ["remote", "full-time"])

            token = csrf_from(c, "/profile")
            c.post(
                "/profile",
                data={
                    "csrf_token": token,
                    "skills": "Django, SQL",
                    "experience": "wizard",
                    "location": "London",
                    "preferred_work": ["remote", "sabbatical"],
                },
            )
            doc = db.get_user(username)
            check("unknown experience level ignored", doc.get("experience") == "senior")
            check("unknown work type dropped", doc.get("preferred_work") == ["remote"])

            token = csrf_from(c, "/profile")
            c.post(
                "/profile",
                data={"csrf_token": token, "skills": "x", "password": "hijacked"},
            )
            doc = db.get_user(username)
            check("profile form cannot overwrite the password", doc["password"] != "hijacked")

            print("\n7. Logout")
            r = c.get("/logout")
            check("logout redirects to /login", "/login" in r.headers["Location"])
            check("session cleared", c.get("/").status_code == 302)

            token = csrf_from(c, "/login")
            r = c.post(
                "/login",
                data={"csrf_token": token, "username": username, "password": password},
            )
            check("can log back in after logout", r.status_code == 302)

    finally:
        print("\n8. Cleanup")
        try:
            db.users.delete_many({"username": username})
            check("throwaway user removed", db.get_user(username) is None)
        except Exception as e:
            check(f"cleanup failed: {e}", False)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for label in FAILED:
        print(f"  FAILED: {label}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
