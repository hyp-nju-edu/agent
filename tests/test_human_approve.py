import asyncio
import pytest
from sentinel.core.types import Action, Approval, Decision, GuardrailResult, RiskLevel, ApprovalDecision
from sentinel.core.approval import HumanApprove


def _r():
    return GuardrailResult(decision=Decision.REQUIRE_APPROVAL, reason="x",
                           risk_level=RiskLevel.HIGH, guardrail_name="g")


@pytest.mark.asyncio
async def test_human_approve_resolves_approved():
    async def resolver(action, result):
        return Approval(ApprovalDecision.APPROVED, "user said yes")
    h = HumanApprove(resolver, timeout=5)
    a = await h.approve(Action("run_shell", {"cmd": "x"}), _r())
    assert a.decision == ApprovalDecision.APPROVED
    assert a.reason == "user said yes"


@pytest.mark.asyncio
async def test_human_approve_resolves_denied():
    async def resolver(action, result):
        return Approval(ApprovalDecision.DENIED, "user said no")
    h = HumanApprove(resolver, timeout=5)
    a = await h.approve(Action("run_shell", {"cmd": "x"}), _r())
    assert a.decision == ApprovalDecision.DENIED


@pytest.mark.asyncio
async def test_human_approve_timeout_denies_fail_closed():
    async def resolver(action, result):
        await asyncio.sleep(10)
    h = HumanApprove(resolver, timeout=0.05)
    a = await h.approve(Action("run_shell", {"cmd": "x"}), _r())
    assert a.decision == ApprovalDecision.DENIED
    assert "timeout" in a.reason.lower()


@pytest.mark.asyncio
async def test_human_approve_resolver_error_denies():
    async def resolver(action, result):
        raise RuntimeError("ws disconnected")
    h = HumanApprove(resolver, timeout=5)
    a = await h.approve(Action("run_shell", {"cmd": "x"}), _r())
    assert a.decision == ApprovalDecision.DENIED
    assert "error" in a.reason.lower() or "resolver" in a.reason.lower()
