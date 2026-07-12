import pytest
from sentinel.core.types import Action, Decision, RiskLevel, RunContext, ToolResult
from sentinel.core.llm import MockLLM, LLMResponse
from sentinel.core.tools import ToolRegistry
from sentinel.core.guardrails import (
    GuardrailPipeline, PatternGuardrail, ScopeFenceGuardrail,
    SandboxBoundaryGuardrail, RiskClassifierGuardrail,
)
from sentinel.core.approval import AutoApprove, AutoDeny, ThresholdApprove
from sentinel.core.sandbox import InProcessSandbox
from sentinel.core.audit import AuditLog
from sentinel.core.hitl import HITLStateMachine, ActionState
from sentinel.core.feedback import PytestValidator
from sentinel.core.loop import agent_loop


class StubShell:
    name = "run_shell"
    risk_level = RiskLevel.HIGH
    def __init__(self, stdout="", success=True):
        self._stdout = stdout
        self._success = success
    async def execute(self, args, sandbox):
        return ToolResult(success=self._success, stdout=self._stdout)


def _pipeline(workspace="."):
    return GuardrailPipeline([
        PatternGuardrail(),
        ScopeFenceGuardrail(workspace=workspace),
        SandboxBoundaryGuardrail(),
        RiskClassifierGuardrail(),
    ])


# ① Governance intercept
@pytest.mark.asyncio
async def test_demo_governance_intercept():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "rm -rf /"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    events = []
    async for e in agent_loop(RunContext(task="demo"), llm, ToolRegistry([StubShell()]),
                               _pipeline(), AutoApprove(), InProcessSandbox(workspace="."),
                               AuditLog(), HITLStateMachine(), max_turns=3):
        events.append(e)
    assert any(e.type == "ActionDenied" for e in events)
    assert not any(e.type == "ActionExecuted" for e in events)


# ② Feedback self-correction
@pytest.mark.asyncio
async def test_demo_feedback_self_correction():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "pytest"}}]),
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "cat tests/test_foo.py"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    # first call fails, second succeeds
    tool = StubShell(stdout="FAILED tests/test_foo.py::test_a - assert 1 == 2", success=False)
    tool2 = StubShell(stdout="file contents", success=True)
    class SwitchingRegistry:
        def __init__(self):
            self.calls = 0
        def get(self, name):
            self.calls += 1
            return tool if self.calls == 1 else tool2
        def names(self):
            return ["run_shell"]
    events = []
    async for e in agent_loop(RunContext(task="demo"), llm, SwitchingRegistry(),
                               _pipeline(), AutoApprove(), InProcessSandbox(workspace="."),
                               AuditLog(), HITLStateMachine(), max_turns=5):
        events.append(e)
    feedbacks = [e for e in events if e.type == "FeedbackReceived"]
    assert feedbacks and feedbacks[0].data["passed"] is False
    assert any("assertion_failure" in f for f in feedbacks[0].data["failures"])
    # agent took a different next action (cat the test file)
    requested = [e for e in events if e.type == "ActionRequested"]
    assert any("cat" in e.data.get("args", {}).get("cmd", "") for e in requested)


# ③ HITL depth
@pytest.mark.asyncio
async def test_demo_hitl_depth():
    # high-risk network action → ThresholdApprove denies (deterministic)
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "pip install requests"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    events = []
    async for e in agent_loop(RunContext(task="demo"), llm, ToolRegistry([StubShell()]),
                               _pipeline(), ThresholdApprove(), InProcessSandbox(workspace="."),
                               AuditLog(), HITLStateMachine(), max_turns=3):
        events.append(e)
    assert any(e.type == "ApprovalNeeded" for e in events)
    assert any(e.type == "ActionDenied" for e in events)
    assert not any(e.type == "ActionExecuted" for e in events)
