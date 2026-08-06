## Task 10: HITL State Machine

**Files:**
- Create: `sentinel/core/hitl.py`
- Test: `tests/test_hitl.py`

**Interfaces:**
- Produces: `ActionState` enum, `HITLStateMachine` (`submit(action) -> state`, `approve(action_id)`, `deny(action_id)`, `timeout(action_id)`, `mark_executed(action_id)`, `state(action_id)`). Illegal transitions raise. Timeout → Skipped (fail-closed).

- [ ] **Step 1: Write the failing test**

`tests/test_hitl.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_hitl.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`sentinel/core/hitl.py`:
```python
from __future__ import annotations
from enum import Enum

from sentinel.core.types import Action


class ActionState(str, Enum):
    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


class HITLStateMachine:
    """Tracks each action through its governance lifecycle. Fail-closed."""

    def __init__(self) -> None:
        self._states: dict[str, ActionState] = {}

    def submit(self, action: Action) -> ActionState:
        self._states[action.id] = ActionState.PENDING_APPROVAL
        return self._states[action.id]

    def approve(self, action_id: str) -> ActionState:
        self._require(action_id, ActionState.PENDING_APPROVAL)
        self._states[action_id] = ActionState.EXECUTING
        return self._states[action_id]

    def deny(self, action_id: str) -> ActionState:
        self._require(action_id, ActionState.PENDING_APPROVAL)
        self._states[action_id] = ActionState.SKIPPED
        return self._states[action_id]

    def timeout(self, action_id: str) -> ActionState:
        self._require(action_id, ActionState.PENDING_APPROVAL)
        self._states[action_id] = ActionState.SKIPPED
        return self._states[action_id]

    def mark_executed(self, action_id: str, success: bool) -> ActionState:
        self._require(action_id, ActionState.EXECUTING)
        self._states[action_id] = ActionState.EXECUTED if success else ActionState.FAILED
        return self._states[action_id]

    def state(self, action_id: str) -> ActionState:
        return self._states[action_id]

    def _require(self, action_id: str, expected: ActionState) -> None:
        if action_id not in self._states:
            raise KeyError(f"unknown action: {action_id}")
        if self._states[action_id] != expected:
            raise PermissionError(
                f"illegal transition: {action_id} is "
                f"{self._states[action_id]}, expected {expected}"
            )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest tests/test_hitl.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add sentinel/core/hitl.py tests/test_hitl.py
git commit -m "feat(governance): add HITL state machine with fail-closed transitions"
```

---

