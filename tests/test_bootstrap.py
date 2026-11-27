"""Tests for one-time first-administrator bootstrap safeguards."""
import pytest

from itoms.services import bootstrap


class Cursor:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.statements = []
        self.batch = []
        self.lastrowid = 71

    def execute(self, sql, params=None):
        self.statements.append((sql, params))

    def executemany(self, sql, params):
        self.batch.append((sql, list(params)))

    def fetchone(self):
        return next(self.responses)

    def fetchall(self):
        return next(self.responses)

    def close(self):
        pass


class Connection:
    def __init__(self, responses):
        self.cur = Cursor(responses)
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


def patch_bootstrap(monkeypatch, connection):
    monkeypatch.setattr(bootstrap, "get_connection", lambda: connection)
    monkeypatch.setattr(bootstrap, "validate_password", lambda value: None)
    monkeypatch.setattr(bootstrap, "hash_password", lambda value: "hashed-password")


def test_bootstrap_creates_department_scoped_admin_atomically(monkeypatch):
    connection = Connection([(1,), None, (0,), (1,), [(3,), (4,), (5,)]])
    patch_bootstrap(monkeypatch, connection)

    employee_id = bootstrap.bootstrap_first_administrator(
        employee_code="IT-001", full_name="First Admin", username="itadmin",
        password="StrongPassword1!", department_id=9,
    )

    assert employee_id == 71
    assert connection.committed and not connection.rolled_back
    sql = [statement for statement, _ in connection.cur.statements]
    assert any("INITIAL_ADMIN_BOOTSTRAPPED" in statement for statement in sql)
    assert any("'DEPARTMENT'" in statement for statement in sql)
    assert len(connection.cur.batch[0][1]) == 3


def test_bootstrap_refuses_completed_marker(monkeypatch):
    connection = Connection([(1,), ("completed",)])
    patch_bootstrap(monkeypatch, connection)

    with pytest.raises(bootstrap.BootstrapError, match="already been completed"):
        bootstrap.bootstrap_first_administrator(
            employee_code="IT-001", full_name="First Admin", username="itadmin",
            password="StrongPassword1!", department_id=9,
        )

    assert connection.rolled_back and not connection.committed


def test_bootstrap_refuses_existing_accounts(monkeypatch):
    connection = Connection([(1,), None, (2,)])
    patch_bootstrap(monkeypatch, connection)

    with pytest.raises(bootstrap.BootstrapError, match="Accounts already exist"):
        bootstrap.bootstrap_first_administrator(
            employee_code="IT-001", full_name="First Admin", username="itadmin",
            password="StrongPassword1!", department_id=9,
        )

    assert connection.rolled_back and not connection.committed


def test_bootstrap_refuses_inactive_or_missing_department(monkeypatch):
    connection = Connection([(1,), None, (0,), None])
    patch_bootstrap(monkeypatch, connection)

    with pytest.raises(bootstrap.BootstrapError, match="department does not exist"):
        bootstrap.bootstrap_first_administrator(
            employee_code="IT-001", full_name="First Admin", username="itadmin",
            password="StrongPassword1!", department_id=9,
        )

    assert connection.rolled_back and not connection.committed
