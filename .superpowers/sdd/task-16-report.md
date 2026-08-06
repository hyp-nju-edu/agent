# Task 16 Report: Mechanism Demo (§A.6)

## What I Implemented

Created `tests/test_mechanism_demo.py` with three capstone tests reproducing the §A.6 mechanism demonstrations under `MockLLM`:

1. **① `test_demo_governance_intercept`** — MockLLM scripts `rm -rf /`; `PatternGuardrail` matches the fork-bomb/recursive-force pattern and denies at the guardrail layer (no approval path). Asserts `ActionDenied` emitted, no `ActionExecuted`.
2. **② `test_demo_feedback_self_correction`** — A `SwitchingRegistry` returns a failing `StubShell` on the first call (stdout contains `FAILED ... - assert 1 == 2`) and a succeeding one on the second. `PytestValidator` parses the `FAILED` line into an `assertion_failure`. Asserts `FeedbackReceived` with `passed=False`, an `assertion_failure` failure, and that the agent's next requested action contains `cat` (self-correction).
3. **③ `test_demo_hitl_depth`** — MockLLM scripts `pip install requests`; `SandboxBoundaryGuardrail` flags the network hint → `REQUIRE_APPROVAL` (HIGH); `ThresholdApprove` (default threshold MEDIUM) denies since HIGH > MEDIUM. Asserts `ApprovalNeeded`, `ActionDenied`, no `ActionExecuted`.

### Deviation from brief
- Added `assert any(e.type == "ApprovalNeeded" for e in events)` to ③. The task notes explicitly state "③ should assert this" (the loop yields `ApprovalNeeded` as of the Task 13 fix). This is a strict strengthening; the brief's verbatim code omitted it. All other code matches the brief verbatim.

## Test Results

```
tests/test_mechanism_demo.py::test_demo_governance_intercept      PASSED
tests/test_mechanism_demo.py::test_demo_feedback_self_correction  PASSED
tests/test_mechanism_demo.py::test_demo_hitl_depth                PASSED
3 passed in 0.06s
```

Full suite: **88 passed in 0.49s** (85 pre-existing + 3 new). No network, no Docker, no real LLM.

## Integration Bugs Found
None. All three demos passed on the first run, confirming Tasks 2–15 integrate correctly.

## Self-Review Findings

- **Determinism**: All three tests use `MockLLM` with scripted responses and in-process stubs. No I/O, no timers, no randomness. ✓
- **`StubShell` protocol conformance**: exposes `name = "run_shell"` and `risk_level = RiskLevel.HIGH` as class attributes, satisfying the `Tool` protocol's structural shape. ✓
- **`SwitchingRegistry`**: implements only `get()`/`names()` as the task notes specified; the loop calls exactly these two methods on the registry. ✓
- **Trace verification (①)**: `_shell_text` produces `"rm -rf / "`; the `PatternGuardrail` regex `\brm\b(?=.*(?:--recursive|\s-[a-z]*r))(?=.*(?:--force|\s-[a-z]*f))` matches (` -r` and ` -f` both satisfy the `\s-[a-z]*X` alternation via backtracking). Returns `DENY/CRITICAL`. Pipeline short-circuits on DENY. ✓
- **Trace verification (②)**: `pytest` cmd passes all guardrails (ALLOW/LOW from `PatternGuardrail`); `AutoApprove` is not invoked (decision is ALLOW, not REQUIRE_APPROVAL). First `tools.get` call → `SwitchingRegistry.calls=1` → failing tool. `PytestValidator` regex `FAILED\s+\S+.*?-\s*(.+)` captures `assert 1 == 2` → `ASSERTION_FAILURE`. Second call → succeeding tool. Agent's second LLM response requests `cat tests/test_foo.py`. ✓
- **Trace verification (③)**: `SandboxBoundaryGuardrail` matches `"pip install"` hint → `REQUIRE_APPROVAL/HIGH`. Pipeline returns this (only REQUIRE_APPROVAL result). Loop yields `ApprovalNeeded`, calls `ThresholdApprove.approve`: `HIGH > MEDIUM` → `DENIED`. Loop yields `ActionDenied`, `continue`s. ✓
- **Unused imports**: The brief imports `AutoDeny`, `Action`, `Decision`, `ActionState`, `PytestValidator` which are not directly referenced in the test bodies. Kept verbatim per the brief (they document the consumed surface area). Not a defect.
- **Redundant markers**: `@pytest.mark.asyncio` is redundant under `asyncio_mode = "auto"` but harmless and matches the brief.

## Concerns
None.
