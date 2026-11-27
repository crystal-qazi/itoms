"""Action-level permission and resource-scope authorization tests."""
from itoms.services import authorization


class Cursor:
    def __init__(self, assignments):
        self.assignments = assignments

    def execute(self, *_args, **_kwargs):
        pass

    def fetchall(self):
        return self.assignments

    def fetchone(self):
        return None

    def close(self):
        pass


class Connection:
    def __init__(self, assignments):
        self.cur = Cursor(assignments)

    def cursor(self):
        return self.cur

    def close(self):
        pass


def test_action_permission_without_resource_context_uses_active_assignment(monkeypatch):
    monkeypatch.setattr(authorization, "get_connection", lambda: Connection([("OWN", None)]))

    assert authorization.has_permission(10, "approvals.create") is True


def test_resource_permission_still_enforces_owner_scope(monkeypatch):
    monkeypatch.setattr(authorization, "get_connection", lambda: Connection([("OWN", None)]))

    assert authorization.has_permission(
        10, "change.read",
        authorization.ResourceContext(owner_employee_id=11, resource_type="change", resource_id="25"),
    ) is False


def test_resource_permission_allows_matching_owner_scope(monkeypatch):
    monkeypatch.setattr(authorization, "get_connection", lambda: Connection([("OWN", None)]))

    assert authorization.has_permission(
        10, "change.read",
        authorization.ResourceContext(owner_employee_id=10, resource_type="change", resource_id="25"),
    ) is True
