## Task 11: Audit Log

**Files:**
- Create: `sentinel/core/audit.py`
- Test: `tests/test_audit.py`

**Interfaces:**
- Produces: `AuditEntry` dataclass, `AuditLog` (`append(entry)`, `for_action(action_id)`, `query(**filters)`, `all()`). Backed by in-memory list (SQLite swap-in later).

- [ ] **Step 1: Write the failing test**

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

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_audit.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

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

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_audit.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/audit.py tests/test_audit.py
git commit -m "feat(governance): add append-only AuditLog"
```

---

