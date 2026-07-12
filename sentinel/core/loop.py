from __future__ import annotations
from typing import Any, AsyncIterator

from sentinel.core.types import (
    Action, ApprovalDecision, Decision, Event, RunContext, ToolResult,
)
from sentinel.core.llm import LLMProvider
from sentinel.core.tools import ToolRegistry
from sentinel.core.guardrails import GuardrailPipeline
from sentinel.core.approval import ApprovalPolicy
from sentinel.core.sandbox import InProcessSandbox
from sentinel.core.audit import AuditEntry, AuditLog
from sentinel.core.hitl import HITLStateMachine
from sentinel.core.feedback import select_validator


async def agent_loop(
    ctx: RunContext,
    llm: LLMProvider,
    tools: ToolRegistry,
    pipeline: GuardrailPipeline,
    approval_policy: ApprovalPolicy,
    sandbox: InProcessSandbox,
    audit: AuditLog,
    hitl: HITLStateMachine,
    max_turns: int = 10,
) -> AsyncIterator[Event]:
    messages = [{"role": "system", "content": f"Task: {ctx.task}"}]
    for turn in range(max_turns):
        yield Event(type="TurnStarted", data={"turn": turn})
        resp = await llm.complete(messages=messages, tools=tools.names())
        yield Event(type="LLMResponse", data={"text": resp.text})
        if not resp.tool_calls:
            yield Event(type="Stopped", data={"reason": "done"})
            return
        for call in resp.tool_calls:
            action = Action(tool=call["tool"], args=call.get("args", {}),
                             raw_source=str(call), turn_id=str(turn))
            yield Event(type="ActionRequested",
                        data={"tool": action.tool, "args": action.args})
            result = pipeline.check(action, ctx)
            audit.append(AuditEntry(
                action_id=action.id, guardrail=result.guardrail_name,
                decision=result.decision, risk_level=result.risk_level,
                reason=result.reason,
            ))
            if result.decision == Decision.DENY:
                yield Event(type="ActionDenied",
                            data={"action_id": action.id, "reason": result.reason})
                continue
            if result.decision == Decision.REQUIRE_APPROVAL:
                hitl.submit(action)
                approval = await approval_policy.approve(action, result)
                if approval.decision == ApprovalDecision.DENIED:
                    hitl.deny(action.id)
                    audit.append(AuditEntry(
                        action_id=action.id, guardrail="approval",
                        decision=Decision.DENY, risk_level=result.risk_level,
                        outcome="skipped", reason=approval.reason))
                    yield Event(type="ActionDenied",
                                data={"action_id": action.id, "reason": approval.reason})
                    continue
                hitl.approve(action.id)
            tool = tools.get(action.tool)
            tool_result = await tool.execute(action.args, sandbox)
            if action.id in hitl._states:
                hitl.mark_executed(action.id, success=tool_result.success)
            yield Event(type="ActionExecuted",
                        data={"action_id": action.id, "success": tool_result.success})
            validator = select_validator(action)
            feedback = validator.parse(tool_result, action)
            yield Event(type="FeedbackReceived",
                        data={"passed": feedback.passed,
                              "failures": [f.kind.value for f in feedback.failures]})
            messages.append({"role": "tool", "content": tool_result.stdout})
        yield Event(type="TurnComplete", data={"turn": turn})
    yield Event(type="Stopped", data={"reason": "max_turns"})
