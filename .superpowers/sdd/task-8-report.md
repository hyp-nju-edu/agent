# Task 8 Report: GuardrailPipeline (aggregation)

## Status: DONE

## What I Implemented

Appended `GuardrailPipeline` to `sentinel/core/guardrails.py` and 4 test cases to `tests/test_guardrails.py`, following strict TDD (RED → GREEN → commit).

### `GuardrailPipeline` (sentinel/core/guardrails.py)

A guardrail aggregator that runs a list of guardrails and combines their results with fail-closed semantics:

1. **Any `DENY` → `DENY`** (short-circuit on the decision aggregation; the first DENY result is returned before approvals are considered).
2. **Else any `REQUIRE_APPROVAL` → `REQUIRE_APPROVAL`** with the **highest risk level** among the approval results (selected via `max(approvals, key=lambda x: x.risk_level)`).
3. **Else `ALLOW`** (returns the first ALLOW result).
4. **Fallback** for an empty pipeline: `GuardrailResult(Decision.ALLOW, "no guardrails", RiskLevel.LOW, "pipeline")`.

The constructor takes a `list[Guardrail]` and defensively copies it (`list(guardrails)`) to prevent external mutation.

### Test cases (tests/test_guardrails.py)

- `test_pipeline_deny_short_circuits` — `rm -rf /` through PatternGuardrail+ScopeFenceGuardrail → DENY.
- `test_pipeline_require_approval_when_network` — `pip install requests` through PatternGuardrail+SandboxBoundaryGuardrail → REQUIRE_APPROVAL.
- `test_pipeline_allow_when_safe` — `pytest` through PatternGuardrail+SandboxBoundaryGuardrail → ALLOW.
- `test_pipeline_highest_risk_wins` — `pip install x` through SandboxBoundaryGuardrail+RiskClassifierGuardrail → REQUIRE_APPROVAL with `RiskLevel.HIGH`.

## TDD Evidence

### RED (before implementation)

Appended the 4 tests + `GuardrailPipeline` import. Running `python -m pytest tests/test_guardrails.py -v` failed during collection with:

```
ImportError: cannot import name 'GuardrailPipeline' from 'sentinel.core.guardrails'
```

This matches the brief's predicted RED state exactly.

### GREEN (after implementation)

After appending `GuardrailPipeline`, all guardrail tests pass:

```
tests/test_guardrails.py::test_pipeline_deny_short_circuits PASSED       [ 86%]
tests/test_guardrails.py::test_pipeline_require_approval_when_network PASSED [ 91%]
tests/test_guardrails.py::test_pipeline_allow_when_safe PASSED           [ 95%]
tests/test_guardrails.py::test_pipeline_highest_risk_wins PASSED         [100%]
============================= 23 passed in 0.07s ==============================
```

Full suite regression check: **46 passed in 0.31s** (test_guardrails, test_llm, test_sandbox, test_tools, test_types). No existing tests broken.

## Files Changed

- `sentinel/core/guardrails.py` — appended `GuardrailPipeline` class (+21 lines).
- `tests/test_guardrails.py` — added `GuardrailPipeline` to existing import block; appended 4 test functions (+20 lines).

## Commits

- `bfab311` — `feat(governance): add GuardrailPipeline with deny/approve aggregation`

## Self-Review Findings

1. **Implementation matches brief verbatim.** The `GuardrailPipeline` class is exactly as specified in the task brief — no deviations.
2. **Fail-closed guarantee holds.** A dangerous action that any guardrail DENYs will always produce a DENY from the pipeline, because the DENY scan runs before any approval/allow logic. The aggregation can never let a dangerous action through.
3. **`max` over `RiskLevel` works correctly.** `RiskLevel` defines `__lt__`/`__gt__`/`__le__`/`__ge__` via the `_ORDER` mapping (LOW=0 < MEDIUM=1 < HIGH=2 < CRITICAL=3), so `max(approvals, key=lambda x: x.risk_level)` selects the genuinely highest risk. Verified by `test_pipeline_highest_risk_wins`.
4. **Defensive copy.** `self._guardrails = list(guardrails)` prevents callers from mutating the pipeline's guardrail list after construction.
5. **Import style.** Added `GuardrailPipeline` to the existing multi-line import block rather than introducing a duplicate `from sentinel.core.guardrails import GuardrailPipeline` line — idiomatic and avoids redundant imports.
6. **No comments added** (per global constraints).
7. **No existing tests broken** — 19 prior guardrail tests + 27 other tests all still pass.

## Concerns

- **Minor (non-blocking):** The implementation evaluates *all* guardrails eagerly via the list comprehension `results = [g.check(action, ctx) for g in self._guardrails]` before scanning for DENY. This is the verbatim spec from the brief, and "short-circuit" in the brief refers to the *decision aggregation* (DENY is returned without considering approvals), not lazy evaluation of guardrails. True lazy short-circuiting would skip later guardrails once a DENY is found, which could be a future optimization but is out of scope for this task. No change needed — matches spec.

- **Minor (non-blocking):** The empty-pipeline fallback returns `ALLOW`. This is fail-*open* for an empty pipeline, but an empty pipeline is an explicit configuration choice (no guardrails configured), not a dangerous action slipping through. The brief explicitly specifies this fallback, so it is correct per spec. A production deployment should validate that pipelines are non-empty at construction time, but that is a separate concern outside this task's scope.

---

## Task 8 Review Fix — highest-risk-wins genuinely exercised

### Finding (Important)

`test_pipeline_highest_risk_wins` used `GuardrailPipeline([SandboxBoundaryGuardrail(), RiskClassifierGuardrail()])` on `pip install x`. But `RiskClassifierGuardrail` returns `ALLOW` (it only classifies, never blocks), so the pipeline had only ONE `REQUIRE_APPROVAL` result (from `SandboxBoundaryGuardrail`). `max()` over a one-element list is trivial — the highest-risk-wins selection logic and `RiskLevel` comparison operators were never actually exercised. Replacing `max` with `min` would still have passed.

### Fix

Added a NEW test `test_pipeline_highest_risk_wins_two_approvals` alongside the existing test (kept the original). The new test uses two inline stub guardrail classes that BOTH return `REQUIRE_APPROVAL` at DIFFERENT risk levels:

- `_MediumApproval` → `REQUIRE_APPROVAL` / `RiskLevel.MEDIUM` / name `"med"`
- `_HighApproval` → `REQUIRE_APPROVAL` / `RiskLevel.HIGH` / name `"high"`

The pipeline therefore collects TWO approvals and must select the higher via `max(approvals, key=lambda x: x.risk_level)`. The test asserts the returned result is `REQUIRE_APPROVAL` with `RiskLevel.HIGH` and `guardrail_name == "high"`. Replacing `max` with `min` would now return the MEDIUM result and fail the `risk_level == RiskLevel.HIGH` assertion, so the selection logic is genuinely exercised.

### Implementation status

**No implementation fix needed.** The existing `GuardrailPipeline.check` already uses `max(approvals, key=lambda x: x.risk_level)`, and `RiskLevel` defines `__lt__`/`__gt__`/`__le__`/`__ge__` via the `_ORDER` mapping (LOW=0 < MEDIUM=1 < HIGH=2 < CRITICAL=3). The new test passes against the unmodified implementation, confirming the highest-risk-wins logic is correct.

### Verification

- New test alone: `tests/test_guardrails.py::test_pipeline_highest_risk_wins_two_approvals PASSED`.
- Full guardrail suite: 24 passed (was 23; +1 new test).
- Full project suite: **47 passed in 0.32s** — no regressions.

### Files Changed

- `tests/test_guardrails.py` — added `GuardrailResult` to the `sentinel.core.types` import; appended `_MediumApproval` / `_HighApproval` stub classes and `test_pipeline_highest_risk_wins_two_approvals` (+23 lines net). No changes to `sentinel/core/guardrails.py`.

### Commits

- `c2756a5` — `test(governance): exercise highest-risk-wins with two approval guardrails`
