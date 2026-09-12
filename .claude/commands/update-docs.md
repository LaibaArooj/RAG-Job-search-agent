---
description: Sync all project docs with recent changes, then commit
allowed-tools: Read, Edit, Write, Grep, Glob, Bash(git *)
---

Bring the project documentation back in sync with the code.

1. Run `git log --oneline -20` and `git diff main...HEAD --stat` to see what has changed
   since the docs were last updated.
2. Update `docs/CHANGELOG.md` — add entries under the right headings for anything shipped
   that isn't already listed. Newest first. User-facing language, not commit messages.
3. Update `docs/PROJECT_STATUS.md` — milestone statuses, what's completed, what's in
   progress, and a "where we left off" note detailed enough for a cold start.
4. Update `docs/ARCHITECTURE.md` — only if components, folder layout, data model or
   external services actually changed.
5. Update `CLAUDE.md` — only if commands, stack or constraints changed. Keep it short;
   if something is getting long, move it into `docs/` and link to it instead.
6. If a feature that shipped is non-trivial, write or update its reference doc in
   `docs/features/`.
7. Stage the doc changes and commit with message `docs: sync project documentation`.

Report what you changed in three lines or fewer.
