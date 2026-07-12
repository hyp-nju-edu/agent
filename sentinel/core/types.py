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

    def __gt__(self, other: "RiskLevel") -> bool:
        order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1,
                 RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}
        return order[self] > order[other]


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
