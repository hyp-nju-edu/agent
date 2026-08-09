# Sentinel — A Self-Implemented Coding Agent Harness

> Agent = LLM + Harness. Sentinel makes the harness layer explicit.

Sentinel is a coding agent harness built for the AI4SE final project (Project A).
The LLM is the CPU; Sentinel is everything else: decision loop, tools, governance
guardrails, feedback loops, memory, and configuration — all self-implemented.
It is "using a harness (Superpowers) to build another harness."

## Project Intro

Sentinel lets you watch an agent work on a coding task in a browser, with
dangerous actions gated by human approval (HITL). Its core value is the
**harness layer**: governance guardrails, an objective feedback loop, tool
dispatch, memory, and configuration are all implemented as deterministic code
that can be unit-tested with a mock LLM — no network, no Docker, no real API
keys required.

## Quick Start

### Local (without Docker)

```bash
pip install -e ".[dev,all]"

# Store your API key securely (never written to code or git)
sentinel config set-key --provider openai
sentinel config status

# (Optional) custom API endpoints in sentinel.yaml:
#   api_base:
#     openai: https://your-proxy.example/v1
#     anthropic: https://your-anthropic-proxy.example
# Unset api_base → official OpenAI/Anthropic endpoints.

# Start the WebUI
sentinel serve
# Open http://localhost:8000
```

### Docker

```bash
docker build -t sentinel .

# Key supplied at run time (never baked into the image):
docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... sentinel
# or, with the key already in the host keyring, omit -e and use the CLI:
#   sentinel config set-key --provider openai   (on the host)
```

## Testing

All tests run offline with a mock LLM — no network, no Docker, no real API keys:

```bash
python -m pytest -q
```

The suite covers every core mechanism deterministically: tool dispatch,
guardrail intercept, approval/HITL (approve / deny / timeout), feedback
parsing, memory read/write, config loading, and the main loop. The §A.6
mechanism demo lives in `tests/test_mechanism_demo.py`.

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

### Module layout

```
sentinel/
  core/
    types.py       # Action, Decision, RiskLevel, Feedback, Event, ...
    llm.py         # LLMProvider protocol + MockLLM
    providers.py   # OpenAI / Anthropic via raw httpx
    tools.py       # Tool protocol + ToolRegistry
    builtins.py    # real built-in tools (read/write/shell/tests/search)
    sandbox.py     # InProcessSandbox (path-boundary enforcement)
    guardrails.py  # 4 guardrails + GuardrailPipeline
    approval.py    # AutoApprove / AutoDeny / ThresholdApprove / HumanApprove
    hitl.py        # HITL state machine (fail-closed)
    audit.py       # append-only audit log
    feedback.py    # pytest/ruff/mypy validators
    memory.py      # SQLite + TF-IDF MemoryStore
    config.py      # YAML config loader
    loop.py        # agent_loop async generator
  credentials.py   # keyring-backed CredentialStore (injectable backend)
  cli.py           # config set-key/status/clear-key, serve
  server/
    app.py         # FastAPI + WebSocket (streams Events, HITL bridge)
    static/        # linear-app-styled single-page WebUI
tests/             # 20 test modules, 147 tests, all offline
docs/              # SPEC.md, PLAN.md, PLAN-PHASE-2.md, SPEC_PROCESS.md,
                   # AGENT_LOG.md, REFLECTION.md
```

## Credential Security

Keys are stored in the OS keyring (macOS Keychain / Windows Credential Manager / Linux Secret Service), never in code, git, or logs. `sentinel config status` prints `openai: set / anthropic: not set` — never plaintext.

- **First run:** `sentinel config set-key --provider openai` prompts with hidden input; the key is written to the keyring.
- **Update / clear:** re-run `set-key` to overwrite; `clear-key --provider <p>` to remove.
- **`.env` fallback:** supported via `python-dotenv` for local dev only — it is plaintext and process-env-visible (documented risk).
- **Threat model:** see `docs/SPEC.md` §4.2 (source code, git history, logs, process env, target machine).
- **Repo hygiene:** a pre-commit scan blocks `sk-` key patterns; no real credentials exist in the history.

## Security Boundary & Known Limitations

- **Sandbox:** the harness runs tools through a sandbox backend. Without Docker it uses `InProcessSandbox` (restricted working directory + path-boundary checks, no container isolation). With Docker it can use a container sandbox; the container runs non-root, no-network-by-default, resource-limited.
- **Fail-closed:** any guardrail ambiguity, approval timeout, or policy error results in **denial**, never execution.
- **Known limitations:**
  - Docker is required only if you want containerized sandbox isolation; the harness core runs without it.
  - The model list in the WebUI is a backend-maintained static registry — no live call to provider `/models` endpoints.
  - WebUI does not accept API keys in the browser; keys are configured via the CLI/keyring.
  - Keyring support depends on the OS backend; the encrypted-file fallback requires a master password.
  - Platforms: Python 3.11+ on macOS / Windows / Linux.

## Distribution

- **Docker image:** `docker build -t sentinel .` + `docker run -p 8000:8000 ...` (see Quick Start). CI builds the image on every push; it is pushed to the public GitHub Container Registry (`ghcr.io/hyp-nju-edu/agent:latest`) on `main` once a `GHCR_PAT` secret (a GitHub PAT with `packages:write`) is configured in the repo.
- **Source / PyPI:** installable as `pip install -e ".[dev,all]"`; the package name is `sentinel-harness`.
- **Deployed WebUI:** public URL to be published at `<deployed-url>` (deployment by the project owner; see below).

## Deployment (WebUI)

The container image runs the FastAPI app on port 8000 with no other dependencies, so it can be
deployed to any container host (Fly.io / Render / Railway / a VPS). Steps:

1. `docker build -t sentinel .`
2. `docker run -p 8000:8000 -e OPENAI_API_KEY=sk-... sentinel` (or configure the key in the
   host keyring via `sentinel config set-key` before `sentinel serve`).
3. Publish the exposed URL here when live: **`<deployed-url>`**.

Deployment is intentionally *not* CI-triggered from this repo (no cloud credentials are stored
here); the project owner performs it and records the URL above.

## CI / CD

- `.gitlab-ci.yml` runs a `unit-test` job (the required NJU GitLab job) on every push.
- `.github/workflows/ci.yml` runs the full offline test suite on every push/PR, and **builds the
  Docker image** (verifying the `Dockerfile`) on the same triggers. On `main`, when a `GHCR_PAT`
  secret is configured, it also pushes the image to GHCR.
- Last CI/CD execution: **passing** (147 tests; image build OK).

## License

MIT
