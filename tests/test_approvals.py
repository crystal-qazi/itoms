"""Approval workflow validation and audit contract tests."""
import pytest

from itoms.services import approvals


class FakeCursor:
    def __init__(self):
        self.lastrowid = 42
        self.statements = []
        self.rows = iter([(1,), (1,)])

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return next(self.rows)

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.fake_cursor = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self, *args, **kwargs):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_create_approval_writes_submission_audit_in_same_transaction(monkeypatch):
    connection = FakeConnection()
    monkeypatch.setattr(approvals, "has_permission", lambda *_: True)
    monkeypatch.setattr(approvals, "get_connection", lambda: connection)

    request_id = approvals.create_approval(
        actor_employee_id=10,
        request_type="CHANGE",
        resource_type="change",
        resource_id="25",
        approver_employee_ids=[11, 12],
        reason="Routine change",
    )

    assert request_id == 42
    assert connection.committed
    audit_sql = [sql for sql, _ in connection.fake_cursor.statements if "APPROVAL_SUBMITTED" in sql]
    assert len(audit_sql) == 1


def test_create_approval_rejects_requester_as_approver_before_database(monkeypatch):
    monkeypatch.setattr(approvals, "has_permission", lambda *_: True)
    monkeypatch.setattr(approvals, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(approvals.ApprovalError, match="distinct approvers"):
        approvals.create_approval(
            actor_employee_id=10,
            request_type="CHANGE",
            resource_type="change",
            resource_id="25",
            approver_employee_ids=[11, 10],
        )


def test_create_approval_rejects_oversized_reason_before_database(monkeypatch):
    monkeypatch.setattr(approvals, "has_permission", lambda *_: True)
    monkeypatch.setattr(approvals, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(approvals.ApprovalError, match="reason is too long"):
        approvals.create_approval(
            actor_employee_id=10,
            request_type="CHANGE",
            resource_type="change",
            resource_id="25",
            approver_employee_ids=[11],
            reason="x" * 4001,
        )


def test_decision_rejects_oversized_comment_before_database(monkeypatch):
    monkeypatch.setattr(approvals, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(approvals.ApprovalError, match="comment is too long"):
        approvals.decide_approval(
            actor_employee_id=11,
            request_id=42,
            decision="APPROVED",
            comment="x" * 4001,
        )
