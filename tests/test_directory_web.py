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


def test_directory_blueprint_is_registered():
    app = _app_with_identity()
    assert "directory.index" in app.view_functions
    assert "directory.create_employee" in app.view_functions
    assert "directory.membership" in app.view_functions
    assert "directory.manager_assignment" in app.view_functions


def test_directory_page_denies_missing_permission(monkeypatch):
    from itoms.web import directory as directory_web

    app = _app_with_identity()
    monkeypatch.setattr(directory_web, "has_permission", lambda *_: False)
    response = app.test_client().get("/admin/directory/")
    assert response.status_code == 403


def test_directory_mutation_rejects_missing_csrf(monkeypatch):
    from itoms.web import directory as directory_web

    app = _app_with_identity()
    monkeypatch.setattr(directory_web, "create_directory_employee", lambda **_: pytest.fail("must not write"))
    client = app.test_client()
    with client.session_transaction() as state:
        state["csrf_token"] = "expected-token"
    response = client.post("/admin/directory/employees", data={
        "employee_code": "E-1", "full_name": "Example", "username": "example",
        "initial_password": "NotARealPassword123!",
    })
    assert response.status_code == 400
