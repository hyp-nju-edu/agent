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
