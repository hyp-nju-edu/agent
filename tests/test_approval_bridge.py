import asyncio
import pytest
from fastapi.testclient import TestClient

from sentinel.core.types import (
    Action, ApprovalDecision, Decision, GuardrailResult, RiskLevel, ToolResult,
)
from sentinel.core.llm import MockLLM, LLMResponse
from sentinel.core.guardrails import GuardrailPipeline, SandboxBoundaryGuardrail
from sentinel.core.approval import AutoApprove
from sentinel.server.app import create_app, WebSocketApprovalResolver


class StubTool:
    name = "run_shell"
    risk_level = RiskLevel.HIGH

    async def execute(self, args, sandbox):
        return ToolResult(success=True, stdout="ok")


@pytest.mark.asyncio
async def test_resolver_resolves_approved():
    resolver = WebSocketApprovalResolver()
    action = Action("run_shell", {"cmd": "x"}, id="a1")
    result = GuardrailResult(Decision.REQUIRE_APPROVAL, "x", RiskLevel.HIGH, "g")

    task = asyncio.create_task(resolver.resolve(action, result))
    await asyncio.sleep(0.01)
    resolver.submit("a1", "approved")
    approval = await task
    assert approval.decision == ApprovalDecision.APPROVED


@pytest.mark.asyncio
async def test_resolver_resolves_denied():
    resolver = WebSocketApprovalResolver()
    action = Action("run_shell", {"cmd": "x"}, id="a2")
    result = GuardrailResult(Decision.REQUIRE_APPROVAL, "x", RiskLevel.HIGH, "g")

    task = asyncio.create_task(resolver.resolve(action, result))
    await asyncio.sleep(0.01)
    resolver.submit("a2", "denied")
    approval = await task
    assert approval.decision == ApprovalDecision.DENIED


@pytest.mark.asyncio
async def test_resolver_submit_unknown_id_ignored():
    resolver = WebSocketApprovalResolver()
    resolver.submit("nonexistent", "approved")


def test_websocket_human_approval_flow():
    llm = MockLLM(responses=[
        LLMResponse(text="",
            tool_calls=[{"tool": "run_shell",
                         "args": {"cmd": "pip install requests"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = [StubTool()]
    pipe = GuardrailPipeline([SandboxBoundaryGuardrail()])

    client = TestClient(create_app(
        workspace=".",
        llm=llm,
        tools=tools,
        pipeline=pipe,
        use_human_approval=True,
        approval_timeout=10,
    ))

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "install requests"})
        events = []
        for _ in range(30):
            msg = ws.receive_json()
            events.append(msg)
            if msg["type"] == "ApprovalNeeded":
                ws.send_json({"type": "approval",
                              "action_id": msg["data"]["action_id"],
                              "decision": "approved"})
            if msg["type"] == "Stopped":
                break

    types = [e["type"] for e in events]
    assert "ApprovalNeeded" in types
    assert "ActionExecuted" in types
    assert "Stopped" in types


def test_websocket_human_approval_denied():
    llm = MockLLM(responses=[
        LLMResponse(text="",
            tool_calls=[{"tool": "run_shell",
                         "args": {"cmd": "pip install requests"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = [StubTool()]
    pipe = GuardrailPipeline([SandboxBoundaryGuardrail()])

    client = TestClient(create_app(
        workspace=".",
        llm=llm,
        tools=tools,
        pipeline=pipe,
        use_human_approval=True,
        approval_timeout=10,
    ))

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "install requests"})
        events = []
        for _ in range(30):
            msg = ws.receive_json()
            events.append(msg)
            if msg["type"] == "ApprovalNeeded":
                ws.send_json({"type": "approval",
                              "action_id": msg["data"]["action_id"],
                              "decision": "denied"})
            if msg["type"] == "Stopped":
                break

    types = [e["type"] for e in events]
    assert "ApprovalNeeded" in types
    assert "ActionDenied" in types
    assert "Stopped" in types
    assert "ActionExecuted" not in types
