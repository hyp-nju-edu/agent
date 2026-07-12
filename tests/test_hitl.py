import pytest
from sentinel.core.types import Action
from sentinel.core.hitl import HITLStateMachine, ActionState

def test_submit_sets_pending():
    fsm = HITLStateMachine()
    s = fsm.submit(Action("run_shell", {"cmd": "pip install x"}, id="a1"))
    assert s == ActionState.PENDING_APPROVAL

def test_approve_transitions_to_executing():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    s = fsm.approve("a1")
    assert s == ActionState.EXECUTING

def test_deny_transitions_to_skipped():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    s = fsm.deny("a1")
    assert s == ActionState.SKIPPED

def test_timeout_transitions_to_skipped():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    s = fsm.timeout("a1")
    assert s == ActionState.SKIPPED

def test_executed_after_approved():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    fsm.approve("a1")
    s = fsm.mark_executed("a1", success=True)
    assert s == ActionState.EXECUTED

def test_failed_after_approved():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    fsm.approve("a1")
    s = fsm.mark_executed("a1", success=False)
    assert s == ActionState.FAILED

def test_illegal_transition_raises():
    fsm = HITLStateMachine()
    fsm.submit(Action("x", {}, id="a1"))
    with pytest.raises(PermissionError):
        fsm.mark_executed("a1", success=True)  # not approved yet

def test_unknown_action_raises():
    fsm = HITLStateMachine()
    with pytest.raises(KeyError):
        fsm.approve("nope")
