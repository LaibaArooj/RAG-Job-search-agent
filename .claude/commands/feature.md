---
description: Build one feature end to end — research, plan, implement, test
argument-hint: [feature description or issue number]
---

Build: $ARGUMENTS

Follow these four steps in order. Do not skip ahead to implementation.

**1. Research** (skip for small, well-understood changes)
   - If an issue number was given, read it with `gh issue view`.
   - Read `docs/PROJECT_SPEC.md` and `docs/ARCHITECTURE.md` for relevant context.
   - Use the Explore subagent to find the existing code this touches.
   - If the feature needs an unfamiliar API or library, look up current docs with web search.

**2. Plan**
   - Enter plan mode. Produce an implementation plan: files to create or change,
     the order to do them in, the data model impact, and the test strategy.
   - Ask me any clarifying question where the spec is ambiguous.
   - Wait for my approval.

**3. Implement**
   - Create a branch: `feat/<short-desc>`.
   - Work through the plan. Use parallel subagents only where the pieces are genuinely
     independent.
   - Follow every constraint in `CLAUDE.md`.

**4. Test**
   - Write or update tests for the new behaviour.
   - Run the full lint and test suite. Fix what breaks.
   - For UI work, verify the flow actually works, not just that it compiles.

When it's green: update the docs (`/update-docs`), then commit and open a PR.
