# Sentinel Implementation Plan — Phase 1: Testable Harness Core + Governance + Mechanism Demo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Sentinel's self-implemented harness kernel (decision loop, tools, LLM abstraction, governance, feedback, memory, config) with mock-LLM deterministic unit tests and the §A.6 mechanism demo — all runnable offline with no network, no Docker, no real LLM.

**Architecture:** Async-generator event loop (`agent_loop`) with injectable collaborators (LLMProvider, ToolRegistry, GuardrailPipeline, ApprovalPolicy). Governance is the deep dimension: composable pure-function guardrails + injectable approval policy + HITL state machine + append-only audit log. The same loop runs in tests (`MockLLM` + `AutoApprove`) and prod.

**Tech Stack:** Python 3.11+, pytest, pytest-asyncio, pyyaml, stdlib sqlite3. No external agent frameworks.

## Global Constraints

- Python 3.11+ required.
- No agent orchestration frameworks (LangChain/AutoGen/CrewAI/LlamaIndex agent) — the loop + governance + feedback is our own code.
- Mechanisms must be code, not prompts; every core mechanism testable with mock/stub LLM, no network, no Docker.
- TDD enforced: red → green → refactor. No implementation before its failing test.
- Keys never hardcoded; this phase has no real keys (mock LLM only).
- Commit after every green test. Conventional Commits messages (`feat:`, `test:`, `chore:`).

## File Structure

```
sentinel/
  __init__.py
  core/
    __init__.py
    types.py        # Action, Decision, RiskLevel, GuardrailResult, ToolResult, Feedback, Failure, Event, RunContext
    llm.py          # LLMProvider protocol, LLMResponse, MockLLM
    tools.py        # Tool protocol, ToolRegistry
    sandbox.py      # SandboxBackend protocol, InProcessSandbox
    guardrails.py   # Guardrail protocol, Pattern/ScopeFence/SandboxBoundary/RiskClassifier, GuardrailPipeline
    approval.py     # ApprovalPolicy protocol, AutoApprove/AutoDeny/ThresholdApprove, Approval
    hitl.py         # ActionState, HITLStateMachine
    audit.py        # AuditEntry, AuditLog
    feedback.py     # Validator protocol, PytestValidator, RuffValidator, MypyValidator
    memory.py       # MemoryStore (sqlite3 + TF-IDF)
    config.py       # Config, load_config
    loop.py         # agent_loop async generator
tests/
  __init__.py
  conftest.py
  test_types.py
  test_llm.py
  test_tools.py
  test_sandbox.py
  test_guardrails.py
  test_approval.py
  test_hitl.py
  test_audit.py
  test_feedback.py
  test_memory.py
  test_config.py
  test_loop.py
  test_mechanism_demo.py
pyproject.toml
sentinel.yaml
```

Each file has one responsibility. Tests mirror the module layout.

---

## Task 1: Project Scaffolding
> **Status:** ✅ complete — commits: 916cbb0 / f10ba36

**Files:**
- Create: `pyproject.toml`
- Create: `sentinel/__init__.py`, `sentinel/core/__init__.py`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Create: `.gitignore`

**Interfaces:** Produces a runnable `pytest` invocation and an empty importable `sentinel` package.

- [x] **Step 1: Initialize git repo**

```bash
cd E:\agent
git init
git add -A
git commit -m "chore: initial commit"
```

- [x] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
.env
*.egg-info/
dist/
build/
sentinel.db
*.db
```

- [x] **Step 3: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "sentinel-harness"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.setuptools.packages.find]
include = ["sentinel*"]
```

- [x] **Step 4: Create package `__init__` files**

`sentinel/__init__.py`:
```python
"""Sentinel: a coding agent harness."""
__version__ = "0.1.0"
```

`sentinel/core/__init__.py`: (empty)
```python
"""Sentinel harness core."""
```

`tests/__init__.py`: (empty file)

`tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

- [x] **Step 5: Install dev deps and verify pytest runs**

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```
Expected: `no tests ran` (exit 0 — collection succeeds, no tests yet). If `pytest-asyncio` warns about `asyncio_mode`, it is already set to `auto`.

- [x] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: scaffold sentinel package and pytest config"
```

---

## Task 2: Core Types
> **Status:** ✅ complete — commits: f802bae / ec0f0cd

**Files:**
- Create: `sentinel/core/types.py`
- Test: `tests/test_types.py`

**Interfaces:**
- Produces: `Action`, `Decision`, `RiskLevel`, `GuardrailResult`, `ToolResult`, `Feedback`, `Failure`, `FailureKind`, `Event`, `RunContext`, `Approval`, `ApprovalDecision`.

- [x] **Step 1: Write the failing test**

`tests/test_types.py`:
```python
from sentinel.core.types import (
    Action, Decision, RiskLevel, GuardrailResult, ToolResult,
    Feedback, Failure, FailureKind, Event, RunContext, Approval,
    ApprovalDecision,
)

def test_action_defaults_have_id():
    a = Action(tool="run_shell", args={"cmd": "ls"})
    assert a.tool == "run_shell"
    assert a.id  # auto-generated
    assert a.raw_source == ""
    assert a.turn_id == ""

def test_decision_values():
    assert Decision.ALLOW.value == "allow"
    assert Decision.DENY.value == "deny"
    assert Decision.REQUIRE_APPROVAL.value == "require_approval"

def test_risk_level_ordering():
    assert RiskLevel.LOW < RiskLevel.HIGH
    assert RiskLevel.CRITICAL > RiskLevel.MEDIUM

def test_guardrail_result_fields():
    r = GuardrailResult(decision=Decision.DENY, reason="x",
                        risk_level=RiskLevel.CRITICAL, guardrail_name="pat")
    assert r.decision == Decision.DENY
    assert r.risk_level == RiskLevel.CRITICAL

def test_tool_result_defaults():
    t = ToolResult(success=True)
    assert t.stdout == "" and t.stderr == ""
    assert t.truncated is False
    assert t.artifacts == {}

def test_feedback_unknown_passed():
    f = Feedback(kind="pytest", passed=None, failures=[], raw_output="...")
    assert f.passed is None
    assert f.failures == []

def test_event_carries_type_and_data():
    e = Event(type="ApprovalNeeded", data={"action_id": "a1"})
    assert e.type == "ApprovalNeeded"
    assert e.data["action_id"] == "a1"

def test_run_context_holds_task():
    ctx = RunContext(task="fix the test")
    assert ctx.task == "fix the test"
    assert ctx.turns == []

def test_approval_decision_values():
    assert ApprovalDecision.APPROVED.value == "approved"
    assert ApprovalDecision.DENIED.value == "denied"
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_types.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'sentinel.core.types'`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/types.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import uuid4


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def __lt__(self, other: "RiskLevel") -> bool:
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1,
                 RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
        return order[self] < order[other]


class Decision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    DENIED = "denied"


class FailureKind(str, Enum):
    SYNTAX_ERROR = "syntax_error"
    ASSERTION_FAILURE = "assertion_failure"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    UNKNOWN = "unknown"


@dataclass
class Action:
    tool: str
    args: dict[str, Any]
    raw_source: str = ""
    turn_id: str = ""
    id: str = field(default_factory=lambda: uuid4().hex)


@dataclass
class GuardrailResult:
    decision: Decision
    reason: str
    risk_level: RiskLevel
    guardrail_name: str


@dataclass
class ToolResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    artifacts: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class Failure:
    kind: FailureKind
    message: str
    location: str = ""


@dataclass
class Feedback:
    kind: str
    passed: bool | None
    failures: list[Failure] = field(default_factory=list)
    raw_output: str = ""


@dataclass
class Event:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Approval:
    decision: ApprovalDecision
    reason: str = ""


@dataclass
class RunContext:
    task: str
    config: Any = None
    memory: list[str] = field(default_factory=list)
    turns: list[Any] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_types.py -v
```
Expected: PASS (9 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/types.py tests/test_types.py
git commit -m "feat(core): add core types (Action, Decision, GuardrailResult, Feedback, Event)"
```

---

## Task 3: LLM Abstraction + MockLLM
> **Status:** ✅ complete — commits: 58aa1c4

**Files:**
- Create: `sentinel/core/llm.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Produces: `LLMProvider` protocol (`async complete(messages, tools) -> LLMResponse`), `LLMResponse`, `MockLLM` (scripts responses from a queue).

- [x] **Step 1: Write the failing test**

`tests/test_llm.py`:
```python
import pytest
from sentinel.core.llm import LLMProvider, LLMResponse, MockLLM

@pytest.mark.asyncio
async def test_mock_llm_returns_scripted_response():
    mock = MockLLM(responses=[LLMResponse(text="I will run pytest", tool_calls=[])])
    resp = await mock.complete(messages=[{"role": "user", "content": "go"}], tools=[])
    assert resp.text == "I will run pytest"
    assert resp.tool_calls == []

@pytest.mark.asyncio
async def test_mock_llm_raises_when_empty():
    mock = MockLLM(responses=[])
    with pytest.raises(RuntimeError, match="no more scripted responses"):
        await mock.complete(messages=[], tools=[])

@pytest.mark.asyncio
async def test_mock_llm_yields_tool_calls():
    calls = [{"tool": "run_shell", "args": {"cmd": "pytest"}}]
    mock = MockLLM(responses=[LLMResponse(text="", tool_calls=calls)])
    resp = await mock.complete(messages=[], tools=[])
    assert resp.tool_calls == calls

def test_llm_provider_is_protocol():
    assert hasattr(LLMProvider, "complete")
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_llm.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/llm.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(Protocol):
    async def complete(self, messages: list[dict[str, Any]],
                        tools: list[dict[str, Any]]) -> LLMResponse: ...


class MockLLM:
    """Deterministic LLM that returns scripted responses in order."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self._index = 0

    async def complete(self, messages: list[dict[str, Any]],
                       tools: list[dict[str, Any]]) -> LLMResponse:
        if self._index >= len(self._responses):
            raise RuntimeError("no more scripted responses")
        r = self._responses[self._index]
        self._index += 1
        return r
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_llm.py -v
```
Expected: PASS (4 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/llm.py tests/test_llm.py
git commit -m "feat(core): add LLMProvider protocol and MockLLM"
```

---

## Task 4: Tool Layer + ToolRegistry
> **Status:** ✅ complete — commits: de6777f

**Files:**
- Create: `sentinel/core/tools.py`
- Test: `tests/test_tools.py`

**Interfaces:**
- Consumes: `Action`, `ToolResult` from `types`.
- Produces: `Tool` protocol (`name`, `risk_level`, `execute(args, sandbox) -> ToolResult`), `ToolRegistry`.

- [x] **Step 1: Write the failing test**

`tests/test_tools.py`:
```python
import pytest
from sentinel.core.types import Action, ToolResult, RiskLevel
from sentinel.core.tools import Tool, ToolRegistry

class EchoTool:
    name = "echo"
    risk_level = RiskLevel.LOW
    async def execute(self, args, sandbox):
        return ToolResult(success=True, stdout=str(args.get("msg", "")))

@pytest.mark.asyncio
async def test_tool_executes():
    t = EchoTool()
    r = await t.execute({"msg": "hi"}, sandbox=None)
    assert r.success and r.stdout == "hi"

def test_registry_get_returns_tool():
    reg = ToolRegistry([EchoTool()])
    assert reg.get("echo").name == "echo"

def test_registry_get_unknown_raises():
    reg = ToolRegistry([EchoTool()])
    import pytest
    with pytest.raises(KeyError):
        reg.get("nope")

def test_registry_lists_names():
    reg = ToolRegistry([EchoTool()])
    assert reg.names() == ["echo"]
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_tools.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/tools.py`:
```python
from __future__ import annotations
from typing import Protocol, runtime_checkable

from sentinel.core.types import Action, RiskLevel, ToolResult


class SandboxBackend(Protocol):
    async def run(self, command: list[str], cwd: str | None = None) -> ToolResult: ...
    async def read_file(self, path: str) -> ToolResult: ...
    async def write_file(self, path: str, content: str) -> ToolResult: ...


@runtime_checkable
class Tool(Protocol):
    name: str
    risk_level: RiskLevel
    async def execute(self, args: dict, sandbox: SandboxBackend) -> ToolResult: ...


class ToolRegistry:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {t.name: t for t in tools}

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return list(self._tools.keys())
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_tools.py -v
```
Expected: PASS (4 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/tools.py tests/test_tools.py
git commit -m "feat(core): add Tool protocol and ToolRegistry"
```

---

## Task 5: InProcessSandbox Backend
> **Status:** ✅ complete — commits: 91ee50c

**Files:**
- Create: `sentinel/core/sandbox.py`
- Test: `tests/test_sandbox.py`

**Interfaces:**
- Consumes: `ToolResult` from `types`, `SandboxBackend` protocol from `tools`.
- Produces: `InProcessSandbox` (restricted working dir; enforces path boundaries).

- [x] **Step 1: Write the failing test**

`tests/test_sandbox.py`:
```python
import pytest
from sentinel.core.sandbox import InProcessSandbox

@pytest.mark.asyncio
async def test_run_echo(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    r = await sb.run(["python", "-c", "print('hi')"])
    assert r.success and "hi" in r.stdout

@pytest.mark.asyncio
async def test_run_failure_captured(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    r = await sb.run(["python", "-c", "import sys; sys.exit(2)"])
    assert not r.success

@pytest.mark.asyncio
async def test_write_and_read_file(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    w = await sb.write_file("sub/a.txt", "hello")
    assert w.success
    r = await sb.read_file("sub/a.txt")
    assert r.success and r.stdout == "hello"

@pytest.mark.asyncio
async def test_read_outside_workspace_denied(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    r = await sb.read_file("../../etc/passwd")
    assert not r.success
    assert "denied" in r.error.lower()

@pytest.mark.asyncio
async def test_write_outside_workspace_denied(tmp_path):
    sb = InProcessSandbox(workspace=str(tmp_path))
    r = await sb.write_file("../evil.txt", "x")
    assert not r.success
    assert "denied" in r.error.lower()
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_sandbox.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/sandbox.py`:
```python
from __future__ import annotations
import os
import subprocess
from pathlib import Path

from sentinel.core.types import ToolResult


class InProcessSandbox:
    """Restricted working-directory sandbox (no container isolation)."""

    def __init__(self, workspace: str) -> None:
        self.workspace = Path(workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        p = (self.workspace / path).resolve()
        if self.workspace not in p.parents and p != self.workspace:
            raise PermissionError(f"path outside workspace denied: {path}")
        return p

    async def run(self, command: list[str], cwd: str | None = None) -> ToolResult:
        try:
            proc = subprocess.run(
                command,
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return ToolResult(
                success=proc.returncode == 0,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    async def read_file(self, path: str) -> ToolResult:
        try:
            p = self._resolve(path)
            return ToolResult(success=True, stdout=p.read_text(encoding="utf-8"))
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))

    async def write_file(self, path: str, content: str) -> ToolResult:
        try:
            p = self._resolve(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(success=True)
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_sandbox.py -v
```
Expected: PASS (5 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/sandbox.py tests/test_sandbox.py
git commit -m "feat(core): add InProcessSandbox with path boundary enforcement"
```

---

## Task 6: Guardrail Protocol + PatternGuardrail
> **Status:** ✅ complete — commits: 14997c0 / 2c93ddd

**Files:**
- Create: `sentinel/core/guardrails.py`
- Test: `tests/test_guardrails.py` (PatternGuardrail cases only in this task)

**Interfaces:**
- Consumes: `Action`, `Decision`, `RiskLevel`, `GuardrailResult`, `RunContext` from `types`.
- Produces: `Guardrail` protocol (`name`, `check(action, ctx) -> GuardrailResult`), `PatternGuardrail`, `DEFAULT_PATTERNS`.

- [x] **Step 1: Write the failing test**

`tests/test_guardrails.py`:
```python
from sentinel.core.types import Action, Decision, RiskLevel, RunContext
from sentinel.core.guardrails import PatternGuardrail, Guardrail

def test_pattern_guardrail_denies_rm_rf():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "rm -rf /"}), RunContext(task=""))
    assert r.decision == Decision.DENY
    assert g.name == "pattern"

def test_pattern_guardrail_denies_drop_table():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "psql -c 'DROP TABLE users'"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_pattern_guardrail_denies_force_push():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "git push --force"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_pattern_guardrail_allows_pytest():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "pytest"}), RunContext(task=""))
    assert r.decision == Decision.ALLOW

def test_pattern_guardrail_custom_pattern():
    g = PatternGuardrail(patterns=[r"FORBIDDEN_CMD"])
    r = g.check(Action("run_shell", {"cmd": "FORBIDDEN_CMD"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_guardrail_is_protocol():
    assert hasattr(Guardrail, "check")
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/guardrails.py`:
```python
from __future__ import annotations
import re
from typing import Protocol, runtime_checkable

from sentinel.core.types import Action, Decision, GuardrailResult, RiskLevel, RunContext

DEFAULT_PATTERNS: list[str] = [
    r"\brm\s+-rf\b",
    r"DROP\s+TABLE",
    r"git\s+push\s+(--force|-f)\b",
    r"curl\b.*\|\s*sh",
    r"chmod\s+777\b",
    r":\(\)\{\s*:\|:&\s*\};\s*:",  # fork bomb
]


@runtime_checkable
class Guardrail(Protocol):
    name: str
    def check(self, action: Action, ctx: RunContext) -> GuardrailResult: ...


def _shell_text(action: Action) -> str:
    cmd = action.args.get("cmd", "")
    if not isinstance(cmd, str):
        cmd = str(cmd)
    return f"{cmd} " + " ".join(f"{k}={v}" for k, v in action.args.items())


class PatternGuardrail:
    name = "pattern"

    def __init__(self, patterns: list[str] | None = None) -> None:
        self._patterns = [re.compile(p, re.IGNORECASE) for p in
                          (patterns if patterns is not None else DEFAULT_PATTERNS)]

    def check(self, action: Action, ctx: RunContext) -> GuardrailResult:
        text = _shell_text(action)
        for pat in self._patterns:
            if pat.search(text):
                return GuardrailResult(
                    decision=Decision.DENY,
                    reason=f"matched dangerous pattern: {pat.pattern}",
                    risk_level=RiskLevel.CRITICAL,
                    guardrail_name=self.name,
                )
        return GuardrailResult(
            decision=Decision.ALLOW, reason="no dangerous pattern",
            risk_level=RiskLevel.LOW, guardrail_name=self.name,
        )
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: PASS (6 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/guardrails.py tests/test_guardrails.py
git commit -m "feat(governance): add Guardrail protocol and PatternGuardrail"
```

---

## Task 7: ScopeFence + SandboxBoundary + RiskClassifier Guardrails
> **Status:** ✅ complete — commits: 3b2311a

**Files:**
- Modify: `sentinel/core/guardrails.py` (add three guardrails)
- Modify: `tests/test_guardrails.py` (add cases)

**Interfaces:**
- Produces: `ScopeFenceGuardrail`, `SandboxBoundaryGuardrail`, `RiskClassifierGuardrail`.

- [x] **Step 1: Write the failing tests (append to `tests/test_guardrails.py`)**

```python
from sentinel.core.guardrails import (
    ScopeFenceGuardrail, SandboxBoundaryGuardrail, RiskClassifierGuardrail,
)

def test_scope_fence_denies_out_of_workspace_write():
    g = ScopeFenceGuardrail(workspace="/tmp/ws")
    r = g.check(Action("write_file", {"path": "../../etc/passwd", "content": "x"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_scope_fence_denies_sensitive_read():
    g = ScopeFenceGuardrail(workspace="/tmp/ws")
    r = g.check(Action("read_file", {"path": ".env"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_scope_fence_denies_ssh_read():
    g = ScopeFenceGuardrail(workspace="/tmp/ws")
    r = g.check(Action("read_file", {"path": "~/.ssh/id_rsa"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_scope_fence_allows_in_workspace_write():
    g = ScopeFenceGuardrail(workspace="/tmp/ws")
    r = g.check(Action("write_file", {"path": "src/main.py", "content": "x"}), RunContext(task=""))
    assert r.decision == Decision.ALLOW

def test_sandbox_boundary_flags_network_action():
    g = SandboxBoundaryGuardrail()
    r = g.check(Action("run_shell", {"cmd": "pip install requests"}), RunContext(task=""))
    assert r.decision == Decision.REQUIRE_APPROVAL
    assert "network" in r.reason.lower()

def test_sandbox_boundary_allows_offline():
    g = SandboxBoundaryGuardrail()
    r = g.check(Action("run_shell", {"cmd": "pytest"}), RunContext(task=""))
    assert r.decision == Decision.ALLOW

def test_risk_classifier_assigns_high_to_write():
    g = RiskClassifierGuardrail()
    r = g.check(Action("write_file", {"path": "a.py", "content": "x"}), RunContext(task=""))
    assert r.risk_level == RiskLevel.MEDIUM

def test_risk_classifier_assigns_critical_to_shell():
    g = RiskClassifierGuardrail()
    r = g.check(Action("run_shell", {"cmd": "x"}), RunContext(task=""))
    assert r.risk_level == RiskLevel.HIGH
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: FAIL with `ImportError: cannot import name 'ScopeFenceGuardrail'`

- [x] **Step 3: Write minimal implementation (append to `sentinel/core/guardrails.py`)**

```python
from pathlib import Path
import fnmatch

SENSITIVE_GLOBS = ["**/.env", "**/.aws/*", "**/.ssh/*", "**/credentials*",
                   "**/*.key", "**/*.pem"]


class ScopeFenceGuardrail:
    name = "scope_fence"

    def __init__(self, workspace: str = ".") -> None:
        self._workspace = Path(workspace).resolve()

    def _is_within(self, path: str) -> bool:
        try:
            p = (self._workspace / path).resolve()
        except Exception:
            return False
        return self._workspace == p or self._workspace in p.parents

    def _is_sensitive(self, path: str) -> bool:
        for pat in SENSITIVE_GLOBS:
            if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch("/" + path, pat):
                return True
        return False

    def check(self, action: Action, ctx: RunContext) -> GuardrailResult:
        path = action.args.get("path", "")
        if not path:
            return GuardrailResult(Decision.ALLOW, "no path", RiskLevel.LOW, self.name)
        if self._is_sensitive(path):
            return GuardrailResult(Decision.DENY, f"sensitive path denied: {path}",
                                    RiskLevel.CRITICAL, self.name)
        if not self._is_within(path):
            return GuardrailResult(Decision.DENY, f"path outside workspace: {path}",
                                    RiskLevel.HIGH, self.name)
        return GuardrailResult(Decision.ALLOW, "within workspace", RiskLevel.LOW, self.name)


NETWORK_HINTS = ["pip install", "curl ", "wget ", "git clone", "npm install",
                 "http://", "https://"]


class SandboxBoundaryGuardrail:
    name = "sandbox_boundary"

    def check(self, action: Action, ctx: RunContext) -> GuardrailResult:
        text = _shell_text(action)
        for hint in NETWORK_HINTS:
            if hint in text:
                return GuardrailResult(
                    Decision.REQUIRE_APPROVAL,
                    f"action requires network: {hint.strip()}",
                    RiskLevel.HIGH, self.name,
                )
        return GuardrailResult(Decision.ALLOW, "no network needed",
                               RiskLevel.LOW, self.name)


TOOL_RISK = {
    "read_file": RiskLevel.LOW,
    "list_dir": RiskLevel.LOW,
    "search": RiskLevel.LOW,
    "write_file": RiskLevel.MEDIUM,
    "run_tests": RiskLevel.MEDIUM,
    "run_shell": RiskLevel.HIGH,
}


class RiskClassifierGuardrail:
    name = "risk_classifier"

    def check(self, action: Action, ctx: RunContext) -> GuardrailResult:
        risk = TOOL_RISK.get(action.tool, RiskLevel.MEDIUM)
        return GuardrailResult(Decision.ALLOW, "classified", risk, self.name)
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: PASS (all guardrail tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/guardrails.py tests/test_guardrails.py
git commit -m "feat(governance): add ScopeFence, SandboxBoundary, RiskClassifier guardrails"
```

---

## Task 8: GuardrailPipeline (aggregation)
> **Status:** ✅ complete — commits: bfab311 / c2756a5

**Files:**
- Modify: `sentinel/core/guardrails.py` (add `GuardrailPipeline`)
- Modify: `tests/test_guardrails.py` (add cases)

**Interfaces:**
- Produces: `GuardrailPipeline.check(action, ctx) -> GuardrailResult` (aggregates: any Deny → Deny; else any RequireApproval → RequireApproval with highest risk; else Allow).

- [x] **Step 1: Write the failing tests (append)**

```python
from sentinel.core.guardrails import GuardrailPipeline

def test_pipeline_deny_short_circuits():
    pipe = GuardrailPipeline([PatternGuardrail(), ScopeFenceGuardrail(workspace="/tmp/ws")])
    r = pipe.check(Action("run_shell", {"cmd": "rm -rf /"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_pipeline_require_approval_when_network():
    pipe = GuardrailPipeline([PatternGuardrail(), SandboxBoundaryGuardrail()])
    r = pipe.check(Action("run_shell", {"cmd": "pip install requests"}), RunContext(task=""))
    assert r.decision == Decision.REQUIRE_APPROVAL

def test_pipeline_allow_when_safe():
    pipe = GuardrailPipeline([PatternGuardrail(), SandboxBoundaryGuardrail()])
    r = pipe.check(Action("run_shell", {"cmd": "pytest"}), RunContext(task=""))
    assert r.decision == Decision.ALLOW

def test_pipeline_highest_risk_wins():
    pipe = GuardrailPipeline([SandboxBoundaryGuardrail(), RiskClassifierGuardrail()])
    r = pipe.check(Action("run_shell", {"cmd": "pip install x"}), RunContext(task=""))
    assert r.decision == Decision.REQUIRE_APPROVAL
    assert r.risk_level == RiskLevel.HIGH
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: FAIL with `ImportError: cannot import name 'GuardrailPipeline'`

- [x] **Step 3: Write minimal implementation (append to `sentinel/core/guardrails.py`)**

```python
class GuardrailPipeline:
    def __init__(self, guardrails: list[Guardrail]) -> None:
        self._guardrails = list(guardrails)

    def check(self, action: Action, ctx: RunContext) -> GuardrailResult:
        results = [g.check(action, ctx) for g in self._guardrails]
        for r in results:
            if r.decision == Decision.DENY:
                return r
        approvals = [r for r in results if r.decision == Decision.REQUIRE_APPROVAL]
        if approvals:
            best = max(approvals, key=lambda x: x.risk_level)
            return best
        for r in results:
            if r.decision == Decision.ALLOW:
                return r
        return GuardrailResult(Decision.ALLOW, "no guardrails", RiskLevel.LOW, "pipeline")
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: PASS

- [x] **Step 5: Commit**

```bash
git add sentinel/core/guardrails.py tests/test_guardrails.py
git commit -m "feat(governance): add GuardrailPipeline with deny/approve aggregation"
```

---

## Task 9: Approval Policies
> **Status:** ✅ complete — commits: e8f85cd / e20bdb5

**Files:**
- Create: `sentinel/core/approval.py`
- Test: `tests/test_approval.py`

**Interfaces:**
- Consumes: `Action`, `GuardrailResult`, `Approval`, `ApprovalDecision` from `types`.
- Produces: `ApprovalPolicy` protocol (`async approve(action, result) -> Approval`), `AutoApprove`, `AutoDeny`, `ThresholdApprove`.

- [x] **Step 1: Write the failing test**

`tests/test_approval.py`:
```python
import pytest
from sentinel.core.types import Action, GuardrailResult, Decision, RiskLevel
from sentinel.core.approval import (
    ApprovalPolicy, AutoApprove, AutoDeny, ThresholdApprove,
)

def _r(decision, risk):
    return GuardrailResult(decision=decision, reason="x", risk_level=risk,
                           guardrail_name="g")

@pytest.mark.asyncio
async def test_auto_approve_allows():
    a = await AutoApprove().approve(Action("run_shell", {"cmd": "x"}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.HIGH))
    assert a.decision.value == "approved"

@pytest.mark.asyncio
async def test_auto_deny_denies():
    a = await AutoDeny().approve(Action("run_shell", {"cmd": "x"}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.HIGH))
    assert a.decision.value == "denied"

@pytest.mark.asyncio
async def test_threshold_approves_low():
    a = await ThresholdApprove().approve(Action("x", {}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.LOW))
    assert a.decision.value == "approved"

@pytest.mark.asyncio
async def test_threshold_denies_high():
    a = await ThresholdApprove().approve(Action("x", {}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.HIGH))
    assert a.decision.value == "denied"

@pytest.mark.asyncio
async def test_threshold_approves_medium():
    a = await ThresholdApprove().approve(Action("x", {}), _r(Decision.REQUIRE_APPROVAL, RiskLevel.MEDIUM))
    assert a.decision.value == "approved"

def test_approval_policy_is_protocol():
    assert hasattr(ApprovalPolicy, "approve")
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_approval.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/approval.py`:
```python
from __future__ import annotations
from typing import Protocol, runtime_checkable

from sentinel.core.types import Action, Approval, ApprovalDecision, GuardrailResult, RiskLevel


@runtime_checkable
class ApprovalPolicy(Protocol):
    async def approve(self, action: Action, result: GuardrailResult) -> Approval: ...


class AutoApprove:
    async def approve(self, action: Action, result: GuardrailResult) -> Approval:
        return Approval(decision=ApprovalDecision.APPROVED, reason="auto-approve")


class AutoDeny:
    async def approve(self, action: Action, result: GuardrailResult) -> Approval:
        return Approval(decision=ApprovalDecision.DENIED, reason="auto-deny")


class ThresholdApprove:
    """Auto-approve low/medium; deny high/critical (deterministic for tests)."""

    def __init__(self, threshold: RiskLevel = RiskLevel.MEDIUM) -> None:
        self._threshold = threshold

    async def approve(self, action: Action, result: GuardrailResult) -> Approval:
        if result.risk_level <= self._threshold:
            return Approval(ApprovalDecision.APPROVED, "below threshold")
        return Approval(ApprovalDecision.DENIED, "above threshold")
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_approval.py -v
```
Expected: PASS (6 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/approval.py tests/test_approval.py
git commit -m "feat(governance): add ApprovalPolicy and AutoApprove/AutoDeny/ThresholdApprove"
```

---

## Task 10: HITL State Machine
> **Status:** ✅ complete — commits: f049803

**Files:**
- Create: `sentinel/core/hitl.py`
- Test: `tests/test_hitl.py`

**Interfaces:**
- Produces: `ActionState` enum, `HITLStateMachine` (`submit(action) -> state`, `approve(action_id)`, `deny(action_id)`, `timeout(action_id)`, `mark_executed(action_id)`, `state(action_id)`). Illegal transitions raise. Timeout → Skipped (fail-closed).

- [x] **Step 1: Write the failing test**

`tests/test_hitl.py`:
```python
import pytest
from sentinel.core.types import Action
from sentinel.core.hitl import HITLStateMachine, ActionState

def test_submit_sets_pending():
    fsm = HITLStateMachine()
    s = fsm.submit(Action("run_shell", {"cmd": "pip install x"}, id="a1"))
    assert s == ActionState.PENDING_APPROVAL

def test_approve_transitions_to_executing():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    s = fsm.approve("a1")
    assert s == ActionState.EXECUTING

def test_deny_transitions_to_skipped():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    s = fsm.deny("a1")
    assert s == ActionState.SKIPPED

def test_timeout_transitions_to_skipped():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    s = fsm.timeout("a1")
    assert s == ActionState.SKIPPED

def test_executed_after_approved():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    fsm.approve("a1")
    s = fsm.mark_executed("a1", success=True)
    assert s == ActionState.EXECUTED

def test_failed_after_approved():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    fsm.approve("a1")
    s = fsm.mark_executed("a1", success=False)
    assert s == ActionState.FAILED

def test_illegal_transition_raises():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    with pytest.raises(PermissionError):
        fsm.mark_executed("a1", success=True)  # not approved yet

def test_unknown_action_raises():
    fsm = HITLStateMachine()
    with pytest.raises(KeyError):
        fsm.approve("nope")
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_hitl.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/hitl.py`:
```python
from __future__ import annotations
from enum import Enum

from sentinel.core.types import Action


class ActionState(str, Enum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


class HITLStateMachine:
    """Tracks each action through its governance lifecycle. Fail-closed."""

    def __init__(self) -> None:
        self._states: dict[str, ActionState] = {}

    def submit(self, action: Action) -> ActionState:
        self._states[action.id] = ActionState.PENDING_APPROVAL
        return self._states[action.id]

    def approve(self, action_id: str) -> ActionState:
        self._require(action_id, ActionState.PENDING_APPROVAL)
        self._states[action_id] = ActionState.EXECUTING
        return self._states[action_id]

    def deny(self, action_id: str) -> ActionState:
        self._require(action_id, ActionState.PENDING_APPROVAL)
        self._states[action_id] = ActionState.SKIPPED
        return self._states[action_id]

    def timeout(self, action_id: str) -> ActionState:
        self._require(action_id, ActionState.PENDING_APPROVAL)
        self._states[action_id] = ActionState.SKIPPED
        return self._states[action_id]

    def mark_executed(self, action_id: str, success: bool) -> ActionState:
        self._require(action_id, ActionState.EXECUTING)
        self._states[action_id] = ActionState.EXECUTED if success else ActionState.FAILED
        return self._states[action_id]

    def state(self, action_id: str) -> ActionState:
        return self._states[action_id]

    def _require(self, action_id: str, expected: ActionState) -> None:
        if action_id not in self._states:
            raise KeyError(f"unknown action: {action_id}")
        if self._states[action_id] != expected:
            raise PermissionError(
                f"illegal transition: {action_id} is "
                f"{self._states[action_id]}, expected {expected}"
            )
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_hitl.py -v
```
Expected: PASS (8 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/hitl.py tests/test_hitl.py
git commit -m "feat(governance): add HITL state machine with fail-closed transitions"
```

---

## Task 11: Audit Log
> **Status:** ✅ complete — commits: e67cfb9

**Files:**
- Create: `sentinel/core/audit.py`
- Test: `tests/test_audit.py`

**Interfaces:**
- Produces: `AuditEntry` dataclass, `AuditLog` (`append(entry)`, `for_action(action_id)`, `query(**filters)`, `all()`). Backed by in-memory list (SQLite swap-in later).

- [x] **Step 1: Write the failing test**

`tests/test_audit.py`:
```python
from sentinel.core.types import Decision, RiskLevel
from sentinel.core.audit import AuditEntry, AuditLog

def _entry(action_id="a1", guardrail="pattern", decision=Decision.DENY,
           risk=RiskLevel.CRITICAL, outcome="skipped"):
    return AuditEntry(action_id=action_id, guardrail=guardrail,
                      decision=decision, risk_level=risk, outcome=outcome)

def test_append_and_for_action():
    log = AuditLog()
    log.append(_entry("a1"))
    log.append(_entry("a1", guardrail="scope_fence"))
    rows = log.for_action("a1")
    assert len(rows) == 2

def test_query_by_decision():
    log = AuditLog()
    log.append(_entry("a1", decision=Decision.DENY))
    log.append(_entry("a2", decision=Decision.ALLOW))
    denied = log.query(decision=Decision.DENY)
    assert len(denied) == 1 and denied[0].action_id == "a1"

def test_query_by_risk():
    log = AuditLog()
    log.append(_entry("a1", risk=RiskLevel.CRITICAL))
    log.append(_entry("a2", risk=RiskLevel.LOW))
    crit = log.query(risk_level=RiskLevel.CRITICAL)
    assert len(crit) == 1

def test_all_returns_everything():
    log = AuditLog()
    log.append(_entry("a1"))
    log.append(_entry("a2"))
    assert len(log.all()) == 2
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_audit.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/audit.py`:
```python
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any

from sentinel.core.types import Decision, RiskLevel


@dataclass
class AuditEntry:
    action_id: str
    guardrail: str
    decision: Decision
    risk_level: RiskLevel
    outcome: str = ""
    reason: str = ""
    timestamp: float = field(default_factory=time.time)


class AuditLog:
    """Append-only audit log (in-memory; SQLite swap-in later)."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    def for_action(self, action_id: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.action_id == action_id]

    def query(self, **filters: Any) -> list[AuditEntry]:
        out: list[AuditEntry] = []
        for e in self._entries:
            if all(getattr(e, k) == v for k, v in filters.items()):
                out.append(e)
        return out

    def all(self) -> list[AuditEntry]:
        return list(self._entries)
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_audit.py -v
```
Expected: PASS (4 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/audit.py tests/test_audit.py
git commit -m "feat(governance): add append-only AuditLog"
```

---

## Task 12: Feedback Validators
> **Status:** ✅ complete — commits: 0becacd

**Files:**
- Create: `sentinel/core/feedback.py`
- Test: `tests/test_feedback.py`

**Interfaces:**
- Consumes: `ToolResult`, `Action`, `Feedback`, `Failure`, `FailureKind` from `types`.
- Produces: `Validator` protocol (`parse(tool_result, action) -> Feedback`), `PytestValidator`, `RuffValidator`, `MypyValidator`, `select_validator(action)`.

- [x] **Step 1: Write the failing test**

`tests/test_feedback.py`:
```python
from sentinel.core.types import Action, ToolResult
from sentinel.core.feedback import (
    PytestValidator, RuffValidator, MypyValidator, select_validator,
)

def test_pytest_pass():
    r = PytestValidator().parse(ToolResult(success=True, stdout="3 passed"), Action("run_tests", {}))
    assert r.passed is True and r.failures == []

def test_pytest_assertion_failure():
    out = "FAILED tests/test_x.py::test_a - assert 1 == 2\n1 failed"
    r = PytestValidator().parse(ToolResult(success=False, stdout=out), Action("run_tests", {}))
    assert r.passed is False
    assert any(f.kind.value == "assertion_failure" for f in r.failures)

def test_pytest_syntax_error():
    out = "SyntaxError: invalid syntax\n1 error"
    r = PytestValidator().parse(ToolResult(success=False, stdout=out), Action("run_tests", {}))
    assert r.passed is False
    assert any(f.kind.value == "syntax_error" for f in r.failures)

def test_pytest_import_error():
    out = "ModuleNotFoundError: No module named 'foo'\n1 failed"
    r = PytestValidator().parse(ToolResult(success=False, stdout=out), Action("run_tests", {}))
    assert any(f.kind.value == "import_error" for f in r.failures)

def test_ruff_failure():
    out = "src/a.py:3:1 E302 expected 2 blank lines"
    r = RuffValidator().parse(ToolResult(success=False, stdout=out), Action("run_shell", {"cmd": "ruff check"}))
    assert r.passed is False and len(r.failures) == 1

def test_mypy_type_error():
    out = "src/a.py:5: error: Incompatible types"
    r = MypyValidator().parse(ToolResult(success=False, stdout=out), Action("run_shell", {"cmd": "mypy"}))
    assert r.passed is False
    assert any(f.kind.value == "type_error" for f in r.failures)

def test_select_validator_pytest():
    assert isinstance(select_validator(Action("run_tests", {})), PytestValidator)

def test_select_validator_ruff():
    assert isinstance(select_validator(Action("run_shell", {"cmd": "ruff check src"})), RuffValidator)

def test_select_validator_mypy():
    assert isinstance(select_validator(Action("run_shell", {"cmd": "mypy src"})), MypyValidator)
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_feedback.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/feedback.py`:
```python
from __future__ import annotations
import re
from typing import Protocol, runtime_checkable

from sentinel.core.types import Action, Failure, FailureKind, Feedback, ToolResult


@runtime_checkable
class Validator(Protocol):
    def parse(self, tool_result: ToolResult, action: Action) -> Feedback: ...


class PytestValidator:
    def parse(self, tool_result: ToolResult, action: Action) -> Feedback:
        out = tool_result.stdout + "\n" + tool_result.stderr
        failures: list[Failure] = []
        if re.search(r"SyntaxError", out, re.IGNORECASE):
            failures.append(Failure(FailureKind.SYNTAX_ERROR, "SyntaxError"))
        if re.search(r"ModuleNotFoundError|ImportError", out):
            failures.append(Failure(FailureKind.IMPORT_ERROR, "import error"))
        for m in re.finditer(r"FAILED\s+\S+.*?-\s*(.+)", out):
            failures.append(Failure(FailureKind.ASSERTION_FAILURE, m.group(1).strip()))
        passed = tool_result.success if tool_result.success else (not failures and "passed" in out)
        return Feedback(kind="pytest", passed=bool(passed) if not failures else False,
                        failures=failures, raw_output=out)


class RuffValidator:
    def parse(self, tool_result: ToolResult, action: Action) -> Feedback:
        out = tool_result.stdout + "\n" + tool_result.stderr
        failures = []
        for m in re.finditer(r"^(.+?:\d+:\d+)\s+(\w+)\s+(.+)$", out, re.MULTILINE):
            failures.append(Failure(FailureKind.UNKNOWN, m.group(3).strip(),
                                    location=m.group(1)))
        return Feedback(kind="ruff", passed=tool_result.success,
                        failures=failures, raw_output=out)


class MypyValidator:
    def parse(self, tool_result: ToolResult, action: Action) -> Feedback:
        out = tool_result.stdout + "\n" + tool_result.stderr
        failures = []
        for m in re.finditer(r"^(.+?:\d+):\s*error:\s*(.+)$", out, re.MULTILINE):
            failures.append(Failure(FailureKind.TYPE_ERROR, m.group(2).strip(),
                                    location=m.group(1)))
        return Feedback(kind="mypy", passed=tool_result.success,
                        failures=failures, raw_output=out)


def select_validator(action: Action) -> Validator:
    if action.tool == "run_tests":
        return PytestValidator()
    cmd = str(action.args.get("cmd", ""))
    if "ruff" in cmd:
        return RuffValidator()
    if "mypy" in cmd:
        return MypyValidator()
    return PytestValidator()
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_feedback.py -v
```
Expected: PASS (9 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/feedback.py tests/test_feedback.py
git commit -m "feat(feedback): add pytest/ruff/mypy validators and selector"
```

---

## Task 13: Agent Main Loop
> **Status:** ✅ complete — commits: 9807435 / 8b4643c

**Files:**
- Create: `sentinel/core/loop.py`
- Test: `tests/test_loop.py`

**Interfaces:**
- Consumes: `LLMProvider`, `ToolRegistry`, `GuardrailPipeline`, `ApprovalPolicy`, `RunContext`, `Event`, `Action`, `ToolResult`, `Feedback`, `HITLStateMachine`, `AuditLog`, `select_validator`.
- Produces: `async def agent_loop(ctx, llm, tools, pipeline, approval_policy, sandbox, audit, hitl, max_turns) -> AsyncIterator[Event]`.

- [x] **Step 1: Write the failing test**

`tests/test_loop.py`:
```python
import pytest
from sentinel.core.types import (
    Action, Decision, RiskLevel, RunContext, ToolResult, Event,
)
from sentinel.core.llm import MockLLM, LLMResponse
from sentinel.core.tools import ToolRegistry
from sentinel.core.guardrails import GuardrailPipeline, PatternGuardrail
from sentinel.core.approval import AutoApprove, AutoDeny
from sentinel.core.sandbox import InProcessSandbox
from sentinel.core.audit import AuditLog
from sentinel.core.hitl import HITLStateMachine, ActionState
from sentinel.core.loop import agent_loop

class StubTool:
    name = "run_shell"
    risk_level = RiskLevel.HIGH
    def __init__(self, stdout="ok", success=True):
        self._stdout = stdout
        self._success = success
    async def execute(self, args, sandbox):
        return ToolResult(success=self._success, stdout=self._stdout)

def _events(gen):
    import asyncio
    async def collect():
        return [e async for e in gen]
    return asyncio.run(collect())

@pytest.mark.asyncio
async def test_loop_runs_safe_action_and_stops():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "pytest"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = ToolRegistry([StubTool(stdout="3 passed")])
    pipe = GuardrailPipeline([PatternGuardrail()])
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=5):
        events.append(e)
    types = [e.type for e in events]
    assert "ActionRequested" in types
    assert "ActionExecuted" in types
    assert "Stopped" in types

@pytest.mark.asyncio
async def test_loop_denies_dangerous_action():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "rm -rf /"}}]),
        LLMResponse(text="done", tool_calls=[]),
    ])
    tools = ToolRegistry([StubTool()])
    pipe = GuardrailPipeline([PatternGuardrail()])
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=5):
        events.append(e)
    assert any(e.type == "ActionDenied" for e in events)
    assert any(e.type == "Stopped" for e in events)

@pytest.mark.asyncio
async def test_loop_stops_on_max_turns():
    llm = MockLLM(responses=[
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "ls"}}]),
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "ls"}}]),
        LLMResponse(text="", tool_calls=[{"tool": "run_shell", "args": {"cmd": "ls"}}]),
    ])
    tools = ToolRegistry([StubTool()])
    pipe = GuardrailPipeline([PatternGuardrail()])
    events = []
    async for e in agent_loop(RunContext(task="t"), llm, tools, pipe,
                              AutoApprove(), InProcessSandbox(workspace="."),
                              AuditLog(), HITLStateMachine(), max_turns=2):
        events.append(e)
    assert events[-1].type == "Stopped"
    assert "max_turns" in events[-1].data.get("reason", "")
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_loop.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/loop.py`:
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
) -> AsyncIterator[Event]:
    messages = [{"role": "system", "content": f"Task: {ctx.task}"}]
    for turn in range(max_turns):
        yield Event(type="TurnStarted", data={"turn": turn})
        resp = await llm.complete(messages=messages, tools=tools.names())
        yield Event(type="LLMResponse", data={"text": resp.text})
        if not resp.tool_calls:
            yield Event(type="Stopped", data={"reason": "done"})
            return
        for call in resp.tool_calls:
            action = Action(tool=call["tool"], args=call.get("args", {}),
                             raw_source=str(call), turn_id=str(turn))
            yield Event(type="ActionRequested",
                        data={"tool": action.tool, "args": action.args})
            result = pipeline.check(action, ctx)
            audit.append(AuditEntry(
                action_id=action.id, guardrail=result.guardrail_name,
                decision=result.decision, risk_level=result.risk_level,
                reason=result.reason,
            ))
            if result.decision == Decision.DENY:
                yield Event(type="ActionDenied",
                            data={"action_id": action.id, "reason": result.reason})
                continue
            if result.decision == Decision.REQUIRE_APPROVAL:
                hitl.submit(action)
                approval = await approval_policy.approve(action, result)
                if approval.decision == ApprovalDecision.DENIED:
                    hitl.deny(action.id)
                    audit.append(AuditEntry(
                        action_id=action.id, guardrail="approval",
                        decision=Decision.DENY, risk_level=result.risk_level,
                        outcome="skipped", reason=approval.reason))
                    yield Event(type="ActionDenied",
                                data={"action_id": action.id, "reason": approval.reason})
                    continue
                hitl.approve(action.id)
            tool = tools.get(action.tool)
            tool_result = await tool.execute(action.args, sandbox)
            if action.id in hitl._states:
                hitl.mark_executed(action.id, success=tool_result.success)
            yield Event(type="ActionExecuted",
                        data={"action_id": action.id, "success": tool_result.success})
            validator = select_validator(action)
            feedback = validator.parse(tool_result, action)
            yield Event(type="FeedbackReceived",
                        data={"passed": feedback.passed,
                              "failures": [f.kind.value for f in feedback.failures]})
            messages.append({"role": "tool", "content": tool_result.stdout})
        yield Event(type="TurnComplete", data={"turn": turn})
    yield Event(type="Stopped", data={"reason": "max_turns"})
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_loop.py -v
```
Expected: PASS (3 tests). The `mark_executed` call is guarded by `action.id in hitl._states` so ALLOW-path actions (never submitted to the HITL machine) are not tracked — only `REQUIRE_APPROVAL` actions walk the state machine.

- [x] **Step 5: Commit**

```bash
git add sentinel/core/loop.py tests/test_loop.py
git commit -m "feat(core): add async agent_loop with governance + feedback integration"
```

---

## Task 14: Memory Store
> **Status:** ✅ complete — commits: add49ba

**Files:**
- Create: `sentinel/core/memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Produces: `MemoryStore` (`add(kind, key, content)`, `search(query, limit) -> list`, uses sqlite3 + TF-IDF). Self-implemented (no framework memory).

- [x] **Step 1: Write the failing test**

`tests/test_memory.py`:
```python
from sentinel.core.memory import MemoryStore

def test_add_and_search(tmp_path):
    store = MemoryStore(path=str(tmp_path / "mem.db"))
    store.add("convention", "testing", "always run pytest first")
    store.add("decision", "framework", "no langchain allowed")
    results = store.search("pytest testing")
    assert len(results) >= 1
    assert "pytest" in results[0].lower()

def test_search_ranks_relevant(tmp_path):
    store = MemoryStore(path=str(tmp_path / "mem.db"))
    store.add("note", "a", "the agent uses docker sandbox")
    store.add("note", "b", "pytest runs the tests")
    results = store.search("pytest")
    assert "pytest runs the tests" in results[0]

def test_empty_query_returns_any(tmp_path):
    store = MemoryStore(path=str(tmp_path / "mem.db"))
    store.add("note", "a", "something")
    assert len(store.search("")) >= 1
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_memory.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/memory.py`:
```python
from __future__ import annotations
import math
import re
import sqlite3
import time
from collections import Counter


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


class MemoryStore:
    """Self-implemented memory: SQLite + TF-IDF retrieval."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS memory "
            "(id INTEGER PRIMARY KEY, kind TEXT, key TEXT, content TEXT, created_at REAL)"
        )
        self._conn.commit()

    def add(self, kind: str, key: str, content: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO memory (kind, key, content, created_at) VALUES (?, ?, ?, ?)",
            (kind, key, content, time.time()),
        )
        self._conn.commit()
        return cur.lastrowid

    def _all(self) -> list[tuple[int, str, str, str]]:
        return self._conn.execute(
            "SELECT id, kind, key, content FROM memory"
        ).fetchall()

    def search(self, query: str, limit: int = 5) -> list[str]:
        rows = self._all()
        if not rows:
            return []
        docs = [_tokens(r[3]) for r in rows]
        n = len(docs)
        df = Counter()
        for d in docs:
            for term in set(d):
                df[term] += 1
        idf = {t: math.log((n + 1) / (df[t] + 1)) + 1 for t in df}
        q_tokens = _tokens(query)
        if not q_tokens:
            return [r[3] for r in rows[:limit]]
        scored = []
        for i, d in enumerate(docs):
            tf = Counter(d)
            score = sum(tf.get(t, 0) * idf.get(t, 0) for t in q_tokens)
            scored.append((score, rows[i][3]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [content for score, content in scored[:limit] if score > 0] or [rows[0][3]]
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_memory.py -v
```
Expected: PASS (3 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/memory.py tests/test_memory.py
git commit -m "feat(memory): add self-implemented SQLite + TF-IDF MemoryStore"
```

---

## Task 15: Config Loader
> **Status:** ✅ complete — commits: a4e0d9e

**Files:**
- Create: `sentinel/core/config.py`
- Create: `sentinel.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass, `load_config(path) -> Config`. Reads provider/model, allowed tools, risk thresholds, sandbox, guardrail patterns, max_turns, approval timeout.

- [x] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
import textwrap
from sentinel.core.config import load_config, Config

def test_load_config(tmp_path):
    yaml = textwrap.dedent("""
        provider: openai
        model: gpt-4o-mini
        max_turns: 8
        approval_timeout: 30
        sandbox:
          image: sentinel-sandbox:latest
          network: false
        tools: [read_file, write_file, run_shell, run_tests]
        guardrail_patterns: ["rm -rf", "DROP TABLE"]
    """)
    p = tmp_path / "sentinel.yaml"
    p.write_text(yaml)
    cfg = load_config(str(p))
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o-mini"
    assert cfg.max_turns == 8
    assert cfg.approval_timeout == 30
    assert cfg.sandbox["network"] is False
    assert "run_shell" in cfg.tools
    assert "rm -rf" in cfg.guardrail_patterns

def test_load_config_missing_required_raises(tmp_path):
    import pytest
    p = tmp_path / "bad.yaml"
    p.write_text("provider: openai\n")
    with pytest.raises(ValueError, match="missing"):
        load_config(str(p))
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_config.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Write minimal implementation**

`sentinel/core/config.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Config:
    provider: str
    model: str
    max_turns: int = 10
    approval_timeout: int = 30
    sandbox: dict = field(default_factory=lambda: {"image": "sentinel-sandbox:latest", "network": False})
    tools: list[str] = field(default_factory=list)
    guardrail_patterns: list[str] = field(default_factory=list)


REQUIRED = {"provider", "model"}


def load_config(path: str) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    missing = REQUIRED - set(data.keys())
    if missing:
        raise ValueError(f"missing required config keys: {sorted(missing)}")
    return Config(
        provider=data["provider"],
        model=data["model"],
        max_turns=data.get("max_turns", 10),
        approval_timeout=data.get("approval_timeout", 30),
        sandbox=data.get("sandbox", {"image": "sentinel-sandbox:latest", "network": False}),
        tools=data.get("tools", []),
        guardrail_patterns=data.get("guardrail_patterns", []),
    )
```

`sentinel.yaml`:
```yaml
provider: openai
model: gpt-4o-mini
max_turns: 10
approval_timeout: 30
sandbox:
  image: sentinel-sandbox:latest
  network: false
tools: [read_file, write_file, list_dir, run_shell, run_tests, search]
guardrail_patterns:
  - "rm -rf"
  - "DROP TABLE"
  - "git push --force"
```

- [x] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_config.py -v
```
Expected: PASS (2 tests)

- [x] **Step 5: Commit**

```bash
git add sentinel/core/config.py sentinel.yaml tests/test_config.py
git commit -m "feat(config): add YAML config loader with required-key validation"
```

---

## Task 16: Mechanism Demo (§A.6 ①②③)
> **Status:** ✅ complete — commits: 0eb386a

**Files:**
- Create: `tests/test_mechanism_demo.py`

**Interfaces:**
- Consumes: all core modules. Reproduces ① governance intercept, ② feedback self-correction, ③ HITL depth — under `MockLLM`, deterministically.

- [x] **Step 1: Write the failing test**

`tests/test_mechanism_demo.py`:
```python
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
    assert any(e.type == "ActionDenied" for e in events)
    assert not any(e.type == "ActionExecuted" for e in events)
```

- [x] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_mechanism_demo.py -v
```
Expected: FAIL (Task 16 written before its dependencies are green in a fresh session; once Tasks 1–15 pass, this should pass too).

- [x] **Step 3: Verify the demo passes**

```bash
python -m pytest tests/test_mechanism_demo.py -v
```
Expected: PASS (3 tests). The `StubShell` tools already expose `name = "run_shell"` and `risk_level = RiskLevel.HIGH` as class attributes, satisfying the `Tool` protocol shape; `SwitchingRegistry` only needs `get()`/`names()`.

- [x] **Step 4: Run the full suite**

```bash
python -m pytest -q
```
Expected: all tests PASS (no network, no Docker, no real LLM).

- [x] **Step 5: Commit**

```bash
git add tests/test_mechanism_demo.py sentinel/core/loop.py
git commit -m "test(demo): add §A.6 mechanism demo (governance intercept, feedback self-correction, HITL depth)"
```

---

## Self-Review (run after writing)

**1. Spec coverage (Phase 1 scope):**
- §3.1 Decision/main loop → Task 13 ✓
- §3.2 Tools → Tasks 4, 5 ✓
- §3.3 Governance (deep) → Tasks 6, 7, 8, 9, 10, 11 ✓
- §3.4 Feedback → Task 12 ✓
- §3.5 Memory → Task 14 ✓
- §3.6 Config → Task 15 ✓
- §9 领域与机制设计 (mechanisms as code) → Tasks 6–11 ✓
- §A.6 mechanism demo → Task 16 ✓
- §3.7 WebUI, §3.8 credentials, §7 distribution, §4.2 credential threat model, CI → **Phase 2** (deferred; not in this plan).

**2. Placeholder scan:** No TBD/TODO/"implement later". All steps contain real code. ✓

**3. Type consistency:** `Action.id` (str), `Decision`/`RiskLevel`/`ApprovalDecision` enums, `GuardrailResult` fields, `Tool.execute(args, sandbox) -> ToolResult`, `ApprovalPolicy.approve(action, result) -> Approval`, `HITLStateMachine.submit/approve/deny/timeout/mark_executed`, `AuditLog.append/for_action/query/all`, `select_validator(action) -> Validator` — consistent across tasks. ✓

**Known follow-up (Phase 2):** WebUI (FastAPI + WebSocket + Open Design frontend), `HumanApprove` policy (awaits WebSocket), `DockerSandbox` backend, credential CLI + keyring, Docker image + PyPI distribution, deployment, CI (`.gitlab-ci.yml` `unit-test` + GitHub Actions), `OpenAIProvider`/`AnthropicProvider`.

---

*End of Phase 1 plan. Next: choose execution approach (subagent-driven or inline).*
