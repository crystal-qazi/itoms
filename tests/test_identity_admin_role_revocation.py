"""Unit validation for scoped role-assignment revocation."""
import pytest

from itoms.services import identity_admin
from itoms.services.identity_admin import IdentityAdministrationError


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.statements = []
    def execute(self, sql, params=None):
        self.statements.append((sql, params))
    def fetchone(self):
        return next(self.rows)
    def close(self):
        pass


class Connection:
    def __init__(self, rows):
        self.cur = Cursor(rows)
        self.committed = False
        self.rolled_back = False
    def cursor(self):
        return self.cur
    def commit(self):
        self.committed = True
    def rollback(self):
        self.rolled_back = True
    def close(self):
        pass


def test_revoke_role_assignment_rejects_invalid_ids_before_database(monkeypatch):
    monkeypatch.setattr(
        identity_admin, "get_connection",
        lambda: pytest.fail("database must not be opened for invalid IDs"),
    )
    with pytest.raises(IdentityAdministrationError, match="positive integers"):
        identity_admin.revoke_role_assignment(actor_employee_id=1, assignment_id=0)


def test_revoke_role_assignment_returns_false_when_missing(monkeypatch):
    connection = Connection([None])
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    assert identity_admin.revoke_role_assignment(
        actor_employee_id=1, assignment_id=99,
    ) is False
    assert connection.committed
    assert not connection.rolled_back


def test_revoke_role_assignment_blocks_self_revocation(monkeypatch):
    connection = Connection([(10, 3, "OWN", None, True)])
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)
    monkeypatch.setattr(
        identity_admin, "has_permission",
        lambda *_: pytest.fail("self-revocation must be blocked before permission lookup"),
    )

    with pytest.raises(IdentityAdministrationError, match="Self-revocation"):
        identity_admin.revoke_role_assignment(actor_employee_id=10, assignment_id=4)
    assert connection.rolled_back
