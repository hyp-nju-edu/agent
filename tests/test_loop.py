import pytest
from sentinel.core.types import (
    Action, Decision, RiskLevel, RunContext, ToolResult, Event,
)
from sentinel.core.llm import MockLLM, LLMResponse
from sentinel.core.tools import ToolRegistry
from sentinel.core.guardrails import (
    GuardrailPipeline, PatternGuardrail, SandboxBoundaryGuardrail,
)
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


class RaisingTool:
    name = "run_shell"
    risk_level = RiskLevel.HIGH
    async def execute(self, args, sandbox):
        raise RuntimeError("tool blew up")

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

@pytest.mark.asyncio
async def test_loop_denies_when_approval_rejected():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "pip install x"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = ToolRegistry([StubTool()])
    pipe = GuardrailPipeline([SandboxBoundaryGuardrail()])  # pip install -> REQUIRE_APPROVAL
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoDeny(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=5):
        events.append(e)
    assert any(e.type == "ApprovalNeeded" for e in events)   # also verifies Finding 1
    assert any(e.type == "ActionDenied" for e in events)
    assert not any(e.type == "ActionExecuted" for e in events)


@pytest.mark.asyncio
async def test_loop_approve_then_execute_path_end_to_end():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "pip install requests"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = ToolRegistry([StubTool(stdout="installed")])
    pipe = GuardrailPipeline([SandboxBoundaryGuardrail()])  # pip install -> REQUIRE_APPROVAL
    hitl = HITLStateMachine()
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), hitl, max_turns=5):
        events.append(e)
    # capture action_id from ApprovalNeeded (or ActionRequested)
    approval_events = [e for e in events if e.type == "ApprovalNeeded"]
    assert approval_events, "expected an ApprovalNeeded event"
    action_id = approval_events[0].data["action_id"]
    assert any(e.type == "ActionExecuted" for e in events)
    assert hitl.state(action_id) == ActionState.EXECUTED


@pytest.mark.asyncio
async def test_loop_tool_exception_yields_failed_execution_and_continues():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "pytest"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = ToolRegistry([RaisingTool()])
    pipe = GuardrailPipeline([PatternGuardrail()])
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=5):
        events.append(e)
    types = [e.type for e in events]
    executed = [e for e in events if e.type == "ActionExecuted"]
    assert executed, "expected an ActionExecuted event"
    assert executed[0].data["success"] is False
    # loop must not stop on the tool error (no Stopped with reason=error)
    stopped = [e for e in events if e.type == "Stopped"]
    assert not stopped or stopped[-1].data.get("reason") != "error"
