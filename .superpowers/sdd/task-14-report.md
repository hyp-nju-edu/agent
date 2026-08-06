# Task 14: Memory Store — Report

## What I Implemented

Created `sentinel/core/memory.py` with `MemoryStore` — a self-implemented memory store using stdlib `sqlite3` for persistence and TF-IDF for relevance ranking. No agent frameworks, no external vector DB.

**Interface:**
- `MemoryStore(path: str = ":memory:")` — opens/creates a SQLite DB with a `memory` table.
- `add(kind, key, content) -> int` — inserts a row, returns `lastrowid`.
- `search(query, limit=5) -> list[str]` — TF-IDF ranked retrieval of content strings.

**TF-IDF mechanics:**
- Tokenize via `re.findall(r"\w+", text.lower())`.
- Compute document frequency (df) across all stored docs.
- `idf[t] = log((n+1)/(df[t]+1)) + 1` (smoothed).
- Score each doc as `sum(tf[t] * idf[t] for t in query_tokens)`.
- Sort descending by score; return top `limit` with `score > 0`.
- Empty query → return first `limit` rows (any results).
- Fallback: if no doc scores > 0, return first row's content (ensures non-empty result when docs exist).

## TDD Evidence

### RED (before implementation)
```
tests\test_memory.py:1: in <module>
    from sentinel.core.memory import MemoryStore
E   ModuleNotFoundError: No module named 'sentinel.core.memory'
ERROR tests/test_memory.py
1 error in 0.23s
```

### GREEN (after implementation)
```
tests/test_memory.py::test_add_and_search PASSED                         [ 33%]
tests/test_memory.py::test_search_ranks_relevant PASSED                  [ 66%]
tests/test_memory.py::test_empty_query_returns_any PASSED                [100%]
3 passed in 0.11s
```

### Full suite (no regressions)
```
83 passed in 0.41s
```
(80 prior + 3 new)

## Files Changed

- **Created:** `sentinel/core/memory.py` (54 lines) — `MemoryStore` class + `_tokens` helper.
- **Created:** `tests/test_memory.py` (24 lines) — 3 tests verbatim from the brief.

## Commit

- `add49ba` — `feat(memory): add self-implemented SQLite + TF-IDF MemoryStore`

## Self-Review Findings

1. **Stdlib-only compliance** ✓ — only `math`, `re`, `sqlite3`, `time`, `collections.Counter`. No langchain/llamaindex/chromadb/etc.
2. **Interface conformance** ✓ — `add(kind, key, content)` and `search(query, limit) -> list[str]` match the brief exactly.
3. **TF-IDF correctness** ✓ — smoothed idf prevents division-by-zero; query-token-only scoring is standard TF-IDF dot-product.
4. **Empty-query behavior** ✓ — returns first `limit` rows when query tokenizes to nothing.
5. **Conventions** ✓ — `from __future__ import annotations`, no comments, simple class, matches `audit.py`/`hitl.py` style.
6. **Test isolation** ✓ — each test uses its own `tmp_path / "mem.db"`, no shared state.
7. **Code is verbatim from the brief** — no creative deviations.

## Concerns

- **Non-empty query with zero matches returns the first row** (the `or [rows[0][3]]` fallback). This is per the brief's spec, but means a query like `"zzz"` against docs that don't contain `"zzz"` will still return a result rather than an empty list. Acceptable for the task scope; flagged for awareness.
- **No lint/typecheck tooling configured** in `pyproject.toml` (only pytest + pytest-asyncio in dev deps). Could not run ruff/mypy. Not a regression — prior tasks have the same constraint.
- **CRLF line-ending warnings** from git on Windows — cosmetic only, no functional impact.
- **No connection closing** (`__del__`/context manager). Acceptable for the harness scope; SQLite handles cleanup on process exit. Could add `close()` later if needed.
