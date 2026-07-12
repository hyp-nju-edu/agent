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
