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

@pytest.mark.asyncio
async def test_threshold_denies_critical():
    a = await ThresholdApprove().approve(Action("x", {}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.CRITICAL))
    assert a.decision.value == "denied"

@pytest.mark.asyncio
async def test_threshold_high_still_denies_critical():
    a = await ThresholdApprove(threshold=RiskLevel.HIGH).approve(Action("x", {}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.CRITICAL))
    assert a.decision.value == "denied"

def test_approval_policy_is_protocol():
    assert hasattr(ApprovalPolicy, "approve")
    assert isinstance(AutoApprove(), ApprovalPolicy)
