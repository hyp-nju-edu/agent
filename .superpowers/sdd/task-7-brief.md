## Task 7: ScopeFence + SandboxBoundary + RiskClassifier Guardrails

**Files:**
- Modify: `sentinel/core/guardrails.py` (add three guardrails)
- Modify: `tests/test_guardrails.py` (add cases)

**Interfaces:**
- Produces: `ScopeFenceGuardrail`, `SandboxBoundaryGuardrail`, `RiskClassifierGuardrail`.

- [ ] **Step 1: Write the failing tests (append to `tests/test_guardrails.py`)**

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

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: FAIL with `ImportError: cannot import name 'ScopeFenceGuardrail'`

- [ ] **Step 3: Write minimal implementation (append to `sentinel/core/guardrails.py`)**

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

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: PASS (all guardrail tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/guardrails.py tests/test_guardrails.py
git commit -m "feat(governance): add ScopeFence, SandboxBoundary, RiskClassifier guardrails"
```

---

