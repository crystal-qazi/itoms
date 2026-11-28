"""Identity provisioning and role assignments enforce actor scope."""
import pytest

from itoms.services import identity_admin
from itoms.services.authorization import ResourceContext


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.lastrowid = 91
        self.statements = []

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def fetchone(self):
        return next(self.rows)

    def fetchall(self):
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


def test_account_creation_checks_department_scope(monkeypatch):
    connection = Connection([(1,), (1,)])
    checks = []
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)
    monkeypatch.setattr(
        identity_admin, "has_permissions_in_transaction",
        lambda cur, actor, key, resources, **kwargs: checks.append((key, resources)) or True,
    )
    monkeypatch.setattr(identity_admin, "validate_password", lambda value: None)
    monkeypatch.setattr(identity_admin, "hash_password", lambda value: "hash")

    result = identity_admin.create_employee_account(
        actor_employee_id=10, employee_code="E-1", full_name="Employee",
        username="employee", initial_password="StrongPassword1!", department_id=7,
    )

    assert result == 91
    assert checks == [("identity.accounts.create", [ResourceContext(department_id=7)])]
    assert connection.committed


def test_account_creation_rejects_out_of_scope_department(monkeypatch):
    connection = Connection([(1,)])
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)
    monkeypatch.setattr(
        identity_admin, "has_permissions_in_transaction",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(identity_admin, "validate_password", lambda value: None)
    monkeypatch.setattr(identity_admin, "hash_password", lambda value: "hash")

    with pytest.raises(identity_admin.IdentityAdministrationError, match="this department or team"):
        identity_admin.create_employee_account(
            actor_employee_id=10, employee_code="E-1", full_name="Employee",
            username="employee", initial_password="StrongPassword1!", department_id=7,
        )

    assert connection.rolled_back and not connection.committed


def test_department_role_assignment_is_bound_to_target_department(monkeypatch):
    connection = Connection([(7,), (1,)])
    checks = []
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)
    monkeypatch.setattr(identity_admin, "has_permission",
                        lambda actor, key, context=None: checks.append((key, context)) or True)

    assignment_id = identity_admin.assign_role(
        actor_employee_id=10, employee_id=20, role_id=3,
        scope_type="DEPARTMENT",
    )

    assert assignment_id == 91
    assert checks == [(
        "identity.roles.assign",
        ResourceContext(department_id=7),
    )]
    assert connection.committed


def test_role_assignment_rejects_out_of_scope_target(monkeypatch):
    connection = Connection([(99,)])
    monkeypatch.setattr(identity_admin, "get_connection", lambda: connection)
    monkeypatch.setattr(identity_admin, "has_permission", lambda *_: False)

    with pytest.raises(identity_admin.IdentityAdministrationError, match="employee scope"):
        identity_admin.assign_role(
            actor_employee_id=10, employee_id=20, role_id=3,
            scope_type="DEPARTMENT",
        )

    assert connection.rolled_back and not connection.committed
