from sentinel.core.types import (
    Action, Decision, RiskLevel, GuardrailResult, ToolResult,
    Feedback, Failure, FailureKind, Event, RunContext, Approval,
    ApprovalDecision,
)

def test_action_defaults_have_id():
    a = Action(tool="run_shell", args={"cmd": "ls"})
    assert a.tool == "run_shell"
    assert a.id  # auto-generated
    assert a.raw_source == ""
    assert a.turn_id == ""

def test_decision_values():
    assert Decision.ALLOW.value == "allow"
    assert Decision.DENY.value == "deny"
    assert Decision.REQUIRE_APPROVAL.value == "require_approval"

def test_risk_level_ordering():
    assert RiskLevel.LOW < RiskLevel.HIGH
    assert RiskLevel.CRITICAL > RiskLevel.MEDIUM

def test_risk_level_le_ge():
    assert (RiskLevel.LOW <= RiskLevel.HIGH) is True
    assert (RiskLevel.CRITICAL <= RiskLevel.MEDIUM) is False
    assert (RiskLevel.HIGH >= RiskLevel.LOW) is True
    assert (RiskLevel.MEDIUM >= RiskLevel.CRITICAL) is False

def test_guardrail_result_fields():
    r = GuardrailResult(decision=Decision.DENY, reason="x",
                        risk_level=RiskLevel.CRITICAL, guardrail_name="pat")
    assert r.decision == Decision.DENY
    assert r.risk_level == RiskLevel.CRITICAL

def test_tool_result_defaults():
    t = ToolResult(success=True)
    assert t.stdout == "" and t.stderr == ""
    assert t.truncated is False
    assert t.artifacts == {}

def test_feedback_unknown_passed():
    f = Feedback(kind="pytest", passed=None, failures=[], raw_output="...")
    assert f.passed is None
    assert f.failures == []

def test_event_carries_type_and_data():
    e = Event(type="ApprovalNeeded", data={"action_id": "a1"})
    assert e.type == "ApprovalNeeded"
    assert e.data["action_id"] == "a1"

def test_run_context_holds_task():
    ctx = RunContext(task="fix the test")
    assert ctx.task == "fix the test"
    assert ctx.turns == []

def test_approval_decision_values():
    assert ApprovalDecision.APPROVED.value == "approved"
    assert ApprovalDecision.DENIED.value == "denied"
