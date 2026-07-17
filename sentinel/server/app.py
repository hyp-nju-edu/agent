from __future__ import annotations
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from sentinel.core.types import RunContext, RiskLevel, ToolResult
from sentinel.core.llm import MockLLM, LLMResponse
from sentinel.core.tools import ToolRegistry
from sentinel.core.guardrails import (
    GuardrailPipeline, PatternGuardrail, ScopeFenceGuardrail,
    SandboxBoundaryGuardrail, RiskClassifierGuardrail,
)
from sentinel.core.approval import AutoApprove
from sentinel.core.sandbox import InProcessSandbox
from sentinel.core.audit import AuditLog
from sentinel.core.hitl import HITLStateMachine
from sentinel.core.loop import agent_loop


class _StubTool:
    name = "run_shell"
    risk_level = RiskLevel.HIGH

    async def execute(self, args: dict, sandbox: Any) -> ToolResult:
        return ToolResult(success=True, stdout="3 passed")


def _build_pipeline(workspace: str = ".") -> GuardrailPipeline:
    return GuardrailPipeline([
        PatternGuardrail(),
        ScopeFenceGuardrail(workspace=workspace),
        SandboxBoundaryGuardrail(),
        RiskClassifierGuardrail(),
    ])


def create_app(workspace: str = ".") -> FastAPI:
    app = FastAPI(title="Sentinel")
    audit = AuditLog()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/audit")
    async def get_audit():
        return [{"action_id": e.action_id, "guardrail": e.guardrail,
                 "decision": e.decision.value,
                 "risk_level": e.risk_level.value,
                 "outcome": e.outcome, "reason": e.reason}
                for e in audit.all()]

    @app.get("/")
    async def index():
        static = Path(__file__).parent / "static" / "index.html"
        if static.exists():
            return HTMLResponse(static.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>Sentinel</h1>")

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                msg = await ws.receive_json()
                if msg.get("type") == "task":
                    task = msg.get("task", "")
                    llm = MockLLM(responses=[
                        LLMResponse(text="",
                            tool_calls=[{"tool": "run_shell",
                                         "args": {"cmd": "pytest"}}]),
                        LLMResponse(text="done", tool_calls=[]),
                    ])
                    tools = ToolRegistry([_StubTool()])
                    async for event in agent_loop(
                        RunContext(task=task), llm, tools,
                        _build_pipeline(workspace), AutoApprove(),
                        InProcessSandbox(workspace=workspace),
                        audit, HITLStateMachine(), max_turns=5,
                    ):
                        await ws.send_json({
                            "type": event.type,
                            "data": event.data,
                        })
                    await ws.send_json({"type": "SessionComplete"})
        except WebSocketDisconnect:
            pass

    return app
