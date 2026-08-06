# Frontend LLM Provider/Model Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the web UI pick an LLM provider (OpenAI vs Anthropic) and a model per WebSocket session, with the model list served dynamically from the backend.

**Architecture:** Add a static `MODEL_REGISTRY` + `GET /models` endpoint to the FastAPI app. Extend `create_app` with a session-scoped `llm_builder` callable that builds a real LLM provider from a provider/model pair; on failure it emits an `Error` event over the WebSocket. The CLI wires `build_llm` + keyring into `llm_builder`. The frontend fetches `/models`, renders provider/model `<select>`s, and includes the selection in task messages.

**Tech Stack:** Python 3.11+, FastAPI, WebSocket, httpx-based LLM providers, keyring, vanilla JS (no build step), pytest.

**Spec:** `docs/superpowers/specs/2026-08-06-frontend-model-selection-design.md`

## Global Constraints

- Tests must not hit real network or real keyring — inject fake collaborators (httpx.MockTransport, FakeKeyring, injected `llm`, fake `llm_builder`).
- API keys must never appear in code, tests, logs, or the frontend; keys live in keyring via `sentinel config set-key`.
- Session selection never writes `sentinel.yaml`; only the current WebSocket session is affected.
- No live call to provider `/models` endpoints; the registry is a backend-maintained static constant.
- TDD: write the failing test first, verify it fails, then implement, verify it passes, commit.
- Conventional Commits (e.g. `feat: ...`, `test: ...`, `refactor: ...`).
- Run the full suite with `python -m pytest -q` before finishing; all existing 140 tests must stay green.

---

### Task 1: Backend model registry + `GET /models`

**Files:**
- Modify: `sentinel/server/app.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `MODEL_REGISTRY: dict[str, list[str]]` module constant; `GET /models` returning `{"providers": {...}, "default": {"provider": str, "model": str}}`; `create_app(default_provider: str = "openai", default_model: str = "gpt-4o-mini")` kwargs.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server.py`:

```python
from sentinel.server.app import MODEL_REGISTRY, create_app


def test_models_endpoint_defaults():
    client = TestClient(create_app())
    r = client.get("/models")
    assert r.status_code == 200
    data = r.json()
    assert set(data["providers"]) == {"openai", "anthropic"}
    assert data["providers"]["openai"] == [
        "gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"]
    assert data["default"] == {"provider": "openai", "model": "gpt-4o-mini"}


def test_models_endpoint_custom_defaults():
    client = TestClient(create_app(
        default_provider="anthropic", default_model="claude-sonnet-4"))
    data = client.get("/models").json()
    assert data["default"] == {"provider": "anthropic", "model": "claude-sonnet-4"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_server.py -q`
Expected: FAIL — `cannot import name 'MODEL_REGISTRY'` and 404 on `/models`.

- [ ] **Step 3: Write minimal implementation**

In `sentinel/server/app.py`, above `def _build_pipeline`, add:

```python
MODEL_REGISTRY: dict[str, list[str]] = {
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"],
    "anthropic": ["claude-sonnet-4", "claude-opus-4",
                  "claude-3-7-sonnet", "claude-3-5-haiku"],
}
```

Change `create_app` signature to:

```python
def create_app(
    workspace: str = ".",
    llm: LLMProvider | None = None,
    tools: list[Tool] | None = None,
    pipeline: GuardrailPipeline | None = None,
    use_human_approval: bool = False,
    approval_timeout: float = 30.0,
    default_provider: str = "openai",
    default_model: str = "gpt-4o-mini",
) -> FastAPI:
```

Inside `create_app`, after the `/health` route, add:

```python
    @app.get("/models")
    async def get_models():
        return {
            "providers": MODEL_REGISTRY,
            "default": {"provider": default_provider, "model": default_model},
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_server.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_server.py sentinel/server/app.py
git commit -m "feat: add GET /models endpoint with model registry"
```

---

### Task 2: Session-scoped LLM construction via `llm_builder`

**Files:**
- Modify: `sentinel/server/app.py`
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `MODEL_REGISTRY`, `create_app` defaults from Task 1; existing `_run_session`.
- Produces: `create_app(llm_builder: Callable[[str, str], LLMProvider] | None = None)`; `_run_session` accepts `llm_builder`, `provider`, `model`; task messages carrying `provider`/`model` build a real LLM; builder exceptions produce `{"type":"Error","data":{"message":...}}` then `SessionComplete` with no agent events.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_server.py`:

```python
from sentinel.core.llm import MockLLM, LLMResponse


def test_ws_uses_llm_builder():
    calls = []
    def builder(provider, model):
        calls.append((provider, model))
        return MockLLM(responses=[LLMResponse(text="done", tool_calls=[])])
    client = TestClient(create_app(llm_builder=builder))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "hi", "provider": "anthropic",
                      "model": "claude-sonnet-4"})
        events = []
        for _ in range(10):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "SessionComplete":
                break
    assert calls == [("anthropic", "claude-sonnet-4")]
    assert any(e["type"] == "TurnStarted" for e in events)


def test_ws_llm_builder_error_sends_error_event():
    def builder(provider, model):
        raise RuntimeError(f"no api key for provider '{provider}'")
    client = TestClient(create_app(llm_builder=builder))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "hi", "provider": "openai",
                      "model": "gpt-4o-mini"})
        events = []
        for _ in range(5):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "SessionComplete":
                break
    types = [e["type"] for e in events]
    assert "Error" in types
    assert types[-1] == "SessionComplete"
    assert "TurnStarted" not in types


def test_ws_without_provider_falls_back_to_injected_llm():
    calls = []
    def builder(provider, model):
        calls.append((provider, model))
        return MockLLM(responses=[LLMResponse(text="done", tool_calls=[])])
    injected = MockLLM(responses=[LLMResponse(text="done", tool_calls=[])])
    client = TestClient(create_app(llm=injected, llm_builder=builder))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "task", "task": "hi"})
        events = []
        for _ in range(10):
            msg = ws.receive_json()
            events.append(msg)
            if msg.get("type") == "Stopped":
                break
    assert calls == []
    assert any(e["type"] == "TurnStarted" for e in events)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_server.py -q`
Expected: FAIL — `unexpected keyword argument 'llm_builder'`.

- [ ] **Step 3: Write minimal implementation**

In `sentinel/server/app.py`, add `Callable` to the typing import:

```python
from typing import Any, Callable
```

Change `create_app` signature to add the `llm_builder` kwarg (keep the Task 1 kwargs):

```python
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
```

Change the `ws_endpoint` handler to forward the new fields:

```python
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
```

Change `_run_session` signature and body to build a session-scoped LLM:

```python
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
        from sentinel.core.builtins import default_tools
        active_tools = ToolRegistry(tools if tools else [_StubTool()])
        active_pipe = pipeline or _build_pipeline(workspace)
```

(The rest of `_run_session` — approval policy setup and `agent_loop` — is unchanged.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_server.py -q`
Expected: PASS (including the pre-existing WS tests).

- [ ] **Step 5: Commit**

```bash
git add tests/test_server.py sentinel/server/app.py
git commit -m "feat: session-scoped llm_builder with Error event"
```

---

### Task 3: CLI wiring for `build_llm` + keyring

**Files:**
- Modify: `sentinel/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `create_app(llm, llm_builder, default_provider, default_model, ...)` from Tasks 1–2; existing `build_llm`, `load_config`, `get_credential_store`.
- Produces: `build_server_app(config, cs, workspace=".") -> FastAPI` helper in `sentinel/cli.py`; `cmd_serve` delegates to it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sentinel.core.config import Config


def test_build_server_app_defaults():
    from sentinel.cli import build_server_app
    kr = FakeKeyring()
    kr.set_password("sentinel", "openai", "sk-x")
    cs = CredentialStore(backend=kr)
    app = build_server_app(Config(provider="openai", model="gpt-4o-mini"), cs)
    data = TestClient(app).get("/models").json()
    assert data["default"] == {"provider": "openai", "model": "gpt-4o-mini"}


def test_build_server_app_missing_key_raises():
    from sentinel.cli import build_server_app
    cs = CredentialStore(backend=FakeKeyring())
    with pytest.raises(RuntimeError, match="no api key"):
        build_server_app(Config(provider="openai", model="gpt-4o-mini"), cs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_cli.py -q`
Expected: FAIL — `cannot import name 'build_server_app'`.

- [ ] **Step 3: Write minimal implementation**

In `sentinel/cli.py`, add `Config` to the module imports:

```python
from sentinel.core.config import Config
```

Add `build_server_app` above `cmd_serve` and rewrite `cmd_serve`:

```python
def build_server_app(config: Config, cs: CredentialStore,
                     workspace: str = "."):
    """Build the FastAPI app with a session-scoped LLM builder."""
    from sentinel.server.app import build_llm, create_app

    llm = build_llm(config=config, credential_store=cs)
    return create_app(
        workspace=workspace,
        llm=llm,
        llm_builder=lambda p, m: build_llm(
            Config(provider=p, model=m), credential_store=cs),
        default_provider=config.provider,
        default_model=config.model,
        use_human_approval=True,
        approval_timeout=config.approval_timeout,
    )


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn
    from sentinel.core.config import load_config

    config = load_config(args.config)
    cs = get_credential_store()
    try:
        app = build_server_app(config, cs, args.workspace)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        print("hint: run 'sentinel config set-key --provider "
              f"{config.provider}' first", file=sys.stderr)
        return 1
    uvicorn.run(app, host=args.host, port=args.port)
    return 0
```

Note: the `from sentinel.server.app import build_llm` import moves out of `cmd_serve` into `build_server_app` (keep it inside the function to preserve the lazy-import pattern and avoid pulling fastapi at module load).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_cli.py tests/test_build_llm.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sentinel/cli.py tests/test_cli.py
git commit -m "feat: wire llm_builder into serve command"
```

---

### Task 4: Frontend provider/model selectors

**Files:**
- Modify: `sentinel/server/static/index.html`

**Interfaces:**
- Consumes: `GET /models` (Task 1), task message with `provider`/`model`, `Error` event (Task 2).
- Produces: provider + model `<select>`s in the header, populated from `/models`; task messages include the selection; `Error` events render in red. (Frontend has no JS test harness; verification is manual.)

- [ ] **Step 1: Add the selects to the header**

Replace the `<header>` block:

```html
<header>
  <h1>Sentinel</h1>
  <span>Coding Agent Harness</span>
  <select id="provider-select"></select>
  <select id="model-select"></select>
</header>
```

- [ ] **Step 2: Add styles for selects and Error events**

Append to the `<style>` block:

```css
  header select { background:var(--panel); color:var(--text);
                  border:1px solid var(--border); border-radius:6px;
                  padding:6px 10px; font-size:13px; margin-left:auto; }
  header select + select { margin-left:8px; }
  .event.error { border-color:var(--red); }
```

- [ ] **Step 3: Add JS to load models and populate selects**

Add before `sendBtn.onclick`:

```js
let models = null;

async function loadModels() {
  const r = await fetch('/models');
  models = await r.json();
  const provSel = document.getElementById('provider-select');
  provSel.innerHTML = '';
  Object.keys(models.providers).forEach(p => {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = p;
    provSel.appendChild(opt);
  });
  provSel.value = models.default.provider;
  provSel.onchange = populateModels;
  populateModels();
  document.getElementById('model-select').value = models.default.model;
}

function populateModels() {
  const provSel = document.getElementById('provider-select');
  const modelSel = document.getElementById('model-select');
  modelSel.innerHTML = '';
  (models.providers[provSel.value] || []).forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = m;
    modelSel.appendChild(opt);
  });
}

loadModels();
```

- [ ] **Step 4: Include selection in the task message**

Replace the `sendBtn.onclick` body with:

```js
sendBtn.onclick = () => {
  const task = input.value.trim();
  if (!task) return;
  eventsEl.innerHTML = '';
  ws.send(JSON.stringify({
    type: 'task', task,
    provider: document.getElementById('provider-select').value,
    model: document.getElementById('model-select').value,
  }));
  input.value = '';
};
```

- [ ] **Step 5: Render Error events**

Add a branch at the top of `ws.onmessage`:

```js
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.type === 'Error') {
    const div = document.createElement('div');
    div.className = 'event error';
    div.innerHTML = `<b>Error</b><br>${msg.data.message}`;
    eventsEl.appendChild(div);
    return;
  }
  if (msg.type === 'SessionComplete') return;
  ...
};
```

- [ ] **Step 6: Manual verification**

Run: `python -m pytest -q` (all backend tests still pass, including Task 1–2 WS tests).

Start the demo server:
`python -c "import uvicorn; from sentinel.server.app import create_app; uvicorn.run(create_app(), host='0.0.0.0', port=8000)"`

Expected (open http://localhost:8000):
- Provider select shows `openai` / `anthropic`, defaulting to `openai`.
- Model select lists the four OpenAI models, defaulting to `gpt-4o-mini`.
- Changing provider to `anthropic` swaps the model list to the Anthropic models.
- Sending a task produces events; with a fake `llm_builder` scenario, `Error` events render as red cards.

- [ ] **Step 7: Commit**

```bash
git add sentinel/server/static/index.html
git commit -m "feat: frontend provider/model selection"
```

---

## Self-Review Notes

- **Spec coverage:** Section 1 (registry + `/models` + defaults) → Task 1; Section 2 (`llm_builder`, Error event, CLI lambda) → Tasks 2–3; Section 3 (selects, message fields, Error rendering) → Task 4; Section 4 (tests 1–4) → Tasks 1–2; Section 5 out-of-scope items are respected (no key entry, no persistence, static registry).
- **Placeholder scan:** All steps contain full code or exact commands; no TBD/TODO.
- **Type consistency:** `llm_builder` is consistently `Callable[[str, str], LLMProvider]`; `create_app` kwargs `default_provider`/`default_model` match `/models` output keys; `build_server_app(config, cs, workspace)` matches `cmd_serve` usage. `MockLLM`/`LLMResponse` come from `sentinel.core.llm` (already imported in `app.py`).
