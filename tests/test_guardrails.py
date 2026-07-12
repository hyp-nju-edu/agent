from sentinel.core.types import Action, Decision, RiskLevel, RunContext
from sentinel.core.guardrails import PatternGuardrail, Guardrail
from sentinel.core.guardrails import (
    ScopeFenceGuardrail, SandboxBoundaryGuardrail, RiskClassifierGuardrail,
)

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

def test_pattern_guardrail_denies_rm_fr_reordered():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "rm -fr /"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_pattern_guardrail_denies_rm_r_f_split():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "rm -r -f /"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_pattern_guardrail_denies_rm_long_form():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "rm --recursive --force /"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_pattern_guardrail_denies_chmod_0777():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "chmod 0777 file"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_pattern_guardrail_denies_chmod_R_777():
    g = PatternGuardrail()
    r = g.check(Action("run_shell", {"cmd": "chmod -R 777 file"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_guardrail_is_protocol():
    assert hasattr(Guardrail, "check")
    assert isinstance(PatternGuardrail(), Guardrail)

def test_scope_fence_denies_out_of_workspace_write():
    g = ScopeFenceGuardrail(workspace="/tmp/ws")
    r = g.check(Action("write_file", {"path": "../../etc/passwd", "content": "x"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_scope_fence_denies_sensitive_read():
    g = ScopeFenceGuardrail(workspace="/tmp/ws")
    r = g.check(Action("read_file", {"path": ".env"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_scope_fence_denies_ssh_read():
    g = ScopeFenceGuardrail(workspace="/tmp/ws")
    r = g.check(Action("read_file", {"path": "~/.ssh/id_rsa"}), RunContext(task=""))
    assert r.decision == Decision.DENY

def test_scope_fence_allows_in_workspace_write():
    g = ScopeFenceGuardrail(workspace="/tmp/ws")
    r = g.check(Action("write_file", {"path": "src/main.py", "content": "x"}), RunContext(task=""))
    assert r.decision == Decision.ALLOW

def test_sandbox_boundary_flags_network_action():
    g = SandboxBoundaryGuardrail()
    r = g.check(Action("run_shell", {"cmd": "pip install requests"}), RunContext(task=""))
    assert r.decision == Decision.REQUIRE_APPROVAL
    assert "network" in r.reason.lower()

def test_sandbox_boundary_allows_offline():
    g = SandboxBoundaryGuardrail()
    r = g.check(Action("run_shell", {"cmd": "pytest"}), RunContext(task=""))
    assert r.decision == Decision.ALLOW

def test_risk_classifier_assigns_high_to_write():
    g = RiskClassifierGuardrail()
    r = g.check(Action("write_file", {"path": "a.py", "content": "x"}), RunContext(task=""))
    assert r.risk_level == RiskLevel.MEDIUM

def test_risk_classifier_assigns_critical_to_shell():
    g = RiskClassifierGuardrail()
    r = g.check(Action("run_shell", {"cmd": "x"}), RunContext(task=""))
    assert r.risk_level == RiskLevel.HIGH
