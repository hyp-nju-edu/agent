from __future__ import annotations
import asyncio
from typing import Awaitable, Callable, Protocol, runtime_checkable

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


class HumanApprove:
    """Production approval policy: awaits an async resolver, fail-closed on timeout/error."""

    def __init__(self, resolver: Callable[[Action, GuardrailResult],
                                         Awaitable[Approval]],
                 timeout: float = 30.0) -> None:
        self._resolver = resolver
        self._timeout = timeout

    async def approve(self, action: Action, result: GuardrailResult) -> Approval:
        try:
            return await asyncio.wait_for(
                self._resolver(action, result), timeout=self._timeout)
        except asyncio.TimeoutError:
            return Approval(ApprovalDecision.DENIED, "approval timeout")
        except Exception as e:
            return Approval(ApprovalDecision.DENIED, f"resolver error: {e}")
