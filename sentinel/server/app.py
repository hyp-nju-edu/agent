from __future__ import annotations
import asyncio
import os
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from sentinel.core.types import RunContext, Approval, ApprovalDecision, ToolResult, RiskLevel
from sentinel.core.llm import LLMProvider, MockLLM, LLMResponse
from sentinel.core.tools import Tool, ToolRegistry
from sentinel.core.guardrails import (
    GuardrailPipeline, PatternGuardrail, ScopeFenceGuardrail,
    SandboxBoundaryGuardrail, RiskClassifierGuardrail,
)
from sentinel.core.approval import ApprovalPolicy, AutoApprove, HumanApprove
from sentinel.core.sandbox import InProcessSandbox
from sentinel.core.audit import AuditLog
from sentinel.core.hitl import HITLStateMachine
from sentinel.core.loop import agent_loop
from sentinel.core.config import Config
from sentinel.core.providers import OpenAIProvider, AnthropicProvider
from sentinel.credentials import CredentialStore


class WebSocketApprovalResolver:
    """Bridges WebSocket approval replies to the HumanApprove policy.

    resolve() creates a future keyed by action_id and awaits it.
    submit() resolves that future when the browser replies.
    Designed for a concurrent loop+receiver architecture.
    """

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future[Approval]] = {}

    async def resolve(self, action, result) -> Approval:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[Approval] = loop.create_future()
        self._pending[action.id] = fut
        return await fut

    def submit(self, action_id: str, decision: str, reason: str = "") -> None:
        fut = self._pending.pop(action_id, None)
        if fut is not None and not fut.done():
            if decision == "approved":
                fut.set_result(Approval(ApprovalDecision.APPROVED,
                                        reason or "user approved"))
            else:
                fut.set_result(Approval(ApprovalDecision.DENIED,
                                        reason or "user denied"))


def _build_pipeline(workspace: str = ".") -> GuardrailPipeline:
    return GuardrailPipeline([
        PatternGuardrail(),
        ScopeFenceGuardrail(workspace=workspace),
        SandboxBoundaryGuardrail(),
        RiskClassifierGuardrail(),
    ])


MODEL_REGISTRY: dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"],
    "anthropic": ["claude-sonnet-4", "claude-opus-4",
                  "claude-3-7-sonnet", "claude-3-5-haiku"],
}


def build_llm(
    config: Config,
    credential_store: CredentialStore | None = None,
    env: dict[str, str] | None = None,
) -> LLMProvider:
    """Build a real LLM provider from config + credentials (keyring or env)."""
    cs = credential_store or CredentialStore()
    env = env if env is not None else dict(os.environ)
    key = cs.get_key(config.provider)
    if not key:
        env_key = env.get(f"{config.provider.upper()}_API_KEY", "")
        key = env_key or None
    if not key:
        raise RuntimeError(f"no api key for provider '{config.provider}'")
    if config.provider == "openai":
        return OpenAIProvider(api_key=key, model=config.model)
    if config.provider == "anthropic":
        return AnthropicProvider(api_key=key, model=config.model)
    raise ValueError(f"unknown provider: {config.provider}")


class _StubTool:
    """Default tool for demo mode — returns canned result, no real execution."""
    name = "run_shell"
    risk_level = RiskLevel.HIGH

    async def execute(self, args: dict, sandbox: Any) -> ToolResult:
        return ToolResult(success=True, stdout="3 passed")


def create_app(
    workspace: str = ".",
    llm: LLMProvider | None = None,
    tools: list[Tool] | None = None,
    pipeline: GuardrailPipeline | None = None,
    use_human_approval: bool = False,
    approval_timeout: float = 30.0,
    llm_builder: Callable[[str, str], LLMProvider] | None = None,
    default_provider: str = "openai",
    default_model: str = "gpt-4o-mini",
) -> FastAPI:
    app = FastAPI(title="Sentinel")
    audit = AuditLog()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/models")
    async def get_models():
        return {
            "providers": MODEL_REGISTRY,
            "default": {"provider": default_provider, "model": default_model},
        }

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
            msg = await ws.receive_json()
            if msg.get("type") == "task":
                await _run_session(
                    ws, msg.get("task", ""), workspace, llm, tools,
                    pipeline, use_human_approval, approval_timeout, audit,
                    llm_builder,
                    msg.get("provider"), msg.get("model"),
                )
        except WebSocketDisconnect:
            pass

    async def _run_session(
        ws: WebSocket,
        task: str,
        workspace: str,
        llm: LLMProvider | None,
        tools: list[Tool] | None,
        pipeline: GuardrailPipeline | None,
        use_human_approval: bool,
        approval_timeout: float,
        audit: AuditLog,
        llm_builder: Callable[[str, str], LLMProvider] | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        active_llm = llm or MockLLM(responses=[
            LLMResponse(text="",
                tool_calls=[{"tool": "run_shell",
                             "args": {"cmd": "pytest"}}]),
            LLMResponse(text="done", tool_calls=[]),
        ])
        if llm_builder is not None and provider and model:
            try:
                active_llm = llm_builder(provider, model)
            except Exception as e:
                await ws.send_json({"type": "Error",
                                    "data": {"message": str(e)}})
                await ws.send_json({"type": "SessionComplete"})
                return
        active_tools = ToolRegistry(tools if tools else [_StubTool()])
        active_pipe = pipeline or _build_pipeline(workspace)

        if use_human_approval:
            async def resolver(action, result):
                reply = await ws.receive_json()
                if reply.get("decision") == "approved":
                    return Approval(ApprovalDecision.APPROVED,
                                    "user approved")
                return Approval(ApprovalDecision.DENIED, "user denied")
            approval_policy: ApprovalPolicy = HumanApprove(
                resolver, timeout=approval_timeout)
        else:
            approval_policy = AutoApprove()

        async for event in agent_loop(
            RunContext(task=task), active_llm, active_tools,
            active_pipe, approval_policy,
            InProcessSandbox(workspace=workspace),
            audit, HITLStateMachine(), max_turns=10,
        ):
            await ws.send_json({
                "type": event.type,
                "data": event.data,
            })
        await ws.send_json({"type": "SessionComplete"})

    return app
