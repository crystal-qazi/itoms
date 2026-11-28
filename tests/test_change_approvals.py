"""Change approval submission validation tests."""
import pytest

from itoms.services import change_management


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

    def cursor(self):
        return self.cur

    def commit(self):
        pass

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_change_submission_requires_at_least_one_approver(monkeypatch):
    monkeypatch.setattr(change_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(change_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(change_management.ChangeError, match="1–10 distinct approvers"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SUBMITTED",
            approver_employee_ids=[],
        )


def test_change_submission_rejects_requester_as_approver(monkeypatch):
    monkeypatch.setattr(change_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(change_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(change_management.ChangeError, match="other than yourself"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SUBMITTED",
            approver_employee_ids=[11, 10],
        )


def test_change_submission_requires_approval_creation_permission(monkeypatch):
    def permission(_actor, key, *_context):
        return key != "approvals.create"

    connection = Connection([(25, 10, None, "DRAFT", 1, None)])
    monkeypatch.setattr(change_management, "get_connection", lambda: connection)
    monkeypatch.setattr(
        change_management, "has_permission_in_transaction",
        lambda cur, actor, key, resource=None, **kwargs: key != "approvals.create",
    )

    with pytest.raises(change_management.ChangeError, match="not authorized to submit"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SUBMITTED",
            approver_employee_ids=[11],
        )


def test_change_submission_limits_approval_reason(monkeypatch):
    monkeypatch.setattr(change_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(change_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(change_management.ChangeError, match="reason is too long"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SUBMITTED",
            details="x" * 4001,
            approver_employee_ids=[11],
        )
