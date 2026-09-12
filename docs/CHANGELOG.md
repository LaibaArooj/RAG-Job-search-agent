# Changelog — RAG-Based Intelligent Job Search Agent

All notable changes, newest first. Claude appends an entry after each shipped feature.

## [Unreleased]

### Added
### Changed
### Fixed
### Removed

---

## 2026-09-13 — Search demo runs end to end

### Added
- `RAGPipeline` rebuilt against Groq, with `fallback()` satisfying FR-018: a Groq failure is
  caught and logged, the AI Recommendations panel hides, and the ranked results still render.
- `requirements.txt` — curated direct dependencies with pinned versions.

### Changed
- LLM model is now `groq/compound-mini`. Groq decommissioned Llama 3 mid-project; this is a
  forced substitution recorded in `docs/PROJECT_SPEC.md` § Deviations and **needs supervisor
  sign-off**. The model id is isolated in one constant, so a revert is one line.
- `app.py` calls `fetch_all_jobs()` instead of hitting Adzuna inline. This restores Remotive
  as a source, restores title+company deduplication, and keeps `requests` out of the route
  layer as the SDD requires.

### Fixed
- `rag_pipeline.py` had been overwritten with a byte-identical copy of `app.py`, so it imported
  `RAGPipeline` from itself and the app could not start at all.
- Adzuna returns `company` and `location` as nested objects. The inline fetch passed them to
  the template raw, which rendered them as Python dicts and left job links empty.
- Normalised-score divide is guarded — a zero or negative top similarity raised
  `ZeroDivisionError`, which would have shown a stack trace.
- `.gitignore` listed `models/`, which would have silently ignored the SDD's `models/` package.
- MongoDB URI username contained a Cyrillic `а` (U+0430) instead of Latin `a`, causing Atlas
  `bad auth`. Fixed; the DB user password is still outstanding.

### Removed
- Stale prototype scripts: the Gemini `rag_pipeline.py`, `test_groq.py`, `test_semantic.py`.

---

## 2026-09-11 — Project initialised

### Added
- PSB scaffold: project spec, CLAUDE.md, docs, commands and subagents.
