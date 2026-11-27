"""Approval rejection lifecycle integration tests."""
from itoms.services import approvals


class RejectCursor:
    def __init__(self):
        self.rows = iter([("CHANGE", "change", "25"), ("SUBMITTED",), ("PENDING", 1, "CHANGE", "change", "25"), (101, "PENDING")])
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return next(self.rows)

    def close(self):
        pass


class RejectConnection:
    def __init__(self):
        self.fake_cursor = RejectCursor()
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


def test_rejecting_change_approval_returns_change_to_resubmittable_state(monkeypatch):
    connection = RejectConnection()
    monkeypatch.setattr(approvals, "get_connection", lambda: connection)

    approvals.decide_approval(
        actor_employee_id=11,
        request_id=42,
        decision="REJECTED",
        comment="Needs rollback detail",
    )

    sql = [statement for statement, _ in connection.fake_cursor.statements]
    assert any("UPDATE change_records SET status='REJECTED'" in statement for statement in sql)
    assert any("APPROVAL_REJECTED" in statement for statement in sql)
    assert any("CHANGE_APPROVAL_REJECTED" in statement for statement in sql)
    assert connection.committed
    assert not connection.rolled_back


class CancelCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.statements = []
        self.rowcount = 1

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return next(self.rows)

    def close(self):
        pass


class CancelConn:
    def __init__(self, rows):
        self.fake_cursor = CancelCursor(rows)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


def test_cancelling_change_approval_returns_change_to_draft(monkeypatch):
    first = CancelConn([(10, "PENDING", "CHANGE", "change", "25")])
    second = CancelConn([("SUBMITTED",), (10, "PENDING", "CHANGE", "change", "25")])
    connections = iter([first, second])
    monkeypatch.setattr(approvals, "get_connection", lambda: next(connections))
    monkeypatch.setattr(approvals, "has_permission", lambda *_: True)

    approvals.cancel_approval(actor_employee_id=10, request_id=42)

    sql = [statement for statement, _ in second.fake_cursor.statements]
    change_lock = next(i for i, statement in enumerate(sql) if "FROM change_records" in statement and "FOR UPDATE" in statement)
    approval_lock = next(i for i, statement in enumerate(sql) if "FROM approval_requests" in statement and "FOR UPDATE" in statement)
    assert change_lock < approval_lock
    assert any("UPDATE change_records SET status='DRAFT'" in statement for statement in sql)
    assert any("CHANGE_APPROVAL_CANCELLED" in statement for statement in sql)
    assert second.committed
