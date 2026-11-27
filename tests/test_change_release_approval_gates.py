"""Fail-closed business transition tests for linked approval gates."""
import pytest

from itoms.services import change_management, release_management


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)

    def execute(self, *_args, **_kwargs):
        pass

    def fetchone(self):
        return next(self.rows)

    def close(self):
        pass


class Connection:
    def __init__(self, rows):
        self.cur = Cursor(rows)
        self.rolled_back = False
        self.committed = False

    def cursor(self, *args, **kwargs):
        return self.cur

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_change_cannot_be_scheduled_without_approved_linked_request(monkeypatch):
    snapshot = {"change_id": 25, "requested_by": 10, "status": "SUBMITTED"}
    first = Connection([snapshot])
    second = Connection([("SUBMITTED", 10), None])
    connections = iter([first, second])
    monkeypatch.setattr(change_management, "get_connection", lambda: next(connections))
    monkeypatch.setattr(change_management, "has_permission", lambda *_: True)

    with pytest.raises(change_management.ChangeError, match="fully approved"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SCHEDULED",
        )

    assert second.rolled_back
    assert not second.committed


def test_release_cannot_be_approved_without_approved_linked_request(monkeypatch):
    snapshot = {"release_id": 5, "release_key": "REL-5", "created_by": 10, "status": "READY"}
    first = Connection([snapshot])
    second = Connection([("READY", 10, "REL-5"), None])
    connections = iter([first, second])
    monkeypatch.setattr(release_management, "get_connection", lambda: next(connections))
    monkeypatch.setattr(release_management, "has_permission", lambda *_: True)

    with pytest.raises(release_management.ReleaseError, match="fully approved"):
        release_management.transition_release(
            actor_employee_id=10,
            release_id=5,
            new_status="APPROVED",
        )

    assert second.rolled_back
    assert not second.committed

def test_release_cannot_deploy_without_approved_linked_request(monkeypatch):
    snapshot = {"release_id": 5, "release_key": "REL-5", "created_by": 10, "status": "APPROVED"}
    first = Connection([snapshot])
    second = Connection([("APPROVED", 10, "REL-5"), None])
    connections = iter([first, second])
    monkeypatch.setattr(release_management, "get_connection", lambda: next(connections))
    monkeypatch.setattr(release_management, "has_permission", lambda *_: True)

    with pytest.raises(release_management.ReleaseError, match="fully approved"):
        release_management.transition_release(
            actor_employee_id=10,
            release_id=5,
            new_status="DEPLOYING",
        )

    assert second.rolled_back
    assert not second.committed


def test_release_approval_cannot_bypass_sqa_readiness_gate(monkeypatch):
    snapshot = {"release_id": 5, "release_key": "REL-5", "created_by": 10, "status": "READY"}
    first = Connection([snapshot])
    second = Connection([("READY", 10, "REL-5"), ("APPROVED",), (0,)])
    connections = iter([first, second])
    monkeypatch.setattr(release_management, "get_connection", lambda: next(connections))
    monkeypatch.setattr(release_management, "has_permission", lambda *_: True)

    with pytest.raises(release_management.ReleaseError, match="completed test plan"):
        release_management.transition_release(
            actor_employee_id=10,
            release_id=5,
            new_status="APPROVED",
        )

    assert second.rolled_back
    assert not second.committed


def test_release_deployment_rechecks_sqa_readiness_gate(monkeypatch):
    snapshot = {"release_id": 5, "release_key": "REL-5", "created_by": 10, "status": "APPROVED"}
    first = Connection([snapshot])
    second = Connection([("APPROVED", 10, "REL-5"), ("APPROVED",), (0,)])
    connections = iter([first, second])
    monkeypatch.setattr(release_management, "get_connection", lambda: next(connections))
    monkeypatch.setattr(release_management, "has_permission", lambda *_: True)

    with pytest.raises(release_management.ReleaseError, match="completed test plan"):
        release_management.transition_release(
            actor_employee_id=10,
            release_id=5,
            new_status="DEPLOYING",
        )

    assert second.rolled_back
    assert not second.committed

@pytest.mark.parametrize(
    ("defect_status", "unresolved_count", "blocked"),
    [
        ("FIXED", 1, True),
        ("RETEST", 1, True),
        ("CLOSED", 0, False),
        ("REJECTED", 0, False),
    ],
)
def test_release_gate_treats_only_closed_or_rejected_defects_as_resolved(
    monkeypatch, defect_status, unresolved_count, blocked
):
    class GateCursor:
        def __init__(self):
            self.rows = iter([(1,), (1,), (0,), (unresolved_count,), (1, 0)])
            self.statements = []

        def execute(self, statement, params=None):
            self.statements.append(statement)

        def fetchone(self):
            return next(self.rows)

    cursor = GateCursor()
    if blocked:
        with pytest.raises(release_management.ReleaseError, match="unresolved High/Critical defects"):
            release_management._assert_sqa_release_gate(cursor, "REL-REGRESSION")
    else:
        release_management._assert_sqa_release_gate(cursor, "REL-REGRESSION")

    defect_query = next(
        statement for statement in cursor.statements
        if "sqa_defects" in statement
    )
    assert "d.status NOT IN ('CLOSED','REJECTED')" in defect_query
    assert blocked is (unresolved_count == 1)
