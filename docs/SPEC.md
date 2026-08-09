# Sentinel — SPEC.md (Design Document)

> *Spec-Driven, Subagent-Built, Human-Owned.*
>
> Sentinel is a Coding Agent Harness built for the AI4SE final project (Project A).
> This spec is the output of the `brainstorming` skill and the input to `writing-plans`.

---

## 1. Problem Statement

### 1.1 The problem

When an LLM can do most of the "thinking," an engineer's value moves to the
**harness** layer — the engineering that turns a model that only emits "what to
do next" into a system that works reliably. The core equation is:

```
Agent = LLM + Harness
```

The LLM is the CPU; the harness is everything else: decision encapsulation,
tools, context/memory, governance guardrails, feedback loops, and configuration.
Today most users get the harness for free from a closed product (Claude Code,
Cursor, etc.) and never touch this layer. Sentinel makes that layer explicit
and self-implemented.

### 1.2 Target users

- **Developers** who want to watch an agent work on a coding task in a browser,
  with dangerous actions gated by human approval (HITL).
- **Students/researchers** who want a small, readable, **mock-LLM-testable**
  harness kernel to study how governance, feedback, and tool dispatch actually
  work in code — not in prompts.

### 1.3 Why it's worth building

Sentinel answers the course's central question — *when LLMs do most of the
coding, where is the engineer's value?* — by making that value the deliverable:
governance, feedback, context, safety, and distribution. It is "using a harness
(Superpowers) to build another harness," producing first-hand, critical
understanding of agentic-SE methodology. The deep dimension is **governance**,
because it is the most code-heavy, deterministic, and unit-testable mechanism —
the clearest demonstration that the harness is real engineering, not a prompt.

---

## 2. User Stories

All stories follow INVEST (Independent, Negotiable, Valuable, Estimable, Small,
Testable).

- **US1 — Run a coding task.** As a developer, I want to send a coding task
  (e.g. "fix the failing test in `tests/test_foo.py`") via the WebUI and watch
  the agent read files, edit code, run tests, and report results, so that I
  delegate a well-scoped coding chore.
- **US2 — Gate dangerous actions (HITL).** As a developer, when the agent
  proposes a dangerous action (`rm -rf`, `git push --force`, deleting a DB), I
  want to see an inline approve/deny card with the action, risk level, and
  reason, so that nothing destructive runs without my explicit consent.
- **US3 — Fail-closed on no response.** As a developer, if I don't respond to
  an approval request within the timeout, I want the action to be **denied**
  (not executed), so that inattention can never cause damage.
- **US4 — Self-correct from test feedback.** As a developer, when the agent
  runs tests and they fail, I want the agent to receive structured failure
  feedback and change its next action to fix the failure, so that it closes the
  loop without me nudging it.
- **US5 — Configure behavior declaratively.** As a developer, I want a YAML
  config to set the provider/model, allowed tools, risk thresholds, sandbox
  settings, and guardrail patterns, so that I constrain the agent without
  editing code.
- **US6 — Secure key setup.** As a developer on a fresh machine, I want a
  guided, hidden-input command to store my OpenAI/Anthropic key in the OS
  keyring, and a status command that never echoes plaintext, so that my key
  never lands in code, git, or logs.
- **US7 — Audit a run.** As a developer, after a session I want to view the
  audit trail (every action, its guardrail decision, risk level, and outcome),
  so that I can review what the agent did and why each action was allowed or
  blocked.
- **US8 — Run offline tests.** As a maintainer, I want a one-command test suite
  that exercises every core mechanism with a mock LLM and no network, so that I
  can verify the harness logic deterministically in CI.

---

## 3. Functional Specification (by module)

Each module lists **input / behavior / output / boundary / error handling**.
Modules map to the six harness dimensions (§A.3) plus the WebUI and supporting
infrastructure.

### 3.1 Decision / Main Loop (`agent_loop`)

- **Input:** `RunContext` (task, config snapshot, memory snippets, recent
  turns, tool results), an `LLMProvider`, a `ToolRegistry`, a `GuardrailPipeline`,
  an `ApprovalPolicy`, `max_turns`.
- **Behavior:** `async def agent_loop(...) -> AsyncIterator[Event]`. Each turn:
  organize context → call `llm.complete(messages, tools)` → parse response into
  one or more `Action`s → run each through the guardrail pipeline → if
  `RequiresApproval`, yield `ApprovalNeeded` and await the policy → if allowed,
  execute the tool in the sandbox → capture result → run feedback validators →
  re-inject feedback into context → repeat. Stop on: LLM "done" signal,
  `max_turns`, or unrecoverable error.
- **Output:** an event stream: `TurnStarted`, `LLMResponse`, `ActionRequested`,
  `ApprovalNeeded`, `ActionExecuted`, `FeedbackReceived`, `TurnComplete`,
  `Stopped`.
- **Boundary:** the loop is the **same code** in tests (`MockLLM` +
  `AutoApprove`) and prod (real LLM + `HumanApprove`); only the injected
  collaborators change. No I/O lives in the loop except through injected
  interfaces.
- **Errors:** LLM call failure → retry with backoff (bounded) then yield
  `Stopped(reason=llm_error)`. Unparseable LLM response → yield a
  `ParseError` event and continue (the LLM is re-prompted with the parse
  failure). Tool execution failure → captured as `ActionExecuted(success=False)`
  and fed back as feedback.

### 3.2 Tools (`Tool` layer)

- **Input:** `Action(tool, args, ...)`.
- **Behavior:** `Tool` protocol with `execute(args, sandbox) -> ToolResult`.
  Registry maps tool name → `Tool` instance. MVP set: `read_file`,
  `write_file`, `list_dir`, `run_shell`, `run_tests`, `search`. Each tool
  declares a default `risk_level`. Execution goes through a pluggable
  `SandboxBackend`: `DockerSandbox` (primary, prod) or `InProcessSandbox`
  (restricted working dir, for environments without Docker and for mock-LLM
  tests). Results are truncated to fit context.
- **Output:** `ToolResult(success, stdout, stderr, truncated, artifacts)`.
- **Boundary:** tools never run outside *a* sandbox backend; paths are
  confined to the sandbox workspace. The `InProcessSandbox` enforces the same
  path boundaries as `DockerSandbox` (defense in depth: the `ScopeFenceGuardrail`
  checks paths *before* execution regardless of backend). Adding a tool =
  register a class + declare its risk.
- **Errors:** sandbox unavailable → `ToolResult(success=False, error)`. Command
  not found / non-zero exit → captured as a normal result (non-zero is
  *information*, not a harness error). Output exceeds limit → truncated with a
  marker.

### 3.3 Governance (`Guardrail` pipeline + HITL + audit) — **DEEP DIMENSION**

Detailed in §9. Summary here:

- **Input:** `Action` + `RunContext`.
- **Behavior:** a composable pipeline of `Guardrail`s, each returning
  `GuardrailResult(decision, reason, risk_level)`. Aggregation: any `Deny` →
  `Deny` (short-circuit); else any `RequiresApproval` → `RequiresApproval`
  (highest risk wins); else `Allow`. `RequiresApproval` actions enter the HITL
  state machine; the `ApprovalPolicy` resolves them. Every decision is appended
  to the audit log.
- **Output:** `GuardrailResult`; downstream `ApprovalNeeded` / `ActionExecuted` /
  `Skipped` events; `AuditEntry` rows.
- **Boundary:** guardrails are pure functions of `(action, ctx)` — no LLM, no
  network, no time-of-day effects. Fail-closed: timeout or policy error →
  `Denied`.
- **Errors:** a guardrail that raises → treated as `Deny(reason=guardrail_error)`
  (fail-closed). Illegal HITL transition → raises (programming error, caught in
  tests).

### 3.4 Feedback (`Validator` layer)

- **Input:** `ToolResult` from a `run_tests` / `run_shell` action.
- **Behavior:** the loop selects a `Validator` by inspecting the action's
  tool/args (e.g. `run_tests` → `pytest` validator; `run_shell` with `ruff …`
  → `ruff` validator; `run_shell` with `mypy …` → `mypy` validator). The
  validator parses the output into structured `Feedback(pass, failures)` where
  each failure is classified (`syntax_error`, `assertion_failure`,
  `import_error`, `type_error`, `unknown`). Feedback is re-injected into the
  next turn's context.
- **Output:** `Feedback` object + `FeedbackReceived` event.
- **Boundary:** validators are deterministic parsers; they never call the LLM.
  Unknown output → `unknown` classification (still useful: pass/fail is known).
- **Errors:** unparseable output → `Feedback(pass=unknown, failures=[])`; the
  raw output is still attached for the agent.

### 3.5 Memory (MVP, self-implemented)

- **Input:** a query (task + recent context).
- **Behavior:** retrieve relevant `Memory` rows (project conventions, past
  decisions, codebase notes) by keyword + simple TF-IDF. Loaded as context
  snippets per turn, not wholesale. Writes happen when the agent (or user)
  records a decision/convention.
- **Output:** a ranked list of memory snippets.
- **Boundary:** storage and retrieval are implemented in Sentinel's own code
  (no framework memory). No mandatory vector embeddings at MVP; TF-IDF over
  text is sufficient and self-contained.
- **Errors:** store failure → log and continue (memory is best-effort, not
  on the critical path).

### 3.6 Configuration

- **Input:** a YAML file (`sentinel.yaml`).
- **Behavior:** load provider+model, **custom API endpoints (`api_base`)**,
  allowed tools, risk thresholds, sandbox settings (image, mounts, network
  default-off), guardrail patterns, `max_turns`, approval timeout. A snapshot
  is stored per session so a run is reproducible from its config.
- **`api_base`:** optional per-provider endpoint override, e.g.
  `api_base: {openai: https://my-proxy.example/v1, anthropic: https://...}`.
  Defaults to the official OpenAI/Anthropic endpoints when absent. Keys never
  live in config (see §7), so an API proxy configured here is only an endpoint
  URL — credentials still come from the keyring/env.
- **Output:** a `Config` object + a `ConfigSnapshot` row.
- **Boundary:** unknown keys → warning (ignored); missing required keys →
  startup error. Config never contains secrets (keys live in the keyring).
- **Errors:** invalid YAML / schema → fail fast at startup with a clear
  message.

### 3.7 WebUI (FastAPI + Open Design frontend)

- **Input:** WebSocket connection per session; REST for session list / audit
  trail / config.
- **Behavior:** consume the `agent_loop` async generator; stream `Event`s to
  the browser; render `ApprovalNeeded` as an inline approve/deny card; resolve
  approvals back into the `HumanApprove` policy. Frontend built with **Open
  Design** (`linear-app` design system, `dashboard` skill).
- **Output:** a live, streaming chat + event log + HITL surface + audit-trail
  view.
- **Boundary:** the WebUI is a transport/presentation layer over the testable
  core; it contains no harness logic. WebSocket disconnect mid-approval → the
  pending action times out (fail-closed).
- **Errors:** WebSocket error → session marked `interrupted`; user can resume
  from the last checkpointed turn.

### 3.8 Credential management (`config` CLI)

- **Input:** `sentinel config set-key --provider <p>` (hidden input),
  `sentinel config status`, `sentinel config clear-key --provider <p>`.
- **Behavior:** store/retrieve/clear keys in the OS keyring via Python's
  `keyring`. `status` prints `openai: set / anthropic: not set` — never
  plaintext. `.env` loading supported as a documented fallback.
- **Output:** exit code + status line.
- **Boundary:** keys are never logged, never written to config files, never
  echoed. `.env` is plaintext (documented risk).
- **Errors:** keyring backend missing → fall back to encrypted-file store with
  a master password (and warn). Wrong key → surfaced as an LLM auth error at
  first call.

---

## 4. Non-Functional Requirements

### 4.1 Performance

- A single agent turn (LLM call excluded, since it dominates) must complete its
  harness-side work (parse + guardrail + approve + execute + feedback) in
  **< 200 ms** on a laptop.
- WebSocket event latency (harness → browser) **< 100 ms** for local
  deployments.
- Sandbox container startup **< 5 s** (warm image); a cold first run may be
  longer and is reported in the UI.

### 4.2 Security (with credential threat model)

**Credential threat model:**

| Threat | Mitigation |
|---|---|
| Key in source code | Never hardcoded; a pre-commit hook scans for key patterns (`sk-...`, `sk-ant-...`). |
| Key in git history | `.env` is `.gitignore`'d; pre-commit guard blocks commits containing key patterns; if leaked, rotate. |
| Key in logs | Logging redaction: `Authorization` headers and key material are never logged; a redacting formatter is mandatory. |
| Key in process env (visible to other processes) | Keyring is preferred (retrieved at runtime, not persisted in env); `.env` is documented as plaintext and process-env-visible. |
| Key on target/distribution machine | README documents keyring setup on the target; Docker image reads the key from keyring or an env var supplied at `docker run`. |

**Sandbox security:** sandbox containers run non-root, no network by default,
resource-limited (CPU/mem), read-only system paths, bounded workspace mount.
Network enablement is per-action and requires approval.

**Fail-closed default:** any ambiguity (guardrail error, approval timeout,
policy failure) results in denial, never execution.

### 4.3 Usability

- One-command local run (`sentinel serve` or `docker run`).
- Guided first-run key setup with hidden input.
- The WebUI shows the agent's reasoning, actions, approvals, and results in a
  single streaming view; no need to read logs to follow a run.

### 4.4 Observability

- Every action emits an `AuditEntry` (guardrail, decision, risk, outcome,
  timestamp).
- The audit trail is queryable (by tool / risk / decision / time) and rendered
  in the WebUI.
- Structured logs (JSON) with key redaction; log level configurable.

### 4.5 Portability

- Python 3.11+. Runs on macOS / Windows / Linux.
- Docker required for the sandbox backend; the harness itself runs without
  Docker in mock-LLM tests.

---

## 5. System Architecture

### 5.1 Component diagram

```
┌──────────────────────── browser (Open Design frontend) ────────────────────┐
│  chat input · streaming event log · inline HITL approve/deny · audit view  │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ WebSocket (events) + REST (list/audit)
┌──────────────────────────────────▼────────────────────────────────────────┐
│  WebUI layer (FastAPI)                                                      │
│  - consumes async generator, streams Events, resolves HumanApprove          │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ drives
┌──────────────────────────────────▼────────────────────────────────────────┐
│  Harness core (testable with MockLLM + AutoApprove, no network/Docker)     │
│                                                                            │
│  ┌──────────────┐   ┌──────────────┐   ┌───────────────────────────────┐  │
│  │ agent_loop   │──▶│ LLMProvider  │   │ GuardrailPipeline (DEEP)       │  │
│  │ (async gen)  │   │ (OpenAI/     │   │  Pattern/ScopeFence/           │  │
│  │              │   │  Anthropic/  │   │  SandboxBoundary/RiskClassify  │  │
│  │              │   │  Mock)       │   │  + ApprovalPolicy + HITL FSM  │  │
│  │              │   └──────────────┘   │  + AuditLog                     │  │
│  │              │──▶┌──────────────┐   └───────────────────────────────┘  │
│  │              │   │ ToolRegistry │                                      │
│  │              │   │ (read/write/ │                                      │
│  │              │   │  shell/test) │                                      │
│  │              │   └──────┬───────┘                                      │
│  │              │──▶┌──────▼───────┐   ┌───────────────────────────────┐  │
│  │              │   │ Validators   │   │ Memory (SQLite + TF-IDF)        │  │
│  │              │   │ (pytest/ruff/│   │ Config (YAML + snapshot)        │  │
│  │              │   │  mypy)       │   │                                 │  │
│  └──────────────┘   └──────────────┘   └───────────────────────────────┘  │
└──────────────────────────────────┬────────────────────────────────────────┘
                                   │ tool execution
┌──────────────────────────────────▼────────────────────────────────────────┐
│  Docker sandbox container (per session)                                    │
│  bounded workspace mount · no network by default · non-root · res-limited │
└────────────────────────────────────────────────────────────────────────────┘
                                   │
                          external LLM provider (OpenAI / Anthropic)
```

### 5.2 Data flow (one turn)

1. User sends a task via the browser → WebSocket → `agent_loop` starts.
2. Loop calls `llm.complete(...)` → LLM returns an action (e.g.
   `run_shell: pytest`).
3. Action enters the `GuardrailPipeline` → `Allow` / `Deny` /
   `RequiresApproval`.
4. If `RequiresApproval` → loop yields `ApprovalNeeded` → browser renders an
   approve/deny card → `HumanApprove` awaits the reply (timeout → fail-closed
   deny).
5. If allowed → tool executes in the Docker sandbox → `ToolResult`.
6. `Validator` parses the result → `Feedback` → re-injected into context.
7. Loop continues until `Stopped` (done / `max_turns` / error).

### 5.3 External dependencies

- **LLM providers:** OpenAI (chat completions API), Anthropic (messages API) —
  behind the `LLMProvider` abstraction.
- **Sandbox:** Docker daemon (via socket mount) for sandbox containers.
- **Libraries:** `fastapi`, `uvicorn`, `websockets`, `keyring`, `pytest`,
  `pytest-asyncio`, `docker` (Python SDK), `pyyaml`, `sqlite3` (stdlib). Open
  Design for the frontend build.

---

## 6. Data Model

Storage: SQLite (file-based, no server). All schemas are illustrative; final
DDL lives in the implementation.

- **Session** — `id` (pk), `created_at`, `task` (text), `status`
  (`running|completed|interrupted|error`), `config_snapshot_id` (fk).
- **Turn** — `id` (pk), `session_id` (fk), `index` (int), `llm_response`
  (text), `status`.
- **Action** — `id` (pk), `turn_id` (fk), `tool`, `args` (json), `risk_level`
  (`low|medium|high|critical`), `governance_decision`
  (`allow|deny|require_approval`), `status`
  (`proposed|executing|executed|failed|skipped`), `result` (json).
- **Approval** — `id` (pk), `action_id` (fk, unique), `decision`
  (`approved|denied|timeout`), `decided_by` (text), `decided_at`, `reason`.
- **Feedback** — `id` (pk), `action_id` (fk), `kind`
  (`pytest|ruff|mypy`), `pass` (bool), `failures` (json array).
- **AuditEntry** — `id` (pk), `action_id` (fk), `guardrail` (text), `decision`,
  `risk_level`, `timestamp`, `outcome`.
- **Memory** — `id` (pk), `kind` (`convention|decision|note`), `key`, `content`
  (text), `created_at`.
- **ConfigSnapshot** — `id` (pk), `session_id` (fk), `config_yaml` (text).

**Constraints:** one `Approval` per `Action` (1:1); an `Action` may have many
`AuditEntry` rows (one per guardrail run); `Action.status` transitions are
governed by the HITL state machine (§9.4).

---

## 7. Credential & Distribution Design

### 7.1 Credential storage, entry, update, clear

- **Storage:** OS keyring via Python `keyring` (macOS Keychain / Windows
  Credential Manager / Linux Secret Service). Fallback: an encrypted file with
  a master password (when no keyring backend is available).
- **Entry (first run):** `sentinel config set-key --provider openai` prompts
  with hidden input (`getpass`); the key is written to the keyring, never to
  disk config.
- **View status:** `sentinel config status` prints `openai: set / anthropic:
  not set` — never plaintext.
- **Update / clear:** `sentinel config set-key --provider openai` (overwrite);
  `sentinel config clear-key --provider anthropic` (delete from keyring).
- **`.env` fallback:** supported via `python-dotenv`, documented as plaintext +
  process-env-visible; recommended only for local dev.
- **Custom API endpoints (`api_base`, §3.6):** an endpoint override is a URL
  only — no secrets. If you point it at a proxy/relay, the API key still comes
  from the keyring (or env), never from `sentinel.yaml`. This keeps the
  credential threat model (§4.2) unchanged while supporting network-restricted
  environments (e.g. regions that cannot reach api.openai.com directly).

### 7.2 Distribution

- **Primary: Docker image.** Single `docker build` + single `docker run`. The
  image contains the FastAPI backend + the built Open-Design frontend. It
  mounts the Docker socket (`/var/run/docker.sock`) to spawn per-session
  sandbox containers. Pushed to a public registry (GitHub Container Registry).
- **Secondary: PyPI package.** `pip install sentinel-harness` for local use
  without Docker; falls back to the `InProcessSandbox` backend (same path
  boundaries, no container isolation) — suitable for demos and local
  single-user use.
- **README** documents: get + run commands, **key configuration on the target
  machine** (keyring setup, or `docker run -e OPENAI_API_KEY=...`), and known
  limitations (Docker required for sandbox; keyring platform support matrix).

### 7.3 Deployment

- Containerized deployment to a free-tier host (Render / Fly.io / Railway) to
  satisfy the "accessible WebUI URL" requirement. README documents the deploy
  architecture and CI/CD.

---

## 8. Technology Selection & Rationale

| Choice | Rationale |
|---|---|
| **Python 3.11+** | Richest LLM/AI ecosystem; easy mock-LLM testing with `pytest`/`pytest-asyncio`; fast iteration; natural fit for an agent harness. |
| **async-generator event loop** | Real-time streaming UX + clean HITL (approval is an injectable policy); the same loop runs in tests (`MockLLM` + `AutoApprove`) and prod. |
| **Provider-agnostic LLM layer** | Supports OpenAI + Anthropic behind one `LLMProvider` protocol; the mock sits behind the same interface, so all core tests are provider-independent. |
| **Custom API endpoints (`api_base`)** | Per-provider endpoint override in `sentinel.yaml`; provider constructors take `base_url: str | None = None` and fall back to official endpoints. Supports network-restricted environments (proxy / relay / China-friendly endpoints) without touching credentials. |
| **FastAPI + WebSocket** | Native async, first-class WebSocket, simple REST for audit/config; pairs cleanly with the async generator. |
| **Open Design (`linear-app`, `dashboard` skill)** | Course-recommended design tooling; `linear-app` gives a clean developer-tool aesthetic that fits a coding harness; `dashboard` skill suits the chat + audit layout. |
| **Docker sandbox** | Strong isolation; the sandbox itself is a guardrail layer (no network, non-root, res-limited); great governance narrative. |
| **SQLite** | File-based, no server, sufficient for single-user session/audit data; trivially testable in CI. |
| **OS keyring (`keyring`)** | Cross-platform secure storage; satisfies the credential-security requirement without custom crypto. |
| **GitHub-primary + `.gitlab-ci.yml` for NJU** | GitHub for public repo + PR workflow; `.gitlab-ci.yml` with a `unit-test` job for the NJU GitLab submission requirement. |

---

## 9. 领域与机制设计 (Domain & Mechanism Design) [A.5]

This section answers the four required mechanism questions for the **coding**
domain and specifies how each is **coded** (not prompted), satisfying §A.4-B/C.

### 9.1 The four mechanism questions (coding domain)

- **Actions / tools:** read/write files, execute shell, run tests, search. Each
  tool is a `Tool` class with a declared risk level; execution is confined to
  the Docker sandbox.
- **Objective feedback signal:** running `pytest` / `ruff` / `mypy` produces
  deterministic, parseable output. A `Validator` parses it into structured
  `Feedback` (pass/fail + classified failures) and re-injects it into context.
  This is *code*, not "please check your work."
- **Dangerous actions:** `rm -rf`, `DROP TABLE`, `git push --force`,
  `curl … | sh`, writes outside the workspace, reads of `~/.ssh` / `.env` /
  `**/*.key`, network access in a no-network sandbox. These are intercepted by
  guardrails (§9.2) and gated by HITL (§9.4).
- **Memory:** project conventions, past decisions, codebase notes — stored in
  SQLite, retrieved by keyword + TF-IDF, loaded as snippets per turn.

### 9.2 Deep dimension: why governance, and how it is coded

**Why governance.** Governance is the most code-heavy, deterministic, and
unit-testable dimension. It has the clearest "mechanism = code" form: a
`guardrail(action)` function that returns `Deny` for `rm -rf /` every single
time, with no LLM in the loop. It also carries the strongest safety narrative
(fail-closed, HITL, audit), which is the heart of "what an engineer owns when
the LLM does the coding."

**How it is coded.** Four composable, pure-function guardrails + an injectable
approval policy + a HITL state machine + an audit log.

```python
# Action model — governance inspects structured actions, never raw model text.
@dataclass
class Action:
    tool: str
    args: dict
    raw_source: str
    turn_id: str

class Decision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"

@dataclass
class GuardrailResult:
    decision: Decision
    reason: str
    risk_level: RiskLevel   # low|medium|high|critical
    guardrail_name: str

class Guardrail(Protocol):
    name: str
    def check(self, action: Action, ctx: RunContext) -> GuardrailResult: ...
```

Concrete guardrails (each independently unit-testable, no LLM):

- **`PatternGuardrail`** — regex/keyword match on shell commands & args. Catches
  `rm -rf`, `DROP TABLE`, `git push --force`, `curl … | sh`, `chmod 777`, fork
  bombs. Pattern set is YAML-configurable.
- **`ScopeFenceGuardrail`** — path boundary enforcement. Writes confined to the
  working dir; reads of sensitive paths (`~/.ssh`, `~/.aws`, `.env`,
  `**/credentials*`, `**/*.key`) blocked. Configurable allow/deny path globs.
  Defense-in-depth with the physical sandbox mount.
- **`SandboxBoundaryGuardrail`** — flags actions needing network (`pip install`,
  `curl`, `git clone`) since the sandbox is no-network by default; flags
  resource-heavy actions. Returning `RequiresApproval` here can also trigger a
  sandbox reconfiguration (e.g. enable network for this one action).
- **`RiskClassifierGuardrail`** — assigns `low/medium/high/critical` from tool +
  args + pattern matches. Drives the approval threshold.

**Pipeline aggregation:** any `Deny` → final `Deny` (short-circuit,
fail-closed); else any `RequiresApproval` → final `RequiresApproval` (highest
risk wins); else `Allow`.

### 9.3 Injectable approval policy (the testability hinge)

```python
class ApprovalPolicy(Protocol):
    async def approve(self, action: Action, r: GuardrailResult) -> Approval: ...
```

Implementations: `AutoApprove` / `AutoDeny` (tests, deterministic, no I/O);
`ThresholdApprove` (auto-approve low/medium, escalate high/critical);
`HumanApprove` (prod; yields `ApprovalNeeded`, awaits the WebSocket reply,
**timeout → fail-closed deny**). Because the policy is injected, the *same*
`agent_loop` runs in tests and in prod.

### 9.4 HITL state machine

Each `RequiresApproval` action walks a state machine; transitions are code,
each emits an `AuditEntry`:

```
Proposed → Evaluating → PendingApproval → {Approved | Denied | Timeout}
                                              ↓ Approved            ↓ Denied/Timeout
                                           Executing              Skipped
                                              ↓
                                        Executed | Failed
```

- **Timeout → `Denied` (fail-closed):** no action ever executes without an
  explicit approval.
- Illegal transitions raise (e.g. `PendingApproval → Executing` is forbidden).
- Directly testable: construct `PendingApproval`, inject `Approved` → assert
  `Executing`; inject timeout → assert `Skipped`.

### 9.5 Audit log

Append-only SQLite record of every action + guardrail decision + risk level +
reason + outcome. Queryable by tool / risk / decision / time. Rendered in the
WebUI as the run's audit trail.

### 9.6 Deterministic testability (satisfies §A.4-C)

Every line below runs with **no LLM, no network, no Docker**:

```python
assert guardrail(Action("run_shell", {"cmd": "rm -rf /"})).decision == DENY
assert guardrail(Action("write_file", {"path": "../../etc/passwd"})).decision == DENY
assert guardrail(Action("run_shell", {"cmd": "pytest"})).decision == ALLOW
# HITL: inject Approved → Executing; inject Timeout → Skipped
# Audit: run a scripted sequence, assert the exact entry list
```

### 9.7 Mechanism demonstration (satisfies §A.6)

A reproducible script/test under `MockLLM`:

1. **① Governance intercept:** `MockLLM` scripts `rm -rf /`; the guardrail
   denies it; assert the event sequence shows `Deny` and no execution.
2. **② Feedback self-correction:** inject a failing `pytest` run; the
   `Validator` produces `Feedback(pass=False, failures=[assertion_failure])`;
   assert the agent's next action changes (e.g. it reads the failing test and
   edits the source).
3. **③ HITL depth:** `MockLLM` scripts a high-risk action; `ApprovalNeeded` is
   yielded; inject `Approved` → action executes; inject `Denied` → skipped;
   inject `Timeout` → fail-closed skip. Assert states + audit entries.

---

## 10. Acceptance Criteria

Each feature's "done" is objectively checkable.

- **AC1 (end-to-end run):** with a real LLM key, the agent completes a simple
  coding task: read a file → edit it → run `pytest` → fix a failure → report
  done. Visible in the WebUI as a full event stream.
- **AC2 (six dimensions runnable):** all of decision/tools/memory/governance/
  feedback/config have a runnable minimum; the loop closes (action → feedback
  → corrected action) without manual nudging.
- **AC3 (governance intercept):** `rm -rf /`, out-of-scope writes, and
  sensitive-path reads are denied by guardrails; a high-risk action yields
  `ApprovalNeeded` and is gated by the WebUI approve/deny card.
- **AC4 (fail-closed):** an approval that times out is denied (not executed).
- **AC5 (mock-LLM tests):** the full mock-LLM test suite passes deterministically
  offline (`make test`, no network, no Docker, no real LLM).
- **AC6 (mechanism demo):** the §9.7 demo (①②③) reproduces under `MockLLM`.
- **AC7 (credentials):** a key set via `sentinel config set-key` is stored in
  the keyring; `git log` / source / logs contain no key material (verified by a
  pre-commit scan).
- **AC8 (distribution):** `docker build && docker run` starts the WebUI on a
  fresh machine; the deployed URL is publicly accessible.
- **AC9 (audit):** every action in a session has `AuditEntry` rows queryable
  via the WebUI audit view.

---

## 11. Risks & Open Questions

- **R1 — Docker socket mount.** Spawning sandbox containers via the mounted
  Docker socket is a security surface and adds complexity. *Mitigation:* the
  sandbox image is hardened (non-root, no network, res-limited); the socket is
  never exposed to the agent itself (only the harness uses it).
- **R2 — LLM output parsing fragility.** The action parser must be robust to
  malformed model output. *Mitigation:* schema-validated tool calls
  (function-calling where the provider supports it); a `ParseError` event +
  re-prompt path for unparseable output.
- **R3 — Async test complexity.** Async generators are slightly harder to test
  than sync code. *Mitigation:* `pytest-asyncio` + injectable policies keep
  mock-LLM tests simple and deterministic.
- **R4 — Open Design integration curve.** Wiring an Open-Design-generated
  frontend to a FastAPI WebSocket backend is a learning step. *Mitigation:* keep
  the frontend surface minimal (chat + event log + HITL card + audit view).
- **R5 — Real-LLM cost during development.** *Mitigation:* mock-LLM-first
  testing; real-LLM runs only for end-to-end smoke checks.
- **R6 — Scope creep.** Six dimensions invite breadth. *Mitigation:* the MVP cut
  (§3) keeps five dimensions minimal; only governance goes deep.
- **OQ1 — Repo host.** Confirmed: GitHub-primary (public repo + PR workflow) +
  a `.gitlab-ci.yml` with a `unit-test` job for the NJU GitLab submission
  mirror. CI runs on GitHub Actions; the `.gitlab-ci.yml` is kept in sync and
  must pass on NJU GitLab before submission.
- **OQ2 — Sandbox networking.** Default no-network; per-action network
  enablement requires approval. Whether to allow `pip install` (common in
  coding tasks) by default-with-approval or deny-by-default is a config
  decision, defaulted to *requires approval*.

---

*End of SPEC.md. Next step: `writing-plans` skill produces `PLAN.md` from this
spec, after the user reviews this document.*
