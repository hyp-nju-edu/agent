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
