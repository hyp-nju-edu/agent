# Frontend LLM Provider/Model Selection — Design

## Goal

Let the web UI pick an LLM provider (OpenAI vs Anthropic) and a model per session.
The selection applies only to the current WebSocket session; it is never written to
`sentinel.yaml`. API keys continue to live in the OS keyring (managed via CLI).

## Background

- `sentinel/server/app.py:create_app()` accepts an injected `llm` (real, built by the
  CLI) or falls back to `MockLLM`. Provider/model are fixed by `sentinel.yaml` at boot.
- `sentinel/server/app.py:build_llm(config, credential_store, env)` resolves a key from
  keyring (then env) and returns an `OpenAIProvider`/`AnthropicProvider`.
- Frontend (`sentinel/server/static/index.html`) sends `{"type":"task","task":...}` over
  the `/ws` WebSocket; events stream back as JSON messages.
- Tests inject collaborators (httpx.MockTransport, fake keyring, injected `llm`) so no
  real network or keyring access is needed.

## Design

### 1. Backend model registry + `GET /models`

- Module-level constant `MODEL_REGISTRY: dict[str, list[str]]` in `sentinel/server/app.py`:
  - `openai`: `["gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini"]`
  - `anthropic`: `["claude-sonnet-4", "claude-opus-4", "claude-3-7-sonnet", "claude-3-5-haiku"]`
- New endpoint `GET /models` returns:
  ```json
  {"providers": {"openai": [...], "anthropic": [...]},
   "default": {"provider": "openai", "model": "gpt-4o-mini"}}
  ```
- `create_app` gains `default_provider: str = "openai"` and
  `default_model: str = "gpt-4o-mini"` kwargs; the CLI passes `config.provider` /
  `config.model` so the UI defaults match the deployed config.

### 2. Session-scoped LLM construction

- `create_app` gains `llm_builder: Callable[[str, str], LLMProvider] | None = None`.
- `_run_session` logic:
  1. If the task message carries `provider` and `model` **and** `llm_builder` is set,
     call `llm_builder(provider, model)` to build the active LLM.
     - On exception (e.g. missing key → `RuntimeError`), send
       `{"type":"Error","data":{"message": str(e)}}` over the socket, then end the
       session (`SessionComplete`) without running the loop.
  2. Otherwise fall back to the injected `llm` (or `MockLLM`).
- CLI `cmd_serve` keeps the eager `llm = build_llm(config, cs)` boot-time validation
  (missing default key still fails fast with the `config set-key` hint) **and** passes
  `llm_builder=lambda p, m: build_llm(Config(provider=p, model=m), credential_store=cs)`.
  The injected `llm` doubles as the fallback for clients that omit provider/model. This
  reuses existing keyring resolution and keeps `create_app` free of `CredentialStore`
  dependencies (testable via a fake builder).

### 3. Frontend

- On load, `fetch('/models')` populates a provider `<select>` and a model `<select>`;
  default selection set from `default`.
- Changing the provider re-populates the model list for that provider.
- Task messages become `{"type":"task","task":..., "provider":..., "model":...}`.
- Render a new `Error` event type (red-styled) with the message text; current
  `SessionComplete` stays silently ignored.

### 4. Tests (TDD)

1. `GET /models` returns the registry structure and configured defaults.
2. WS task with `provider`+`model` + injected fake `llm_builder` → builder invoked with
   those values; event stream flows (use a `MockLLM`-like provider).
3. WS task with `provider`+`model` + `llm_builder` that raises → `Error` event sent,
   then `SessionComplete`, and no agent events.
4. WS task without `provider`/`model` → falls back to injected `llm` (no builder call).

### 5. Explicitly out of scope

- No API-key entry in the browser; keys stay in keyring via `sentinel config set-key`.
- No persistence; session choice never touches `sentinel.yaml`.
- No live call to provider `/models` endpoints; the list is a backend-maintained static
  registry.

## Open Questions / Decisions

None outstanding; user approved the above in brainstorming.
