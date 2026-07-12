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

    def contains(self, action_id: str) -> bool:
        return action_id in self._states

    def _require(self, action_id: str, expected: ActionState) -> None:
        if action_id not in self._states:
            raise KeyError(f"unknown action: {action_id}")
        if self._states[action_id] != expected:
            raise PermissionError(
                f"illegal transition: {action_id} is "
                f"{self._states[action_id]}, expected {expected}"
            )
