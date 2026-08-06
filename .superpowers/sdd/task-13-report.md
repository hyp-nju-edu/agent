# Task 13: Agent Main Loop — Report

## What I Implemented

Created `sentinel/core/loop.py` containing `async def agent_loop(...)` — the integration kernel that wires together every prior module (LLM, tools, guardrails, approval, sandbox, audit, HITL, feedback) into a single async generator yielding `Event` objects.

### Loop flow (per turn, up to `max_turns`):
1. Yield `TurnStarted`.
2. Call `llm.complete(messages, tools.names())` → yield `LLMResponse`.
3. If no `tool_calls` → yield `Stopped(reason="done")` and return.
4. For each tool call:
   - Build an `Action` (uuid id, turn_id) → yield `ActionRequested`.
   - Run `pipeline.check(action, ctx)` → append `AuditEntry`.
   - **DENY** → yield `ActionDenied`, `continue` (skip execution).
   - **REQUIRE_APPROVAL** → `hitl.submit` → `approval_policy.approve`:
     - DENIED → `hitl.deny`, append audit (outcome="skipped"), yield `ActionDenied`, `continue`.
     - APPROVED → `hitl.approve`.
   - **ALLOW** → falls through directly to execution (no HITL tracking).
   - Execute tool via `tools.get(action.tool).execute(args, sandbox)`.
   - **Corrected guard**: `if action.id in hitl._states: hitl.mark_executed(...)` — only fires for actions that went through REQUIRE_APPROVAL. This fixes the brief's buggy inline `mark_executed` which would KeyError on the ALLOW path.
   - Yield `ActionExecuted`.
   - `select_validator(action).parse(tool_result, action)` → yield `FeedbackReceived`.
   - Re-inject tool stdout into `messages` as `{"role": "tool", ...}`.
5. Yield `TurnComplete`.
6. After loop exhausts → yield `Stopped(reason="max_turns")`.

## TDD Evidence

### RED (before implementation)
```
tests/test_loop.py:12: in <module>
    from sentinel.core.loop import agent_loop
E   ModuleNotFoundError: No module named 'sentinel.core.loop'
============================== 1 error in 0.25s ==============================
```

### GREEN (after implementation)
```
tests/test_loop.py::test_loop_runs_safe_action_and_stops PASSED          [ 33%]
tests/test_loop.py::test_loop_denies_dangerous_action PASSED             [ 66%]
tests/test_loop.py::test_loop_stops_on_max_turns PASSED                  [100%]
============================== 3 passed in 0.05s ==============================
```

### Full suite regression
```
79 passed in 0.35s
```

## Files Changed
- **Created** `sentinel/core/loop.py` (77 lines) — the async agent loop.
- **Created** `tests/test_loop.py` (93 lines) — 3 tests copied verbatim from the brief (StubTool + _events helper included).

## Commit
```
9807435 feat(core): add async agent_loop with governance + feedback integration
```

## Self-Review Findings

### Correct
- **Corrected `mark_executed` guard applied** — `if action.id in hitl._states:` ensures only REQUIRE_APPROVAL actions walk the HITL state machine to EXECUTED/FAILED. ALLOW-path actions skip this (they were never `submit`-ed, so `mark_executed` would raise `KeyError`). This matches the brief's Step 4 note exactly.
- **Stop conditions** — "done" (no tool_calls) and "max_turns" both verified by tests.
- **Same code path in tests and prod** — the loop is a single async generator; tests drive it with MockLLM + AutoApprove, prod would use real LLM + real approval policy.
- **Feedback re-injection** — tool stdout appended to `messages` for the next LLM turn.
- **Audit trail** — every guardrail decision and every approval denial is appended to the AuditLog.
- **Event coverage** — TurnStarted, LLMResponse, ActionRequested, ActionDenied, ActionExecuted, FeedbackReceived, TurnComplete, Stopped all yielded.

### Concerns (non-blocking)

1. **No `ApprovalNeeded` event yielded.** The global constraints list "ApprovalNeeded (if applicable)" among events to yield, but the brief's verbatim Step 3 code does NOT yield it — it goes straight from REQUIRE_APPROVAL to calling `approval_policy.approve`. I followed the brief (source of truth) since the tests don't assert on `ApprovalNeeded`. If a human-in-the-loop async approval flow is needed later, an `ApprovalNeeded` event should be yielded before awaiting `approval_policy.approve` so a consumer can render a UI.

2. **No error/exception stop condition.** The global constraints mention "Stop conditions: ... or error" but the brief's code has no try/except. If `tool.execute` or `llm.complete` raises, the exception propagates out of the generator and the loop terminates without yielding a `Stopped(reason="error")` event. This matches the brief verbatim, but a production-hardened loop should wrap the turn body in try/except and yield `Stopped(reason="error", data={"exception": ...})`.

3. **Private attribute access `hitl._states`.** The brief's Step 4 note explicitly instructs `if action.id in hitl._states:`. This couples the loop to HITL's internal dict. A cleaner API would expose `hitl.tracks(action_id) -> bool` or `hitl.state(action_id) -> ActionState | None`. Noted for future refactor; matches spec as written.

4. **Unused imports.** `Any` (from typing) and `ToolResult` are imported but not directly referenced in the loop body — they flow through implicitly via tool.execute's return. These match the brief's verbatim import block; left as-is for fidelity. A stricter linter (ruff F401) would flag them.

5. **`_events` helper in test file is unused** by the 3 async tests (they consume via `async for` directly). It's copied verbatim from the brief; left in place.

## Conclusion

Task 13 is complete. The loop integrates all prior modules, passes all 3 specified tests plus the full 79-test regression suite, and uses the corrected `mark_executed` guard as instructed. Concerns are non-blocking design notes for future hardening, not defects against the spec.

---

# Task 13 Review — Fix Report

Three Important findings from the Task 13 review were addressed via TDD (RED → GREEN).

## What Changed

### `sentinel/core/loop.py`
1. **Finding 1 — `ApprovalNeeded` event (Important):** After `hitl.submit(action)` and BEFORE `await approval_policy.approve(...)`, the loop now yields:
   ```python
   yield Event(type="ApprovalNeeded",
               data={"action_id": action.id,
                     "reason": result.reason,
                     "risk_level": result.risk_level.value})
   ```
   This satisfies SPEC §3.1 / §9.3, letting a consumer render an approval UI before the (potentially blocking) `approve` await.

2. **Finding 2 — error stop condition (Important):** The entire per-turn body (from `TurnStarted` through `TurnComplete`) is now wrapped in `try/except Exception as e:`. On any exception the loop yields `Event(type="Stopped", data={"reason": "error", "exception": str(e)})` and returns. No retry/backoff added (deferred as a future enhancement), per the brief.

3. **Minor (related) — explicit approval check:** Replaced the implicit "anything not DENIED → approve" fall-through with an explicit branch:
   ```python
   if approval.decision == ApprovalDecision.APPROVED:
       hitl.approve(action.id)
   else:
       hitl.deny(action.id); audit.append(...); yield ActionDenied; continue
   ```
   Behavior is unchanged (the enum only has APPROVED/DENIED) but the deny path is now explicit and robust against future enum additions.

### `tests/test_loop.py`
- Added `SandboxBoundaryGuardrail` to the guardrails import.
- Added `test_loop_denies_when_approval_rejected` (verbatim from the brief): drives `pip install x` through `SandboxBoundaryGuardrail` (→ REQUIRE_APPROVAL) with an `AutoDeny` policy, then asserts `ApprovalNeeded` is yielded, `ActionDenied` is yielded, and `ActionExecuted` is NOT yielded. This covers the previously-untested security-critical deny branch and simultaneously verifies Finding 1.

## TDD Evidence

### RED (test added before any production fix)
```
tests/test_loop.py::test_loop_denies_when_approval_rejected FAILED       [100%]
...
>       assert any(e.type == "ApprovalNeeded" for e in events)
E       assert False
...
========================= 1 failed, 3 passed in 0.21s =========================
```
The new test fails on the `ApprovalNeeded` assertion exactly as expected — the feature was missing. The other 3 tests remained green, confirming the failure was scoped to the missing behavior (not a typo/setup error).

### GREEN (after applying the three fixes)
```
tests/test_loop.py::test_loop_runs_safe_action_and_stops PASSED          [ 25%]
tests/test_loop.py::test_loop_denies_dangerous_action PASSED             [ 50%]
tests/test_loop.py::test_loop_stops_on_max_turns PASSED                  [ 75%]
tests/test_loop.py::test_loop_denies_when_approval_rejected PASSED       [100%]
============================== 4 passed in 0.06s ==============================
```

### Full suite regression
```
80 passed in 0.36s
```
(79 prior + 1 new test; no regressions.)

## Commit
```
8b4643c fix(core): yield ApprovalNeeded event, add error stop condition, test approval-deny path
```
