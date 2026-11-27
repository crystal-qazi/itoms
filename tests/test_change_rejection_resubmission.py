"""Approval rejection lifecycle integration tests."""
from itoms.services import approvals


class RejectCursor:
    def __init__(self):
        self.rows = iter([("PENDING", 1, "CHANGE", "change", "25"), (101, "PENDING")])
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
