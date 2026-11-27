"""Audited role permission administration tests."""
import pytest

from itoms.services import identity_admin


class Cursor:
    def __init__(self, rows, rowcount=1):
        self.rows = iter(rows)
        self.rowcount = rowcount
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return next(self.rows)

    def close(self):
        pass


class Connection:
    def __init__(self, rows, rowcount=1):
        self.fake_cursor = Cursor(rows, rowcount)
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


def test_grant_role_permission_is_explicit_and_audited(monkeypatch):
    connection = Connection([("Change Manager",), (10,), (1, 0), None, (23,)], rowcount=1)
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    assert identity_admin.grant_role_permission(
        actor_employee_id=1, role_id=4, permission_key="approvals.create"
    ) is True

    sql = [statement for statement, _ in connection.fake_cursor.statements]
    assert any("INSERT IGNORE INTO role_permissions" in statement for statement in sql)
    assert any("IDENTITY_ROLE_PERMISSION_GRANTED" in statement for statement in sql)
    assert connection.committed
    assert not connection.rolled_back


def test_grant_role_permission_requires_management_permission(monkeypatch):
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: False)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(identity_admin.IdentityAdministrationError, match="Not authorized"):
        identity_admin.grant_role_permission(
            actor_employee_id=1, role_id=4, permission_key="approvals.create"
        )


def test_revoke_role_permission_is_audited(monkeypatch):
    connection = Connection([("Change Manager",), (10,), (1, 0), None, (23,)], rowcount=1)
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    assert identity_admin.revoke_role_permission(
        actor_employee_id=1, role_id=4, permission_key="approvals.create"
    ) is True

    sql = [statement for statement, _ in connection.fake_cursor.statements]
    assert any("DELETE FROM role_permissions" in statement for statement in sql)
    assert any("IDENTITY_ROLE_PERMISSION_REVOKED" in statement for statement in sql)
    assert connection.committed


def test_role_permission_management_rejects_unknown_permission(monkeypatch):
    connection = Connection([("Change Manager",), (10,), (1, 0), None, None])
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    with pytest.raises(identity_admin.IdentityAdministrationError, match="not registered"):
        identity_admin.grant_role_permission(
            actor_employee_id=1, role_id=4, permission_key="unknown.permission"
        )

    assert connection.rolled_back
    assert not connection.committed


def test_role_permission_admin_cannot_modify_own_role(monkeypatch):
    connection = Connection([("Change Manager",), (10,), (1, 0), (1,)])
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    with pytest.raises(identity_admin.IdentityAdministrationError, match="own account"):
        identity_admin.grant_role_permission(
            actor_employee_id=1, role_id=4, permission_key="approvals.create"
        )

    assert connection.rolled_back
    assert not connection.committed



def test_grant_role_permission_rejects_role_shared_across_departments(monkeypatch):
    connection = Connection([("Change Manager",), (10,), (2, 1)])
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    with pytest.raises(identity_admin.IdentityAdministrationError, match="all active assignments"):
        identity_admin.grant_role_permission(
            actor_employee_id=1, role_id=4, permission_key="approvals.create"
        )

    assert connection.rolled_back
    assert not connection.committed


def test_grant_role_permission_reserves_unassigned_roles(monkeypatch):
    connection = Connection([("Change Manager",), (10,), (0, None)])
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    with pytest.raises(identity_admin.IdentityAdministrationError, match="reserved"):
        identity_admin.grant_role_permission(
            actor_employee_id=1, role_id=4, permission_key="approvals.create"
        )

    assert connection.rolled_back
    assert not connection.committed


def test_role_permission_scope_requires_actor_department(monkeypatch):
    connection = Connection([("Change Manager",), (None,)])
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    with pytest.raises(identity_admin.IdentityAdministrationError, match="department-scoped"):
        identity_admin.grant_role_permission(
            actor_employee_id=1, role_id=4, permission_key="approvals.create"
        )

    assert connection.rolled_back
    assert not connection.committed


def test_role_admin_cannot_assign_role_to_self(monkeypatch):
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(identity_admin.IdentityAdministrationError, match="Self-assignment"):
        identity_admin.assign_role(
            actor_employee_id=1, employee_id=1, role_id=4, scope_type="OWN"
        )



class MatrixCursor:
    def __init__(self):
        self.results = iter([
            [{"role_id": 4, "role_name": "Change Manager"}],
            [{"permission_key": "approvals.create", "description": "Submit approvals", "is_granted": 1}],
        ])
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchall(self):
        return next(self.results)

    def close(self):
        pass


class MatrixConnection:
    def __init__(self):
        self.fake_cursor = MatrixCursor()

    def cursor(self, dictionary=False):
        assert dictionary is True
        return self.fake_cursor

    def close(self):
        pass


def test_list_role_permission_options_returns_role_grants(monkeypatch):
    connection = MatrixConnection()
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: True)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)

    result = identity_admin.list_role_permission_options(actor_employee_id=1, role_id=4)

    assert result["selected_role_id"] == 4
    assert result["roles"][0]["role_name"] == "Change Manager"
    assert result["permissions"][0]["permission_key"] == "approvals.create"
    assert result["permissions"][0]["is_granted"] == 1


def test_list_role_permission_options_requires_management_permission(monkeypatch):
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: False)
    monkeypatch.setattr(identity_admin, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(identity_admin.IdentityAdministrationError, match="Not authorized"):
        identity_admin.list_role_permission_options(actor_employee_id=1)
