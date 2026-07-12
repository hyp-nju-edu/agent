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
