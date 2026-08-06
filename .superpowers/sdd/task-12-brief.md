## Task 12: Feedback Validators

**Files:**
- Create: `sentinel/core/feedback.py`
- Test: `tests/test_feedback.py`

**Interfaces:**
- Consumes: `ToolResult`, `Action`, `Feedback`, `Failure`, `FailureKind` from `types`.
- Produces: `Validator` protocol (`parse(tool_result, action) -> Feedback`), `PytestValidator`, `RuffValidator`, `MypyValidator`, `select_validator(action)`.

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_feedback.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

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

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_feedback.py -v
```
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/feedback.py tests/test_feedback.py
git commit -m "feat(feedback): add pytest/ruff/mypy validators and selector"
```

---

