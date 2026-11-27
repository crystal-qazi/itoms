"""Unit tests for scoped employee directory administration."""
import pytest

from itoms.services import directory_admin
from itoms.services.directory_admin import DirectoryAdministrationError


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
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
    def cursor(self, **_kwargs):
        return self.cur
    def commit(self):
        self.committed = True
    def rollback(self):
        self.rolled_back = True
    def close(self):
        pass


def test_manager_assignment_requires_team_membership(monkeypatch):
    connection = Connection([(7, 7), (20, 7, True), (7, True), None])
    monkeypatch.setattr(directory_admin, "get_connection", lambda: connection)
    monkeypatch.setattr(directory_admin, "has_permission", lambda *_: True)

    with pytest.raises(DirectoryAdministrationError, match="active member"):
        directory_admin.assign_team_manager(
            actor_employee_id=10, manager_employee_id=20, team_id=30,
        )

    assert connection.rolled_back
    assert not connection.committed
    assert len(connection.cur.statements) == 4


def test_manager_assignment_rejects_cross_department_before_write(monkeypatch):
    connection = Connection([(7, 8)])
    monkeypatch.setattr(directory_admin, "get_connection", lambda: connection)
    monkeypatch.setattr(
        directory_admin, "has_permission",
        lambda *_: pytest.fail("permission must not be checked for cross-department assignment"),
    )

    with pytest.raises(DirectoryAdministrationError, match="same department"):
        directory_admin.assign_team_manager(
            actor_employee_id=10, manager_employee_id=20, team_id=30,
        )

    assert not connection.cur.statements[1:]
    assert not connection.committed



def test_create_team_rejects_blank_name_before_database(monkeypatch):
    monkeypatch.setattr(
        directory_admin, "get_connection",
        lambda: pytest.fail("database must not be opened for an invalid team name"),
    )
    with pytest.raises(DirectoryAdministrationError, match="Team name is required"):
        directory_admin.create_team(actor_employee_id=1, team_name="  ")


def test_set_team_active_rejects_invalid_values_before_database(monkeypatch):
    monkeypatch.setattr(
        directory_admin, "get_connection",
        lambda: pytest.fail("database must not be opened for invalid arguments"),
    )
    with pytest.raises(DirectoryAdministrationError, match="boolean"):
        directory_admin.set_team_active(actor_employee_id=1, team_id=2, is_active="false")



def test_deactivate_employee_rejects_self_deactivation_before_database(monkeypatch):
    monkeypatch.setattr(
        directory_admin, "get_connection",
        lambda: pytest.fail("database must not be opened for self-deactivation"),
    )
    with pytest.raises(DirectoryAdministrationError, match="own employee account"):
        directory_admin.deactivate_employee(actor_employee_id=7, employee_id=7)


def test_deactivate_employee_rejects_invalid_ids_before_database(monkeypatch):
    monkeypatch.setattr(
        directory_admin, "get_connection",
        lambda: pytest.fail("database must not be opened for invalid IDs"),
    )
    with pytest.raises(DirectoryAdministrationError, match="positive integers"):
        directory_admin.deactivate_employee(actor_employee_id=1, employee_id=0)
