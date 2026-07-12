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
