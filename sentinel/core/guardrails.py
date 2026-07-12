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
