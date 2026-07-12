from __future__ import annotations
import re
from pathlib import Path
import fnmatch
from typing import Protocol, runtime_checkable

from sentinel.core.types import Action, Decision, GuardrailResult, RiskLevel, RunContext

DEFAULT_PATTERNS: list[str] = [
    r"\brm\b(?=.*(?:--recursive|\s-[a-z]*r))(?=.*(?:--force|\s-[a-z]*f))",
    r"DROP\s+TABLE",
    r"git\s+push\s+(--force|-f)\b",
    r"curl\b.*\|\s*sh",
    r"\bchmod\b.*\b0*777\b",
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


class GuardrailPipeline:
    def __init__(self, guardrails: list[Guardrail]) -> None:
        self._guardrails = list(guardrails)

    def check(self, action: Action, ctx: RunContext) -> GuardrailResult:
        if not self._guardrails:
            return GuardrailResult(
                Decision.DENY, "no guardrails configured",
                RiskLevel.CRITICAL, "pipeline",
            )
        results: list[GuardrailResult] = []
        for g in self._guardrails:
            try:
                results.append(g.check(action, ctx))
            except Exception as e:
                return GuardrailResult(
                    Decision.DENY, f"guardrail error: {e}",
                    RiskLevel.CRITICAL, g.name,
                )
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
        return GuardrailResult(Decision.DENY, "no guardrail allowed",
                               RiskLevel.CRITICAL, "pipeline")
