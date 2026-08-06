## Task 6: Guardrail Protocol + PatternGuardrail

**Files:**
- Create: `sentinel/core/guardrails.py`
- Test: `tests/test_guardrails.py` (PatternGuardrail cases only in this task)

**Interfaces:**
- Consumes: `Action`, `Decision`, `RiskLevel`, `GuardrailResult`, `RunContext` from `types`.
- Produces: `Guardrail` protocol (`name`, `check(action, ctx) -> GuardrailResult`), `PatternGuardrail`, `DEFAULT_PATTERNS`.

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

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

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_guardrails.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/guardrails.py tests/test_guardrails.py
git commit -m "feat(governance): add Guardrail protocol and PatternGuardrail"
```

---

