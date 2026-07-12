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
