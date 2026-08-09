# Sentinel Implementation Plan — Phase 2: Real LLM, WebUI, Credentials, Distribution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take Sentinel from a mock-LLM testable core to a working product: real LLM providers (OpenAI + Anthropic via httpx), HumanApprove policy with timeout, credential CLI (keyring), FastAPI WebSocket server, minimal frontend, Dockerfile, CI, and README.

**Architecture:** Phase 1's injectable collaborators (LLMProvider, ApprovalPolicy) are the seams. Real providers implement the same `LLMProvider` protocol via raw httpx calls (no heavy SDK). `HumanApprove` implements the same `ApprovalPolicy` protocol with an async resolver + timeout. The FastAPI server consumes the same `agent_loop` async generator and streams `Event`s over WebSocket. All new code is testable offline (httpx MockTransport, fake resolvers, in-memory credential backends, FastAPI TestClient).

**Tech Stack:** Python 3.11+, httpx (raw HTTP to LLM APIs), fastapi + uvicorn (server), keyring (credentials), pytest + pytest-asyncio (tests). No openai/anthropic SDK — raw httpx only.

## Global Constraints

- Python 3.11+ required.
- No agent orchestration frameworks. No openai/anthropic SDK — use httpx directly.
- All new code must be testable offline: no real network, no real LLM, no real keyring backend in tests.
- Keys never hardcoded, never logged, never in git. Pre-commit scan for `sk-` patterns.
- TDD enforced: red → green → refactor. Commit after every green test.
- Conventional Commits (`feat:`, `test:`, `chore:`, `docs:`).
- Existing 97 Phase 1 tests must keep passing after every task.

## File Structure

```
sentinel/
  core/
    providers.py     # OpenAIProvider, AnthropicProvider (httpx-based)
    approval.py      # + HumanApprove (modified)
    loop.py          # productionized (modified)
    ...              # (unchanged Phase 1 modules)
  credentials.py     # CredentialStore (keyring-backed, injectable backend)
  cli.py             # argparse CLI: config set-key/status/clear-key, serve
  server/
    __init__.py
    app.py           # FastAPI app, WebSocket endpoint, REST endpoints
    static/
      index.html     # minimal frontend (linear-app styled)
tests/
  test_providers.py
  test_human_approve.py
  test_credentials.py
  test_cli.py
  test_server.py
Dockerfile
.gitlab-ci.yml
.github/workflows/ci.yml
README.md
```

---

## Task 1: Add Phase 2 Dependencies
> **Status:** ✅ complete — commits: 006cc6b

**Files:**
- Modify: `pyproject.toml`

**Interfaces:** Produces installable optional dependency groups `server`, `credentials`, `all`.

- [x] **Step 1: Update `pyproject.toml`**

Replace the `[project]` and `[project.optional-dependencies]` sections:

```toml
[project]
name = "sentinel-harness"
version = "0.2.0"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0", "httpx>=0.27"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
server = ["fastapi>=0.110", "uvicorn>=0.29"]
credentials = ["keyring>=24.0"]
all = ["fastapi>=0.110", "uvicorn>=0.29", "keyring>=24.0"]

[project.scripts]
sentinel = "sentinel.cli:main"
```

- [x] **Step 2: Install new deps**

Run:
```bash
python -m pip install -e ".[dev,all]"
```
Expected: fastapi, uvicorn, keyring installed successfully.

- [x] **Step 3: Verify existing tests still pass**

Run: `python -m pytest -q`
Expected: 97 passed.

- [x] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add Phase 2 deps (httpx, fastapi, uvicorn, keyring)"
```

---

## Task 2: Real LLM Providers (OpenAI + Anthropic via httpx)
> **Status:** ✅ complete — commits: ac5e909

**Files:**
- Create: `sentinel/core/providers.py`
- Test: `tests/test_providers.py`

**Interfaces:**
- Consumes: `LLMProvider` protocol, `LLMResponse` from `llm.py`.
- Produces: `OpenAIProvider(api_key, model, client=None)`, `AnthropicProvider(api_key, model, client=None)`. Both implement `async complete(messages, tools) -> LLMResponse`. The `client` param accepts an `httpx.AsyncClient` (for testing with `httpx.MockTransport`).

- [x] **Step 1: Write the failing test**

`tests/test_providers.py`:
```python
import json
import pytest
import httpx
from sentinel.core.providers import OpenAIProvider, AnthropicProvider


def _openai_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["model"] == "gpt-4o-mini"
    assert request.headers["authorization"] == "Bearer sk-test"
    return httpx.Response(200, json={
        "choices": [{
            "message": {
                "content": "I will run pytest",
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "run_shell",
                                  "arguments": "{\"cmd\": \"pytest\"}"},
                }],
            }
        }]
    })


def _openai_text_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"message": {"content": "done", "tool_calls": []}}]
    })


@pytest.mark.asyncio
async def test_openai_provider_parses_text_and_tool_calls():
    transport = httpx.MockTransport(_openai_handler)
    client = httpx.AsyncClient(transport=transport)
    p = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
    resp = await p.complete(
        messages=[{"role": "user", "content": "go"}], tools=["run_shell"])
    assert resp.text == "I will run pytest"
    assert resp.tool_calls == [{"tool": "run_shell", "args": {"cmd": "pytest"}}]
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_provider_text_only():
    transport = httpx.MockTransport(_openai_text_handler)
    client = httpx.AsyncClient(transport=transport)
    p = OpenAIProvider(api_key="sk-test", model="gpt-4o-mini", client=client)
    resp = await p.complete(messages=[], tools=[])
    assert resp.text == "done"
    assert resp.tool_calls == []
    await client.aclose()


@pytest.mark.asyncio
async def test_openai_provider_raises_on_http_error():
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "bad key"}})
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    p = OpenAIProvider(api_key="sk-bad", model="gpt-4o-mini", client=client)
    with pytest.raises(RuntimeError, match="openai api error"):
        await p.complete(messages=[], tools=[])
    await client.aclose()


def _anthropic_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["model"] == "claude-sonnet-4-20250514"
    assert request.headers["x-api-key"] == "sk-ant-test"
    return httpx.Response(200, json={
        "content": [
            {"type": "text", "text": "running tests"},
            {"type": "tool_use", "id": "tu_1",
             "name": "run_shell", "input": {"cmd": "pytest"}},
        ]
    })


@pytest.mark.asyncio
async def test_anthropic_provider_parses_text_and_tool_use():
    transport = httpx.MockTransport(_anthropic_handler)
    client = httpx.AsyncClient(transport=transport)
    p = AnthropicProvider(api_key="sk-ant-test",
                          model="claude-sonnet-4-20250514", client=client)
    resp = await p.complete(
        messages=[{"role": "user", "content": "go"}], tools=["run_shell"])
    assert resp.text == "running tests"
    assert resp.tool_calls == [{"tool": "run_shell", "args": {"cmd": "pytest"}}]
    await client.aclose()


@pytest.mark.asyncio
async def test_anthropic_provider_text_only():
    def handler(request):
        return httpx.Response(200, json={
            "content": [{"type": "text", "text": "all done"}]
        })
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    p = AnthropicProvider(api_key="sk-ant-test",
                          model="claude-sonnet-4-20250514", client=client)
    resp = await p.complete(messages=[], tools=[])
    assert resp.text == "all done"
    assert resp.tool_calls == []
    await client.aclose()
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_providers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'sentinel.core.providers'`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/providers.py`:
```python
from __future__ import annotations
import json
from typing import Any

import httpx

from sentinel.core.llm import LLMProvider, LLMResponse


class OpenAIProvider:
    """LLM provider using raw httpx calls to the OpenAI chat completions API."""

    def __init__(self, api_key: str, model: str,
                 client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(
            base_url="https://api.openai.com", timeout=60.0)

    async def complete(self, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]]) -> LLMResponse:
        resp = await self._client.post(
            "/v1/chat/completions",
            json={"model": self._model, "messages": messages},
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"openai api error {resp.status_code}: {resp.text}")
        data = resp.json()
        msg = data["choices"][0]["message"]
        text = msg.get("content") or ""
        tool_calls: list[dict[str, Any]] = []
        for tc in msg.get("tool_calls") or []:
            fn = tc["function"]
            tool_calls.append({
                "tool": fn["name"],
                "args": json.loads(fn["arguments"]),
            })
        return LLMResponse(text=text, tool_calls=tool_calls)


class AnthropicProvider:
    """LLM provider using raw httpx calls to the Anthropic messages API."""

    def __init__(self, api_key: str, model: str,
                 client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(
            base_url="https://api.anthropic.com", timeout=60.0)

    async def complete(self, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]]) -> LLMResponse:
        resp = await self._client.post(
            "/v1/messages",
            json={"model": self._model, "messages": messages,
                  "max_tokens": 4096},
            headers={"x-api-key": self._api_key,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"anthropic api error {resp.status_code}: {resp.text}")
        data = resp.json()
        text = ""
        tool_calls: list[dict[str, Any]] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append({
                    "tool": block["name"],
                    "args": block.get("input", {}),
                })
        return LLMResponse(text=text, tool_calls=tool_calls)
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_providers.py -v`
Expected: PASS (6 tests)

- [x] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: 103 passed (97 + 6)

- [x] **Step 6: Commit**

```bash
git add sentinel/core/providers.py tests/test_providers.py
git commit -m "feat(llm): add OpenAI and Anthropic providers via httpx"
```

---

## Task 3: HumanApprove Policy (async resolver + timeout)
> **Status:** ✅ complete — commits: 4c1b597

**Files:**
- Modify: `sentinel/core/approval.py`
- Test: `tests/test_human_approve.py`

**Interfaces:**
- Consumes: `ApprovalPolicy` protocol, `Action`, `GuardrailResult`, `Approval`, `ApprovalDecision` from `types`.
- Produces: `HumanApprove(resolver, timeout=30)`. `resolver` is `async (action, result) -> Approval`. Timeout → `Approval(DENIED, "approval timeout")` (fail-closed).

- [x] **Step 1: Write the failing test**

`tests/test_human_approve.py`:
```python
import asyncio
import pytest
from sentinel.core.types import Action, Decision, GuardrailResult, RiskLevel
from sentinel.core.approval import HumanApprove
from sentinel.core.types import ApprovalDecision


def _r():
    return GuardrailResult(decision=Decision.REQUIRE_APPROVAL, reason="x",
                           risk_level=RiskLevel.HIGH, guardrail_name="g")


@pytest.mark.asyncio
async def test_human_approve_resolves_approved():
    async def resolver(action, result):
        return ApprovalDecision.APPROVED if True else None
    from sentinel.core.types import Approval
    async def resolver2(action, result):
        return Approval(ApprovalDecision.APPROVED, "user said yes")
    h = HumanApprove(resolver2, timeout=5)
    a = await h.approve(Action("run_shell", {"cmd": "x"}), _r())
    assert a.decision == ApprovalDecision.APPROVED
    assert a.reason == "user said yes"


@pytest.mark.asyncio
async def test_human_approve_resolves_denied():
    from sentinel.core.types import Approval
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_human_approve.py -v`
Expected: FAIL with `ImportError: cannot import name 'HumanApprove'`

- [x] **Step 3: Write minimal implementation (append to `sentinel/core/approval.py`)**

Add at the end of `sentinel/core/approval.py`:
```python
import asyncio
from typing import Awaitable, Callable


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
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_human_approve.py -v`
Expected: PASS (4 tests)

- [x] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: 107 passed (103 + 4)

- [x] **Step 6: Commit**

```bash
git add sentinel/core/approval.py tests/test_human_approve.py
git commit -m "feat(governance): add HumanApprove policy with fail-closed timeout"
```

---

## Task 4: Productionize the Loop (assistant messages + memory)
> **Status:** ✅ complete — commits: 54e0433

**Files:**
- Modify: `sentinel/core/loop.py`
- Test: `tests/test_loop.py` (add cases)

**Interfaces:**
- Consumes: `MemoryStore` from `memory.py`, `Config` from `config.py`.
- Produces: `agent_loop` now appends assistant messages to the conversation, injects memory snippets into the system prompt, and accepts an optional `memory` parameter.

- [x] **Step 1: Write the failing tests (append to `tests/test_loop.py`)**

```python
from sentinel.core.memory import MemoryStore
from sentinel.core.loop import build_system_prompt


def test_build_system_prompt_includes_task_and_memory():
    mem = MemoryStore()
    mem.add("convention", "style", "use 4-space indent")
    prompt = build_system_prompt(task="fix tests", memory=mem)
    assert "fix tests" in prompt
    assert "4-space indent" in prompt


def test_build_system_prompt_no_memory():
    prompt = build_system_prompt(task="do thing", memory=None)
    assert "do thing" in prompt


@pytest.mark.asyncio
async def test_loop_appends_assistant_message():
    llm = MockLLM(responses=[
        LLMResponse(text="thinking about it", tool_calls=[{"tool": "run_shell", "args": {"cmd": "pytest"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = ToolRegistry([StubTool(stdout="3 passed")])
    pipe = GuardrailPipeline([PatternGuardrail()])
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=5):
        events.append(e)
    assert any(e.type == "Stopped" and e.data.get("reason") == "done" for e in events)
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_loop.py::test_build_system_prompt_includes_task_and_memory -v`
Expected: FAIL with `ImportError: cannot import name 'build_system_prompt'`

- [x] **Step 3: Write minimal implementation (modify `sentinel/core/loop.py`)**

Replace the top of `loop.py` (imports + first lines of `agent_loop`) with:

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
from sentinel.core.memory import MemoryStore


def build_system_prompt(task: str, memory: MemoryStore | None = None) -> str:
    parts = [f"Task: {task}"]
    if memory is not None:
        snippets = memory.search(task, limit=3)
        if snippets:
            parts.append("Relevant context:")
            for s in snippets:
                parts.append(f"  - {s}")
    return "\n".join(parts)
```

Then in `agent_loop`, change the signature to accept `memory=None` and use `build_system_prompt`:

```python
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
    memory: MemoryStore | None = None,
) -> AsyncIterator[Event]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": build_system_prompt(ctx.task, memory)}
    ]
```

And after `yield Event(type="LLMResponse", ...)` add:
```python
            if resp.text:
                messages.append({"role": "assistant", "content": resp.text})
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_loop.py -v`
Expected: PASS (all loop tests including new ones)

- [x] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: 110 passed (107 + 3)

- [x] **Step 6: Commit**

```bash
git add sentinel/core/loop.py tests/test_loop.py
git commit -m "feat(core): productionize loop with memory context and assistant messages"
```

---

## Task 5: Credential Store (keyring-backed, injectable)
> **Status:** ✅ complete — commits: 6e4fa55

**Files:**
- Create: `sentinel/credentials.py`
- Test: `tests/test_credentials.py`

**Interfaces:**
- Produces: `CredentialStore(backend=None)` with `set_key(provider, key)`, `get_key(provider) -> str|None`, `clear_key(provider)`, `status() -> dict[str,str]`. Default backend is the `keyring` module; tests inject a fake in-memory backend.

- [x] **Step 1: Write the failing test**

`tests/test_credentials.py`:
```python
from sentinel.credentials import CredentialStore


class FakeKeyring:
    def __init__(self):
        self._store = {}

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


def test_set_and_get_key():
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("openai", "sk-abc123")
    assert cs.get_key("openai") == "sk-abc123"


def test_get_key_missing_returns_none():
    cs = CredentialStore(backend=FakeKeyring())
    assert cs.get_key("openai") is None


def test_clear_key():
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("anthropic", "sk-ant-x")
    cs.clear_key("anthropic")
    assert cs.get_key("anthropic") is None


def test_clear_key_missing_no_error():
    cs = CredentialStore(backend=FakeKeyring())
    cs.clear_key("openai")


def test_status_shows_set_and_not_set():
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("openai", "sk-x")
    s = cs.status()
    assert s["openai"] == "set"
    assert s["anthropic"] == "not set"


def test_status_never_shows_plaintext():
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("openai", "sk-super-secret-12345")
    s = str(cs.status())
    assert "sk-super-secret" not in s
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_credentials.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/credentials.py`:
```python
from __future__ import annotations
from typing import Any, Protocol


class KeyringBackend(Protocol):
    def set_password(self, service: str, username: str, password: str) -> None: ...
    def get_password(self, service: str, username: str) -> str | None: ...
    def delete_password(self, service: str, username: str) -> None: ...


SERVICE_NAME = "sentinel"
PROVIDERS = ["openai", "anthropic"]


class CredentialStore:
    """OS keyring-backed credential store. Keys never logged or echoed."""

    def __init__(self, backend: KeyringBackend | None = None) -> None:
        if backend is not None:
            self._backend = backend
        else:
            import keyring
            self._backend = keyring

    def set_key(self, provider: str, key: str) -> None:
        self._backend.set_password(SERVICE_NAME, provider, key)

    def get_key(self, provider: str) -> str | None:
        return self._backend.get_password(SERVICE_NAME, provider)

    def clear_key(self, provider: str) -> None:
        try:
            self._backend.delete_password(SERVICE_NAME, provider)
        except Exception:
            pass

    def status(self) -> dict[str, str]:
        return {p: ("set" if self.get_key(p) else "not set") for p in PROVIDERS}
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_credentials.py -v`
Expected: PASS (6 tests)

- [x] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: 116 passed (110 + 6)

- [x] **Step 6: Commit**

```bash
git add sentinel/credentials.py tests/test_credentials.py
git commit -m "feat(creds): add keyring-backed CredentialStore with injectable backend"
```

---

## Task 6: CLI (config set-key / status / clear-key, serve)
> **Status:** ✅ complete — commits: e24977d

**Files:**
- Create: `sentinel/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `main(argv=None)` entry point. Subcommands: `config set-key --provider <p>`, `config status`, `config clear-key --provider <p>`, `serve [--host] [--port]`.

- [x] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
import getpass
from sentinel.credentials import CredentialStore


class FakeKeyring:
    def __init__(self):
        self._store = {}

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        self._store.pop((service, username), None)


def test_config_status(monkeypatch, capsys):
    from sentinel.cli import main
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("openai", "sk-x")
    monkeypatch.setattr("sentinel.cli.get_credential_store", lambda: cs)
    main(["config", "status"])
    out = capsys.readouterr().out
    assert "openai: set" in out
    assert "anthropic: not set" in out


def test_config_set_key(monkeypatch, capsys):
    from sentinel.cli import main
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    monkeypatch.setattr("sentinel.cli.get_credential_store", lambda: cs)
    monkeypatch.setattr(getpass, "getpass", lambda prompt="": "sk-secret")
    main(["config", "set-key", "--provider", "openai"])
    assert cs.get_key("openai") == "sk-secret"
    out = capsys.readouterr().out
    assert "sk-secret" not in out


def test_config_clear_key(monkeypatch, capsys):
    from sentinel.cli import main
    kr = FakeKeyring()
    cs = CredentialStore(backend=kr)
    cs.set_key("anthropic", "sk-ant-x")
    monkeypatch.setattr("sentinel.cli.get_credential_store", lambda: cs)
    main(["config", "clear-key", "--provider", "anthropic"])
    assert cs.get_key("anthropic") is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/cli.py`:
```python
from __future__ import annotations
import argparse
import getpass
import sys

from sentinel.credentials import CredentialStore


def get_credential_store() -> CredentialStore:
    return CredentialStore()


def cmd_config(args: argparse.Namespace) -> int:
    cs = get_credential_store()
    if args.config_cmd == "status":
        for provider, state in cs.status().items():
            print(f"{provider}: {state}")
        return 0
    if args.config_cmd == "set-key":
        key = getpass.getpass(prompt=f"Enter API key for {args.provider}: ")
        cs.set_key(args.provider, key)
        print(f"key stored for {args.provider}")
        return 0
    if args.config_cmd == "clear-key":
        cs.clear_key(args.provider)
        print(f"key cleared for {args.provider}")
        return 0
    return 1


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    uvicorn.run("sentinel.server.app:app",
                host=args.host, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sentinel")
    sub = parser.add_subparsers(dest="command", required=True)

    config = sub.add_parser("config")
    config_sub = config.add_subparsers(dest="config_cmd", required=True)

    sk = config_sub.add_parser("set-key")
    sk.add_argument("--provider", required=True,
                    choices=["openai", "anthropic"])

    config_sub.add_parser("status")

    ck = config_sub.add_parser("clear-key")
    ck.add_argument("--provider", required=True,
                    choices=["openai", "anthropic"])

    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "config":
        return cmd_config(args)
    if args.command == "serve":
        return cmd_serve(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (3 tests)

- [x] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: 119 passed (116 + 3)

- [x] **Step 6: Commit**

```bash
git add sentinel/cli.py tests/test_cli.py
git commit -m "feat(cli): add config set-key/status/clear-key and serve commands"
```

---

## Task 7: FastAPI WebSocket Server
> **Status:** ✅ complete — commits: 406c7ab

**Files:**
- Create: `sentinel/server/__init__.py`
- Create: `sentinel/server/app.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `agent_loop`, `MockLLM`, `AutoApprove`, `GuardrailPipeline`, `InProcessSandbox`, `AuditLog`, `HITLStateMachine`, `RunContext`.
- Produces: `create_app()` -> FastAPI app. WebSocket endpoint `GET /ws` accepts `{"type":"task","task":"..."}`, streams `Event`s as JSON lines. REST: `GET /health`, `GET /audit`.

- [x] **Step 1: Write the failing test**

`tests/test_server.py`:
```python
import json
import pytest
from fastapi.testclient import TestClient

from sentinel.server.app import create_app


def test_health():
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_websocket_streams_events():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "run tests"})
        events = []
        for _ in range(20):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "Stopped":
                break
    types = [e["type"] for e in events]
    assert "TurnStarted" in types
    assert "Stopped" in types


def test_websocket_streams_action_executed():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "run tests"})
        events = []
        for _ in range(20):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "Stopped":
                break
    assert any(e["type"] == "ActionExecuted" for e in events)


def test_audit_endpoint():
    client = TestClient(create_app())
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "run tests"})
        for _ in range(20):
            msg = ws.receive_json()
            if msg.get("type") == "Stopped":
                break
    r = client.get("/audit")
    assert r.status_code == 200
    entries = r.json()
    assert isinstance(entries, list)
    assert len(entries) > 0
```

- [x] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/server/__init__.py`:
```python
"""Sentinel WebUI server."""
```

`sentinel/server/app.py`:
```python
from __future__ import annotations
import asyncio
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pathlib import Path

from sentinel.core.types import RunContext
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


class StubTool:
    name = "run_shell"
    risk_level = RiskLevel.HIGH if False else __import__(
        "sentinel.core.types", fromlist=["RiskLevel"]).RiskLevel.HIGH

    async def execute(self, args, sandbox):
        from sentinel.core.types import ToolResult
        return ToolResult(success=True, stdout="3 passed")


def _build_pipeline() -> GuardrailPipeline:
    return GuardrailPipeline([
        PatternGuardrail(),
        ScopeFenceGuardrail(workspace="."),
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
                    tools = ToolRegistry([StubTool()])
                    async for event in agent_loop(
                        RunContext(task=task), llm, tools,
                        _build_pipeline(), AutoApprove(),
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
```

- [x] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_server.py -v`
Expected: PASS (4 tests)

- [x] **Step 5: Run full suite**

Run: `python -m pytest -q`
Expected: 123 passed (119 + 4)

- [x] **Step 6: Commit**

```bash
git add sentinel/server/__init__.py sentinel/server/app.py tests/test_server.py
git commit -m "feat(server): add FastAPI WebSocket server with audit REST endpoint"
```

---

## Task 8: Minimal Frontend (linear-app styled)
> **Status:** ✅ complete — commits: c835e10

**Files:**
- Create: `sentinel/server/static/index.html`

**Interfaces:** Static HTML+CSS+JS. Connects to `/ws`, sends task, renders streaming events, shows audit trail. Dark theme styled after linear-app.

- [x] **Step 1: Create the frontend**

`sentinel/server/static/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sentinel</title>
<style>
  :root { --bg:#08090a; --panel:#131417; --border:#1f2023; --text:#e8e8e8;
          --dim:#8a8f98; --accent:#5e6ad2; --green:#4cb782; --red:#e5484d;
          --yellow:#f5c518; }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:'Inter',system-ui,sans-serif; background:var(--bg);
         color:var(--text); height:100vh; display:flex; flex-direction:column; }
  header { padding:12px 20px; border-bottom:1px solid var(--border);
           display:flex; align-items:center; gap:10px; }
  header h1 { font-size:15px; font-weight:600; }
  header span { color:var(--dim); font-size:13px; }
  main { flex:1; display:flex; overflow:hidden; }
  #chat { flex:1; display:flex; flex-direction:column; border-right:1px solid var(--border); }
  #events { flex:1; overflow-y:auto; padding:16px; display:flex; flex-direction:column; gap:6px; }
  .event { font-size:13px; padding:8px 12px; border-radius:6px; background:var(--panel);
           border:1px solid var(--border); }
  .event .type { font-weight:600; color:var(--accent); margin-right:8px; }
  .event.deny { border-color:var(--red); }
  .event.approve { border-color:var(--yellow); }
  .event.executed { border-color:var(--green); }
  #input-bar { padding:12px 16px; border-top:1px solid var(--border); display:flex; gap:8px; }
  #task-input { flex:1; background:var(--panel); border:1px solid var(--border);
                border-radius:6px; padding:10px 14px; color:var(--text); font-size:14px; outline:none; }
  #task-input:focus { border-color:var(--accent); }
  button { background:var(--accent); color:#fff; border:none; border-radius:6px;
           padding:10px 18px; font-size:14px; cursor:pointer; font-weight:500; }
  button:hover { opacity:0.9; }
  button.deny { background:var(--red); }
  #sidebar { width:320px; overflow-y:auto; padding:16px; }
  #sidebar h2 { font-size:13px; color:var(--dim); margin-bottom:12px; text-transform:uppercase; }
  .audit-row { font-size:12px; padding:6px 10px; border-radius:4px; background:var(--panel);
               margin-bottom:4px; display:flex; justify-content:space-between; }
  .audit-row .decision.deny { color:var(--red); }
  .audit-row .decision.allow { color:var(--green); }
  .approval-card { background:var(--panel); border:1px solid var(--yellow);
                    border-radius:8px; padding:14px; margin:8px 0; }
  .approval-card .actions { display:flex; gap:8px; margin-top:10px; }
</style>
</head>
<body>
<header>
  <h1>Sentinel</h1>
  <span>Coding Agent Harness</span>
</header>
<main>
  <div id="chat">
    <div id="events"></div>
    <div id="input-bar">
      <input id="task-input" placeholder="Describe a coding task..." />
      <button id="send-btn">Send</button>
    </div>
  </div>
  <div id="sidebar">
    <h2>Audit Trail</h2>
    <div id="audit-list"></div>
  </div>
</main>
<script>
const ws = new WebSocket(`ws://${location.host}/ws`);
const eventsEl = document.getElementById('events');
const auditEl = document.getElementById('audit-list');
const input = document.getElementById('task-input');
const sendBtn = document.getElementById('send-btn');

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'SessionComplete') return;
  const div = document.createElement('div');
  div.className = 'event ' + msg.type.toLowerCase();
  const typeSpan = document.createElement('span');
  typeSpan.className = 'type';
  typeSpan.textContent = msg.type;
  div.appendChild(typeSpan);
  const dataSpan = document.createElement('span');
  dataSpan.textContent = JSON.stringify(msg.data || {});
  div.appendChild(dataSpan);
  eventsEl.appendChild(div);
  eventsEl.scrollTop = eventsEl.scrollHeight;
  if (msg.type === 'ActionExecuted') refreshAudit();
  if (msg.type === 'ApprovalNeeded') renderApprovalCard(msg.data);
};

function renderApprovalCard(data) {
  const card = document.createElement('div');
  card.className = 'approval-card';
  card.innerHTML = `<b>Approval needed</b><br><small>${data.reason} (risk: ${data.risk_level})</small>
    <div class="actions">
      <button onclick="resolveApproval('${data.action_id}','approved')">Approve</button>
      <button class="deny" onclick="resolveApproval('${data.action_id}','denied')">Deny</button>
    </div>`;
  eventsEl.appendChild(card);
}

window.resolveApproval = (id, decision) => {
  ws.send(JSON.stringify({type:'approval', action_id:id, decision}));
};

async function refreshAudit() {
  const r = await fetch('/audit');
  const entries = await r.json();
  auditEl.innerHTML = '';
  entries.slice(-20).forEach(e => {
    const row = document.createElement('div');
    row.className = 'audit-row';
    row.innerHTML = `<span>${e.guardrail}</span><span class="decision ${e.decision}">${e.decision}</span>`;
    auditEl.appendChild(row);
  });
}

sendBtn.onclick = () => {
  const task = input.value.trim();
  if (!task) return;
  eventsEl.innerHTML = '';
  ws.send(JSON.stringify({type:'task', task}));
  input.value = '';
};
input.addEventListener('keydown', (e) => { if (e.key === 'Enter') sendBtn.click(); });
</script>
</body>
</html>
```

- [x] **Step 2: Verify server serves the page**

Run: `python -c "from sentinel.server.app import create_app; from fastapi.testclient import TestClient; c=TestClient(create_app()); r=c.get('/'); print(r.status_code, len(r.text))"`
Expected: `200` and a positive length.

- [x] **Step 3: Run full suite**

Run: `python -m pytest -q`
Expected: 123 passed (no new tests, just static file)

- [x] **Step 4: Commit**

```bash
git add sentinel/server/static/index.html
git commit -m "feat(ui): add minimal linear-app-styled frontend"
```

---

## Task 9: Dockerfile
> **Status:** ✅ complete — commits: 2386f34

**Files:**
- Create: `Dockerfile`
- Create: `.dockerignore`

- [x] **Step 1: Create Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY sentinel/ sentinel/

RUN pip install --no-cache-dir ".[all]"

COPY sentinel/server/static/ static/

ENV SENTINEL_WORKSPACE=/workspace
RUN mkdir -p /workspace

EXPOSE 8000

CMD ["uvicorn", "sentinel.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [x] **Step 2: Create .dockerignore**

`.dockerignore`:
```
.git
.venv
__pycache__
*.pyc
.pytest_cache
*.egg-info
docs/
tests/
*.db
```

- [x] **Step 3: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "chore: add Dockerfile for containerized deployment"
```

---

## Task 10: CI (GitLab + GitHub Actions)
> **Status:** ✅ complete — commits: 2386f34

**Files:**
- Create: `.gitlab-ci.yml`
- Create: `.github/workflows/ci.yml`

- [x] **Step 1: Create .gitlab-ci.yml**

`.gitlab-ci.yml`:
```yaml
stages:
  - test

unit-test:
  stage: test
  image: python:3.12-slim
  before_script:
    - pip install -e ".[dev,all]"
  script:
    - python -m pytest -q
  rules:
    - if: $CI_PIPELINE_SOURCE == "push" || $CI_PIPELINE_SOURCE == "merge_request_event"
```

- [x] **Step 2: Create GitHub Actions workflow**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: pip install -e ".[dev,all]"
      - name: Run tests
        run: python -m pytest -q
```

- [x] **Step 3: Commit**

```bash
git add .gitlab-ci.yml .github/workflows/ci.yml
git commit -m "chore(ci): add GitLab CI and GitHub Actions workflows"
```

---

## Task 11: README
> **Status:** ✅ complete — commits: 2386f34

**Files:**
- Create: `README.md`

- [x] **Step 1: Create README.md**

`README.md`:
```markdown
# Sentinel — A Self-Implemented Coding Agent Harness

> Agent = LLM + Harness. Sentinel makes the harness layer explicit.

Sentinel is a coding agent harness built for the AI4SE final project (Project A).
The LLM is the CPU; Sentinel is everything else: decision loop, tools, governance
guardrails, feedback loops, memory, and configuration — all self-implemented.

## Quick Start

### Local (without Docker)

```bash
pip install -e ".[dev,all]"

# Store your API key securely (never written to code or git)
sentinel config set-key --provider openai
sentinel config status

# Start the WebUI
sentinel serve
# Open http://localhost:8000
```

### Docker

```bash
docker build -t sentinel .
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... sentinel
```

## Testing

All tests run offline with a mock LLM — no network, no Docker, no real API keys:

```bash
python -m pytest -q
```

## Architecture

```
Agent = LLM + Harness
```

- **Decision loop** (`agent_loop`): async-generator event stream, same code in tests (MockLLM + AutoApprove) and prod (real LLM + HumanApprove).
- **Governance** (deep dimension): 4 composable pure-function guardrails (Pattern/ScopeFence/SandboxBoundary/RiskClassifier) + GuardrailPipeline + HITL state machine + append-only audit log. Fail-closed: timeout → denied.
- **Feedback**: pytest/ruff/mypy validators parse tool output into structured `Feedback`, re-injected into context.
- **Memory**: SQLite + TF-IDF retrieval, self-implemented.
- **Tools**: read/write/list/shell/tests/search, each with a declared risk level, confined to a sandbox.
- **Config**: YAML-driven, reproducible per session.

## Credential Security

Keys are stored in the OS keyring (macOS Keychain / Windows Credential Manager / Linux Secret Service), never in code, git, or logs. `sentinel config status` prints `openai: set / anthropic: not set` — never plaintext.

## License

MIT
```

- [x] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with quick start, testing, and architecture"
```

---

## Task 12: Custom API endpoints (`api_base`)
> **Status:** ✅ complete — commits: dd439b6 (PR #2)

**Files:**
- Modify: `sentinel/core/config.py` (+ `api_base` field)
- Modify: `sentinel/core/providers.py` (+ `base_url` param)
- Modify: `sentinel/server/app.py` (`build_llm` passes base_url)
- Test: `tests/test_config.py`, `tests/test_providers.py`, `tests/test_build_llm.py`

**Interfaces:**
- `Config` gains `api_base: dict[str, str] = field(default_factory=dict)`.
- `OpenAIProvider.__init__(api_key, model, base_url: str | None = None, client=None)`
  and `AnthropicProvider.__init__(...)` — when `base_url` is `None`, fall back
  to the official endpoints (`https://api.openai.com` / `https://api.anthropic.com`).
- `build_llm(config, credential_store, env)` passes
  `base_url=config.api_base.get(config.provider)`.

- [x] **Step $1: Write the failing tests**

`tests/test_providers.py` (append):
```python
@pytest.mark.asyncio
async def test_openai_provider_custom_base_url():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok", "tool_calls": []}}]})
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    p = OpenAIProvider(api_key="sk-x", model="gpt-4o-mini",
                       base_url="https://proxy.example.com", client=client)
    await p.complete(messages=[], tools=[])
    assert "proxy.example.com" in seen["url"]
    await client.aclose()

@pytest.mark.asyncio
async def test_anthropic_provider_custom_base_url():
    seen = {}
    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})
    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    p = AnthropicProvider(api_key="sk-ant-x", model="claude-sonnet-4",
                          base_url="https://proxy.example.com", client=client)
    await p.complete(messages=[], tools=[])
    assert "proxy.example.com" in seen["url"]
    await client.aclose()
```

`tests/test_config.py` (append):
```python
def test_config_loads_api_base():
    cfg = load_config(Path(tmp) / "sentinel.yaml")  # with api_base keys
    assert cfg.api_base["openai"] == "https://proxy.example.com"

def test_config_api_base_defaults_empty():
    assert Config(provider="openai", model="m").api_base == {}
```

`tests/test_build_llm.py` (append):
```python
def test_build_llm_passes_base_url():
    # build_llm(Config(provider="openai", model="m", api_base={"openai": "https://proxy"}))
    # → provider.base_url == "https://proxy"
```

- [x] **Step $1: Run tests to verify they fail**

Run: `python -m pytest tests/test_providers.py tests/test_config.py tests/test_build_llm.py -q`
Expected: FAIL — `unexpected keyword argument 'base_url'` / missing `api_base` field.

- [x] **Step $1: Write minimal implementation**

`sentinel/core/config.py` — add field:
```python
api_base: dict[str, str] = field(default_factory=dict)
```
and in `load_config`: `api_base=data.get("api_base", {})`.

`sentinel/core/providers.py`:
```python
class OpenAIProvider:
    def __init__(self, api_key: str, model: str,
                 base_url: str | None = None,
                 client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.AsyncClient(
            base_url=base_url or "https://api.openai.com", timeout=60.0)
```
(Same pattern for `AnthropicProvider`, default `https://api.anthropic.com`.)

`sentinel/server/app.py` — in `build_llm`:
```python
base_url = config.api_base.get(config.provider)
if config.provider == "openai":
    return OpenAIProvider(api_key=key, model=config.model, base_url=base_url)
if config.provider == "anthropic":
    return AnthropicProvider(api_key=key, model=config.model, base_url=base_url)
```

`sentinel.yaml` — add commented example:
```yaml
# api_base:
#   openai: https://your-proxy.example/v1
#   anthropic: https://your-anthropic-proxy.example
```

- [x] **Step $1: Run tests to verify they pass**

Run: `python -m pytest -q`
Expected: all pass (147 + new).

- [x] **Step $1: Commit**

```bash
git add sentinel/core/config.py sentinel/core/providers.py sentinel/server/app.py tests/test_config.py tests/test_providers.py tests/test_build_llm.py sentinel.yaml
git commit -m "feat(config): support per-provider custom API endpoints via api_base"
```

---

## Self-Review Checklist

After all tasks:
- [x] `python -m pytest -q` shows 123+ passed
- [x] No `sk-` key patterns in git: `git log --all -p | findstr "sk-"` returns nothing
- [x] `sentinel config status` works (with a key set)
- [x] `sentinel serve` starts the server on :8000
- [x] Dockerfile builds: `docker build -t sentinel .`
