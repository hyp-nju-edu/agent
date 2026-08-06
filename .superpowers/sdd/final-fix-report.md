# Final Whole-Branch Review Fix Report

**Date:** 2026-07-13
**Commit:** 255b8d0 — `fix(core): close final-review gaps (approve path, fail-closed guardrail/tool errors, hitl.contains, empty-pipeline deny)`
**Test result:** 97/97 passing (was 88; +9 new tests)

## Summary

All six Important findings from the final whole-branch review (Phase 1) were fixed
following TDD (RED → GREEN for behavior changes; coverage-gap tests verified
meaningful by temporarily breaking the path). No Minor findings were touched.

## Findings

### Finding 1: REQUIRE_APPROVAL→approve→execute path untested through the loop
**Status:** FIXED
**Files:** `tests/test_loop.py`
Added `test_loop_approve_then_execute_path_end_to_end`: uses
`SandboxBoundaryGuardrail` (`pip install requests` → REQUIRE_APPROVAL) +
`AutoApprove` + `StubShell`. Captures `action_id` from the `ApprovalNeeded`
event and asserts:
- `ApprovalNeeded` event present
- `ActionExecuted` event present
- `hitl.state(action_id) == ActionState.EXECUTED`

Verified the test is meaningful by temporarily disabling `mark_executed` —
the test failed (state stayed `EXECUTING`), then passed after restore.

### Finding 2: §A.6 demo ③ incomplete
**Status:** FIXED
**Files:** `tests/test_mechanism_demo.py`
Kept the existing deny-path test (`test_demo_hitl_depth`). Added two sibling
tests:
- `test_demo_hitl_depth_approve`: `AutoApprove` + `SandboxBoundaryGuardrail`
  + `pip install requests` → asserts `ApprovalNeeded`, `ActionExecuted`, and
  `hitl.state(action_id) == ActionState.EXECUTED`.
- `test_demo_hitl_depth_timeout`: `AutoDeny` (represents timeout-as-denial at
  the loop level) → asserts `ApprovalNeeded`, `ActionDenied`, no
  `ActionExecuted`, and an audit entry with `outcome="skipped"`.

The distinct `hitl.timeout()` transition remains tested in `tests/test_hitl.py`
(unchanged). Per instructions, no `TIMEOUT` approval decision was added.

### Finding 3: Guardrail exceptions not caught (spec §3.3 deviation)
**Status:** FIXED
**Files:** `sentinel/core/guardrails.py`, `tests/test_guardrails.py`
`GuardrailPipeline.check` now wraps each `g.check(action, ctx)` in try/except.
On exception, returns `GuardrailResult(Decision.DENY, f"guardrail error: {e}",
RiskLevel.CRITICAL, g.name)` (fail-closed, short-circuits to Deny).
Added `test_pipeline_guardrail_exception_denies_fail_closed` with a
`_RaisingGuardrail` that raises `RuntimeError("boom")`.

### Finding 4: Tool exceptions stop the loop (spec §3.1 deviation)
**Status:** FIXED
**Files:** `sentinel/core/loop.py`, `tests/test_loop.py`
`tool.execute(...)` is now wrapped in try/except. On exception,
`tool_result = ToolResult(success=False, error=str(e))`, then the loop
continues normally (yields `ActionExecuted` with `success=False`, runs
validator, etc.). Added `test_loop_tool_exception_yields_failed_execution_and_continues`
with a `RaisingTool` that raises — asserts `ActionExecuted` with `success=False`
and that the loop does not stop with `reason="error"`.

### Finding 5: Private `hitl._states` access
**Status:** FIXED
**Files:** `sentinel/core/hitl.py`, `sentinel/core/loop.py`, `tests/test_hitl.py`
Added public method `HITLStateMachine.contains(action_id) -> bool`. Updated
`loop.py` to use `hitl.contains(action.id)` instead of `action.id in hitl._states`.
Added three tests: `test_contains_returns_false_for_unknown`,
`test_contains_returns_true_after_submit`, `test_contains_returns_true_after_deny`.

### Finding 6: Empty pipeline returns ALLOW (fail-open, spec §4.2 deviation)
**Status:** FIXED
**Files:** `sentinel/core/guardrails.py`, `tests/test_guardrails.py`
`GuardrailPipeline.check` now returns `GuardrailResult(Decision.DENY, "no
guardrails configured", RiskLevel.CRITICAL, "pipeline")` for the empty case.
Also hardened the fall-through (no guardrail returned ALLOW) to Deny. Added
`test_pipeline_empty_denies_fail_closed`. No existing test relied on
empty-pipeline ALLOW (all 25 guardrail tests pass).

## Verification

- `python -m pytest -q` → **97 passed in 0.57s** (post-commit, fresh run)
- All new tests followed TDD: RED confirmed before GREEN for behavior changes
  (Findings 3, 4, 5, 6). Coverage-gap tests (Findings 1, 2 approve/timeout)
  verified meaningful by confirming they fail when the path is broken.
- No Minor findings touched. No `TIMEOUT` approval decision added. No
  memory/config wired into the loop.
