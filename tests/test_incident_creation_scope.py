"""Incident creation must honor requester and team scope, not just action grants."""
import pytest

from itoms.services import incidents
from itoms.services.authorization import ResourceContext


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.lastrowid = 501
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


def test_incident_creation_checks_requester_scope(monkeypatch):
    connection = Connection([(7,), (7, True), None])
    checks = []
    monkeypatch.setattr(incidents, "get_connection", lambda: connection)
    monkeypatch.setattr(
        incidents, "has_permission_in_transaction",
        lambda cur, actor, key, context=None, **kwargs:
            checks.append((key, context, kwargs.get("lock_employee_ids"))) or True,
    )

    ticket_id = incidents.create_incident(
        actor_employee_id=11, title="Network issue", description="Link down"
    )

    assert ticket_id == 501
    assert checks == [(
        "incident.create",
        ResourceContext(owner_employee_id=11, department_id=7),
        [11],
    )]
    assert connection.committed


def test_incident_creation_rejects_out_of_scope_requester(monkeypatch):
    connection = Connection([(99,)])
    checks = []
    monkeypatch.setattr(incidents, "get_connection", lambda: connection)
    def permission(cur, actor, key, context=None, **kwargs):
        checks.append((key, context))
        return False
    monkeypatch.setattr(incidents, "has_permission_in_transaction", permission)

    with pytest.raises(incidents.IncidentError, match="requester or team"):
        incidents.create_incident(
            actor_employee_id=11, title="Network issue", description="Link down"
        )

    assert connection.rolled_back and not connection.committed
    assert checks[-1][1].department_id == 99


def test_initial_team_assignment_requires_assign_scope(monkeypatch):
    connection = Connection([(7,), (8,)])
    checks = []
    monkeypatch.setattr(incidents, "get_connection", lambda: connection)
    def permission(cur, actor, key, context=None, **kwargs):
        checks.append((key, context))
        return key != "incident.assign"
    monkeypatch.setattr(incidents, "has_permission_in_transaction", permission)

    with pytest.raises(incidents.IncidentError, match="assign new incidents"):
        incidents.create_incident(
            actor_employee_id=11, title="Network issue", description="Link down",
            assigned_team_id=22,
        )

    assert connection.rolled_back and not connection.committed
    assert checks[-1] == (
        "incident.assign", ResourceContext(team_id=22, department_id=8)
    )
