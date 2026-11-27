"""HTTP tests for the department directory administration boundary."""
from flask import g
import pytest

from itoms import create_app


class TestConfig:
    SECRET_KEY = "testing-key"
    TESTING = True
    DB_HOST = "127.0.0.1"
    DB_PORT = 3306
    DB_NAME = "test"
    DB_USER = "test"
    DB_PASSWORD = ""
    DB_CONNECT_TIMEOUT = 1
    LOG_LEVEL = "CRITICAL"

    @classmethod
    def validate(cls, config):
        return None


def _app_with_identity():
    app = create_app(TestConfig)

    @app.before_request
    def set_test_identity():
        g.account_id = 1
        g.employee_id = 10
        g.mfa_enabled = True

    return app


def test_directory_admin_blueprint_is_registered():
    app = _app_with_identity()
    expected = {
        "directory_admin.index", "directory_admin.create_employee",
        "directory_admin.assign_membership", "directory_admin.remove_membership",
        "directory_admin.assign_manager", "directory_admin.remove_manager",
        "directory_admin.assign_employee_role", "directory_admin.revoke_employee_role",
    }
    assert expected.issubset(app.view_functions)


def test_directory_page_denies_missing_department_authority(monkeypatch):
    from itoms.web import directory_admin as directory_web
    from itoms.services.directory_admin import DirectoryAdministrationError

    app = _app_with_identity()
    monkeypatch.setattr(
        directory_web, "list_directory",
        lambda **_: (_ for _ in ()).throw(DirectoryAdministrationError("denied")),
    )
    response = app.test_client().get("/admin/directory/")
    assert response.status_code == 403


def test_directory_mutation_rejects_missing_csrf(monkeypatch):
    from itoms.web import directory_admin as directory_web

    app = _app_with_identity()
    monkeypatch.setattr(
        directory_web, "create_directory_employee",
        lambda **_: pytest.fail("must not write"),
    )
    response = app.test_client().post("/admin/directory/employees", data={
        "employee_code": "E-1", "full_name": "Example", "username": "example",
        "initial_password": "NotARealPassword123!",
    })
    assert response.status_code == 400


def test_membership_route_passes_primary_selection(monkeypatch):
    from itoms.web import directory_admin as directory_web

    app = _app_with_identity()
    calls = []
    monkeypatch.setattr(directory_web, "assign_team_membership", lambda **kwargs: calls.append(kwargs))
    client = app.test_client()
    with client.session_transaction() as state:
        state["csrf_token"] = "expected-token"
    response = client.post("/admin/directory/memberships", data={
        "csrf_token": "expected-token", "employee_id": "25",
        "team_id": "8", "primary": "1",
    })
    assert response.status_code == 302
    assert calls == [{
        "actor_employee_id": 10, "employee_id": 25, "team_id": 8, "primary": True,
    }]


def test_manager_route_uses_selected_employee_and_team(monkeypatch):
    from itoms.web import directory_admin as directory_web

    app = _app_with_identity()
    calls = []
    monkeypatch.setattr(directory_web, "assign_team_manager", lambda **kwargs: calls.append(kwargs) or True)
    client = app.test_client()
    with client.session_transaction() as state:
        state["csrf_token"] = "expected-token"
    response = client.post("/admin/directory/managers", data={
        "csrf_token": "expected-token", "employee_id": "25", "team_id": "8",
    })
    assert response.status_code == 302
    assert calls == [{
        "actor_employee_id": 10, "manager_employee_id": 25, "team_id": 8,
    }]


def test_directory_page_renders_scoped_records_and_roles(monkeypatch):
    from itoms.web import directory_admin as directory_web

    app = _app_with_identity()
    monkeypatch.setattr(directory_web, "has_permission", lambda *_: True)
    monkeypatch.setattr(directory_web, "list_directory", lambda **_: {
        "department_id": 7,
        "employees": [{
            "employee_id": 25, "employee_code": "E-25",
            "full_name": "Example Employee", "email": None,
            "job_title": "Engineer", "is_active": True,
        }],
        "teams": [{"team_id": 8, "team_name": "Platform", "is_active": True}],
        "memberships": [{
            "employee_id": 25, "team_id": 8, "is_primary": True,
            "team_name": "Platform", "full_name": "Example Employee",
        }],
        "managers": [],
        "roles": [{"role_id": 4, "role_name": "Team Operator"}],
        "role_assignments": [{
            "assignment_id": 12, "employee_id": 25,
            "full_name": "Example Employee", "role_id": 4,
            "role_name": "Team Operator", "scope_type": "DEPARTMENT",
            "scope_reference": "7", "expires_at": None,
        }],
    })
    response = app.test_client().get("/admin/directory/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Example Employee" in body
    assert "Platform" in body
    assert "Team Operator" in body
    assert "Assign role" in body
