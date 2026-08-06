## Task 9: Approval Policies

**Files:**
- Create: `sentinel/core/approval.py`
- Test: `tests/test_approval.py`

**Interfaces:**
- Consumes: `Action`, `GuardrailResult`, `Approval`, `ApprovalDecision` from `types`.
- Produces: `ApprovalPolicy` protocol (`async approve(action, result) -> Approval`), `AutoApprove`, `AutoDeny`, `ThresholdApprove`.

- [ ] **Step 1: Write the failing test**

`tests/test_approval.py`:
```python
import pytest
from sentinel.core.types import Action, GuardrailResult, Decision, RiskLevel
from sentinel.core.approval import (
    ApprovalPolicy, AutoApprove, AutoDeny, ThresholdApprove,
)

def _r(decision, risk):
    return GuardrailResult(decision=decision, reason="x", risk_level=risk,
                           guardrail_name="g")

@pytest.mark.asyncio
async def test_auto_approve_allows():
    a = await AutoApprove().approve(Action("run_shell", {"cmd": "x"}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.HIGH))
    assert a.decision.value == "approved"

@pytest.mark.asyncio
async def test_auto_deny_denies():
    a = await AutoDeny().approve(Action("run_shell", {"cmd": "x"}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.HIGH))
    assert a.decision.value == "denied"

@pytest.mark.asyncio
async def test_threshold_approves_low():
    a = await ThresholdApprove().approve(Action("x", {}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.LOW))
    assert a.decision.value == "approved"

@pytest.mark.asyncio
async def test_threshold_denies_high():
    a = await ThresholdApprove().approve(Action("x", {}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.HIGH))
    assert a.decision.value == "denied"

@pytest.mark.asyncio
async def test_threshold_approves_medium():
    a = await ThresholdApprove().approve(Action("x", {}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.MEDIUM))
    assert a.decision.value == "approved"

def test_approval_policy_is_protocol():
    assert hasattr(ApprovalPolicy, "approve")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_approval.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`sentinel/core/approval.py`:
```python
from __future__ import annotations
from typing import Protocol, runtime_checkable

from sentinel.core.types import Action, Approval, ApprovalDecision, GuardrailResult, RiskLevel


@runtime_checkable
class ApprovalPolicy(Protocol):
    async def approve(self, action: Action, result: GuardrailResult) -> Approval: ...


class AutoApprove:
    async def approve(self, action: Action, result: GuardrailResult) -> Approval:
        return Approval(decision=ApprovalDecision.APPROVED, reason="auto-approve")


class AutoDeny:
    async def approve(self, action: Action, result: GuardrailResult) -> Approval:
        return Approval(decision=ApprovalDecision.DENIED, reason="auto-deny")


class ThresholdApprove:
    """Auto-approve low/medium; deny high/critical (deterministic for tests)."""

    def __init__(self, threshold: RiskLevel = RiskLevel.MEDIUM) -> None:
        self._threshold = threshold

    async def approve(self, action: Action, result: GuardrailResult) -> Approval:
        if result.risk_level <= self._threshold:
            return Approval(ApprovalDecision.APPROVED, "below threshold")
        return Approval(ApprovalDecision.DENIED, "above threshold")
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_approval.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/approval.py tests/test_approval.py
git commit -m "feat(governance): add ApprovalPolicy and AutoApprove/AutoDeny/ThresholdApprove"
```

---

