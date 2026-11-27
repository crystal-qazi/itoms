"""Tests for directory service validation and membership lock ordering."""
import pytest

from itoms.services import directory
from itoms.services.directory import DirectoryError, assign_employee_to_team, remove_employee_from_team


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))

    def fetchone(self):
        return next(self.rows)

    def close(self):
        pass


class Connection:
    def __init__(self, rows):
        self.fake_cursor = Cursor(rows)
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


def test_rejects_invalid_ids_before_database_access(monkeypatch):
    monkeypatch.setattr(directory, "get_connection", lambda: pytest.fail("database must not be opened"))
    with pytest.raises(DirectoryError):
        assign_employee_to_team(0, 2)
    with pytest.raises(DirectoryError):
        assign_employee_to_team(1, -1)
    with pytest.raises(DirectoryError):
        remove_employee_from_team(0, 2)
    with pytest.raises(DirectoryError):
        remove_employee_from_team(1, -1)


def test_remove_locks_employee_then_team_then_membership(monkeypatch):
    connection = Connection([(1, True), (1, True), (False,), (False,)])
    monkeypatch.setattr(directory, "get_connection", lambda: connection)

    remove_employee_from_team(7, 12)

    statements = [sql for sql, _ in connection.fake_cursor.statements]
    assert "FROM employees WHERE employee_id=%s FOR UPDATE" in statements[0]
    assert "FROM teams WHERE team_id=%s FOR UPDATE" in statements[1]
    assert "FROM employee_team_memberships" in statements[2]
    assert "FOR UPDATE" in statements[2]
    assert "FROM team_management_assignments" in statements[3]
    assert "FOR UPDATE" in statements[3]
    assert statements[4].startswith("DELETE FROM employee_team_memberships")
    assert connection.committed
    assert not connection.rolled_back


def test_remove_refuses_primary_membership_and_rolls_back(monkeypatch):
    connection = Connection([(1, True), (1, True), (True,)])
    monkeypatch.setattr(directory, "get_connection", lambda: connection)

    with pytest.raises(DirectoryError, match="Reassign the primary team"):
        remove_employee_from_team(7, 12)

    assert connection.rolled_back
    assert not connection.committed
    assert len(connection.fake_cursor.statements) == 3



def test_remove_refuses_manager_membership_until_manager_assignment_removed(monkeypatch):
    connection = Connection([(1, True), (1, True), (False,), (True,)])
    monkeypatch.setattr(directory, "get_connection", lambda: connection)

    with pytest.raises(DirectoryError, match="Remove the manager assignment"):
        remove_employee_from_team(7, 12)

    assert connection.rolled_back
    assert not connection.committed
    assert len(connection.fake_cursor.statements) == 4



def test_remove_refuses_manager_membership_until_manager_assignment_removed(monkeypatch):
    connection = Connection([(1, True), (1, True), (False,), (True,)])
    monkeypatch.setattr(directory, "get_connection", lambda: connection)

    with pytest.raises(DirectoryError, match="Remove the manager assignment"):
        remove_employee_from_team(7, 12)

    assert connection.rolled_back
    assert not connection.committed
    assert len(connection.fake_cursor.statements) == 4
