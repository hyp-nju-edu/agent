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
