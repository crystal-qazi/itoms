"""Unit tests for engineering task lifecycle invariants."""
from itoms.services.engineering_tasks import TASK_TRANSITIONS

def test_task_lifecycle_has_only_explicit_forward_transitions():
    assert TASK_TRANSITIONS["BACKLOG"] == {"READY", "CANCELLED"}
    assert "DONE" in TASK_TRANSITIONS["IN_REVIEW"]
    assert TASK_TRANSITIONS["DONE"] == set()
    assert TASK_TRANSITIONS["CANCELLED"] == set()

def test_task_transition_map_does_not_allow_unknown_states():
    assert TASK_TRANSITIONS.get("UNKNOWN", set()) == set()
