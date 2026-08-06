## Task 13: Agent Main Loop

**Files:**
- Create: `sentinel/core/loop.py`
- Test: `tests/test_loop.py`

**Interfaces:**
- Consumes: `LLMProvider`, `ToolRegistry`, `GuardrailPipeline`, `ApprovalPolicy`, `RunContext`, `Event`, `Action`, `ToolResult`, `Feedback`, `HITLStateMachine`, `AuditLog`, `select_validator`.
- Produces: `async def agent_loop(ctx, llm, tools, pipeline, approval_policy, sandbox, audit, hitl, max_turns) -> AsyncIterator[Event]`.

- [ ] **Step 1: Write the failing test**

`tests/test_loop.py`:
```python
import pytest
from sentinel.core.types import (
    Action, Decision, RiskLevel, RunContext, ToolResult, Event,
)
from sentinel.core.llm import MockLLM, LLMResponse
from sentinel.core.tools import ToolRegistry
from sentinel.core.guardrails import GuardrailPipeline, PatternGuardrail
from sentinel.core.approval import AutoApprove, AutoDeny
from sentinel.core.sandbox import InProcessSandbox
from sentinel.core.audit import AuditLog
from sentinel.core.hitl import HITLStateMachine, ActionState
from sentinel.core.loop import agent_loop

class StubTool:
    name = "run_shell"
    risk_level = RiskLevel.HIGH
    def __init__(self, stdout="ok", success=True):
        self._stdout = stdout
        self._success = success
    async def execute(self, args, sandbox):
        return ToolResult(success=self._success, stdout=self._stdout)

def _events(gen):
    import asyncio
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())

@pytest.mark.asyncio
async def test_loop_runs_safe_action_and_stops():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "pytest"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = ToolRegistry([StubTool(stdout="3 passed")])
    pipe = GuardrailPipeline([PatternGuardrail()])
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=5):
        events.append(e)
    types = [e.type for e in events]
    assert "ActionRequested" in types
    assert "ActionExecuted" in types
    assert "Stopped" in types

@pytest.mark.asyncio
async def test_loop_denies_dangerous_action():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "rm -rf /"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = ToolRegistry([StubTool()])
    pipe = GuardrailPipeline([PatternGuardrail()])
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=5):
        events.append(e)
    assert any(e.type == "ActionDenied" for e in events)
    assert any(e.type == "Stopped" for e in events)

@pytest.mark.asyncio
async def test_loop_stops_on_max_turns():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "ls"}}]),
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "ls"}}]),
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "ls"}}]),
    ])
    tools = ToolRegistry([StubTool()])
    pipe = GuardrailPipeline([PatternGuardrail()])
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=2):
        events.append(e)
    assert events[-1].type == "Stopped"
    assert "max_turns" in events[-1].data.get("reason", "")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_loop.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`sentinel/core/loop.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_loop.py -v
```
Expected: PASS (3 tests). The `mark_executed` call is guarded by `action.id in hitl._states` so ALLOW-path actions (never submitted to the HITL machine) are not tracked — only `REQUIRE_APPROVAL` actions walk the state machine.

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/loop.py tests/test_loop.py
git commit -m "feat(core): add async agent_loop with governance + feedback integration"
```

---

