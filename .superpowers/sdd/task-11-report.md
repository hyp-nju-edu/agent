# Task 11: Audit Log — Report

## What I Implemented

Created `sentinel/core/audit.py` with:

- **`AuditEntry`** dataclass: `action_id`, `guardrail`, `decision` (Decision), `risk_level` (RiskLevel), `outcome` (default `""`), `reason` (default `""`), `timestamp` (default_factory `time.time`).
- **`AuditLog`** class — append-only, in-memory:
  - `append(entry)` — appends to internal `_entries` list.
  - `for_action(action_id)` — returns new list of entries matching `action_id`.
  - `query(**filters)` — returns entries where all `getattr(e, k) == v` for each filter pair.
  - `all()` — returns a shallow copy of the internal list.

Created `tests/test_audit.py` with 4 tests verbatim from the brief:
`test_append_and_for_action`, `test_query_by_decision`, `test_query_by_risk`, `test_all_returns_everything`.

## TDD Evidence

**RED** (test written before implementation):
```
tests\test_audit.py:2: in <module>
    from sentinel.core.audit import AuditEntry, AuditLog
E   ModuleNotFoundError: No module named 'sentinel.core.audit'
ERROR tests/test_audit.py
```

**GREEN** (after implementing `sentinel/core/audit.py`):
```
tests/test_audit.py::test_append_and_for_action PASSED                   [ 25%]
tests/test_audit.py::test_query_by_decision PASSED                       [ 50%]
tests/test_audit.py::test_query_by_risk PASSED                           [ 75%]
tests/test_audit.py::test_all_returns_everything PASSED                  [100%]
============================== 4 passed in 0.04s ==============================
```

**Full suite regression check:** `67 passed in 0.36s` — no regressions across all prior tasks.

## Files Changed

- `sentinel/core/audit.py` (new, 33 lines)
- `tests/test_audit.py` (new, 41 lines)

## Commits

- `e67cfb9` — `feat(governance): add append-only AuditLog`

## Self-Review Findings

**Append-only guarantee verified:**
- `AuditLog` exposes only `append`, `for_action`, `query`, `all` — no `delete`, `update`, `clear`, or `__setitem__`.
- `all()` returns `list(self._entries)` (a copy), so external mutation of the returned list cannot corrupt the log.
- `for_action` and `query` both return freshly-constructed lists (comprehension / new accumulator), so callers cannot mutate internal state via the returned list.

**Filter semantics match brief:** `query(**filters)` uses `all(getattr(e, k) == v for k, v in filters.items())`, correctly supporting `decision=Decision.DENY`, `risk_level=RiskLevel.CRITICAL`, and arbitrary attribute combinations.

**Conventions followed:**
- `from __future__ import annotations` + `from dataclasses import dataclass, field` matches the style of `sentinel/core/types.py`.
- Type hints on all public methods.
- No comments added (per global constraint).
- No agent orchestration frameworks introduced.
- Python 3.11+ compatible (uses `list[...]` syntax with future annotations).

## Concerns

1. **`AuditEntry` is not frozen.** The brief's dataclass omits `frozen=True`, so a caller holding a reference to an `AuditEntry` (e.g., obtained via `for_action` or `query`) can mutate its fields after it has been appended. For a strict audit log, entries should ideally be immutable. I followed the brief verbatim; flagging for future hardening (e.g., `@dataclass(frozen=True)` when SQLite swap-in lands).
2. **`query` raises `AttributeError` on unknown filter keys.** `getattr(e, k)` without a default will raise if a caller passes a filter key that doesn't correspond to an `AuditEntry` attribute. This is acceptable (programmer error) but could be made more graceful with a default sentinel if desired.
3. **No thread safety.** Not required by the brief and consistent with prior tasks (GuardrailPipeline, ApprovalPolicy, etc. are also single-threaded). Worth noting if the SQLite swap-in introduces concurrent access.
4. **No persistence.** In-memory only, as specified — SQLite swap-in is explicitly deferred.

None of the concerns block acceptance; all are forward-looking notes for the SQLite swap-in task.
