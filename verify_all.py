"""Run every verification script and print one summary — the pre-demo check.

Run with the dev server stopped:  python verify_all.py

Order matters. The offline and cheap checks run first, so a broken data layer or a broken
pipeline is reported before anything spends Adzuna quota on the live run.

    verify_db.py      data layer against Atlas          TC-001/002/010..013
    verify_agent.py   the pipeline, fully offline       TC-006/016..018/021/022
    verify_auth.py    the real routes and session       TC-001..005
    verify_routes.py  save/reject over HTTP             TC-010/011/013
    verify_intent.py  intent parsing, one live Groq call TC-019/020
    verify_live.py    the real APIs and rendered pages  the 2026-09-20 defects

verify_live.py is excluded by default with --offline, because it is the only one that costs
Adzuna quota. Everything else is safe to run as often as you like.
"""

import subprocess
import sys
import time

# The Windows console defaults to cp1252, which cannot encode the em dashes and
# arrows these scripts print, and an encoding crash midway through a check run is a
# uniquely unhelpful failure.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# (script, one-line purpose, costs Adzuna quota)
SCRIPTS = [
    ("verify_db.py", "data layer against live Atlas", False),
    ("verify_agent.py", "search pipeline, fully offline", False),
    ("verify_auth.py", "auth routes, session and CSRF", False),
    ("verify_routes.py", "save/reject routes and categorisation", False),
    ("verify_intent.py", "intent parsing (one live Groq call)", False),
    ("verify_live.py", "real Adzuna/Himalayas/Groq + rendered pages", True),
]

SUMMARY = "passed,"


def run(script):
    """Run one verification script and return (passed, failed, ok, seconds)."""
    started = time.time()
    proc = subprocess.run(
        [sys.executable, script], capture_output=True, text=True, encoding="utf-8",
        errors="replace",
    )
    elapsed = time.time() - started
    output = (proc.stdout or "") + (proc.stderr or "")

    passed = failed = 0
    for line in output.splitlines():
        # Every script ends with a "N passed, M failed" line in the same shape.
        if SUMMARY in line:
            parts = line.replace(",", " ").split()
            try:
                passed = int(parts[parts.index("passed") - 1])
                failed = int(parts[parts.index("failed") - 1])
            except (ValueError, IndexError):
                continue
    return passed, failed, proc.returncode == 0, elapsed, output


def main():
    """Run each script in turn, printing a table and a single verdict."""
    offline_only = "--offline" in sys.argv
    scripts = [s for s in SCRIPTS if not (offline_only and s[2])]

    print("=" * 74)
    print("verify_all.py — " + ("offline checks only" if offline_only
                                else "full check, including the live APIs"))
    print("=" * 74)

    rows = []
    total_passed = total_failed = 0
    broke = []

    for script, purpose, costs_quota in scripts:
        flag = " [uses Adzuna quota]" if costs_quota else ""
        print(f"\n>>> {script} — {purpose}{flag}")
        passed, failed, ok, elapsed, output = run(script)
        total_passed += passed
        total_failed += failed

        if not ok and failed == 0:
            # Crashed rather than failing a check: show why, or the summary lies.
            broke.append(script)
            print(output[-1500:])
            rows.append((script, "CRASHED", elapsed))
        else:
            if failed:
                for line in output.splitlines():
                    if line.strip().startswith("FAIL"):
                        print("   " + line.strip())
            print(f"    {passed} passed, {failed} failed  ({elapsed:.1f}s)")
            rows.append((script, f"{passed} passed, {failed} failed", elapsed))

    print("\n" + "=" * 74)
    for script, result, elapsed in rows:
        print(f"  {script:<20} {result:<26} {elapsed:6.1f}s")
    print("-" * 74)
    print(f"  {'TOTAL':<20} {total_passed} passed, {total_failed} failed")
    print("=" * 74)

    if broke:
        print("\nCRASHED: " + ", ".join(broke))
        print("A crash is not a failed check — the script never reached its summary.")
        return 2
    if total_failed:
        print("\nNOT READY. Fix the failures above before moving on.")
        return 1
    print("\nAll green." + ("  (live API checks were skipped — run without --offline "
                            "before a demo)" if offline_only else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
