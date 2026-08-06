# Task 10 Report: HITL State Machine

## What I Implemented

Created `sentinel/core/hitl.py` providing the Human-In-The-Loop governance state machine:

- **`ActionState`** — `str, Enum` with six states: `PROPOSED`, `PENDING_APPROVAL`, `EXECUTING`, `EXECUTED`, `FAILED`, `SKIPPED`.
- **`HITLStateMachine`** — in-memory tracker for each action's governance lifecycle. Methods:
  - `submit(action: Action) -> ActionState` — records the action and returns `PENDING_APPROVAL`.
  - `approve(action_id) -> ActionState` — `PENDING_APPROVAL` → `EXECUTING`.
  - `deny(action_id) -> ActionState` — `PENDING_APPROVAL` → `SKIPPED`.
  - `timeout(action_id) -> ActionState` — `PENDING_APPROVAL` → `SKIPPED` (fail-closed: no execution without explicit approval).
  - `mark_executed(action_id, success: bool) -> ActionState` — `EXECUTING` → `EXECUTED` (success) or `FAILED` (failure).
  - `state(action_id) -> ActionState` — read-only accessor.
  - `_require(action_id, expected)` — internal guard; raises `KeyError` for unknown actions and `PermissionError` for illegal transitions.

Created `tests/test_hitl.py` with the 8 test cases verbatim from the brief.

## TDD Evidence

### RED (before implementation)
```
tests\test_hitl.py:3: in <module>
    from sentinel.core.hitl import HITLStateMachine, ActionState
E   ModuleNotFoundError: No module named 'sentinel.core.hitl'
=========================== 1 error in 0.23s ===============================
```

### GREEN (after implementation)
```
tests/test_hitl.py::test_submit_sets_pending PASSED                      [ 12%]
tests/test_hitl.py::test_approve_transitions_to_executing PASSED         [ 25%]
tests/test_hitl.py::test_deny_transitions_to_skipped PASSED              [ 37%]
tests/test_hitl.py::test_timeout_transitions_to_skipped PASSED           [ 50%]
tests/test_hitl.py::test_executed_after_approved PASSED                  [ 62%]
tests/test_hitl.py::test_failed_after_approved PASSED                    [ 75%]
tests/test_hitl.py::test_illegal_transition_raises PASSED                [ 87%]
tests/test_hitl.py::test_unknown_action_raises PASSED                    [100%]
============================== 8 passed in 0.04s ==============================
```

### Full suite (no regressions)
```
63 passed in 0.33s
```

## Files Changed

| File | Change |
|------|--------|
| `sentinel/core/hitl.py` | New (66 lines) — `ActionState` enum + `HITLStateMachine` |
| `tests/test_hitl.py` | New (41 lines) — 8 test cases from brief |

## Commit

```
f049803 feat(governance): add HITL state machine with fail-closed transitions
```

## Self-Review Findings

- ✅ All six required states present in `ActionState`.
- ✅ Transition table matches the brief exactly: `submit→PENDING_APPROVAL`, `approve→EXECUTING`, `deny/timeout→SKIPPED`, `mark_executed(success)→EXECUTED|FAILED`.
- ✅ Fail-closed verified: `mark_executed` requires `EXECUTING` state, which is only reachable via `approve()`. No path from `PENDING_APPROVAL` directly to `EXECUTED`/`FAILED`. `timeout` → `SKIPPED` ensures a stalled approval never silently executes.
- ✅ Illegal transitions raise `PermissionError` (tested: `mark_executed` before `approve`).
- ✅ Unknown action raises `KeyError` (tested: `approve("nope")`).
- ✅ `ActionState` subclasses `str, Enum` — consistent with `RiskLevel`/`Decision`/`ApprovalDecision` in `types.py`, enabling value-based comparisons and serialization.
- ✅ Conventional Commit format matches prior governance commits.
- ✅ No comments added (per repo style); `from __future__ import annotations` used consistently with sibling modules.
- ✅ No regressions: full suite 63/63 passing.

## Concerns

- **`PROPOSED` state is currently unreachable** via any transition in this implementation — `submit()` jumps straight to `PENDING_APPROVAL`. This matches the brief verbatim, and `PROPOSED` is listed as a valid state in the global constraints, so it is retained as a reserved state for future use (e.g., pre-submission drafting). Not a defect, but worth flagging for downstream tasks that may need a `propose()` entry point.
- **`state(action_id)` for an unknown id raises `KeyError`** via raw dict access (not via `_require`). This is consistent with the "unknown action raises KeyError" contract but is not explicitly tested. Behavior is correct; only test coverage gap noted.
- **No persistence / no thread-safety.** In-memory, single-instance. Appropriate for current scope; downstream tasks integrating with a real agent loop may need to revisit if actions span processes or threads.
- **`timeout` and `deny` are behaviorally identical** (both `PENDING_APPROVAL → SKIPPED`). Distinct methods are retained per the brief's interface contract so callers can express intent; downstream telemetry/audit may want to distinguish them via an event log rather than state alone.
