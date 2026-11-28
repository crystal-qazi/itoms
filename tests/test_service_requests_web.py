"""HTTP boundary tests for Service Request administration and search."""
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


def _mock_index_dependencies(monkeypatch, web):
    monkeypatch.setattr(web, "has_permission", lambda *_: True)
    monkeypatch.setattr(web, "list_requests", lambda **_: [])
    monkeypatch.setattr(web, "list_categories", lambda: [])
    monkeypatch.setattr(web, "list_category_admin", lambda **_: [])
    monkeypatch.setattr(web, "list_priorities", lambda: [
        {"priority_key": "NORMAL", "priority_label": "Normal", "sort_order": 10, "is_active": True},
    ])
    monkeypatch.setattr(web, "list_priority_admin", lambda **_: [
        {"priority_key": "NORMAL", "priority_label": "Normal", "sort_order": 10, "is_active": True},
    ])


def test_priority_admin_page_renders_labeled_controls_and_search(monkeypatch):
    from itoms.web import service_requests as web

    app = _app_with_identity()
    _mock_index_dependencies(monkeypatch, web)
    response = app.test_client().get("/service-requests/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Priority administration" in body
    assert 'for="priority-key"' in body
    assert 'for="priority-label"' in body
    assert 'for="sr-search"' in body


def test_priority_create_route_rejects_missing_csrf(monkeypatch):
    from itoms.web import service_requests as web

    app = _app_with_identity()
    monkeypatch.setattr(
        web, "create_priority",
        lambda **_: pytest.fail("priority creation must not run without CSRF"),
    )
    response = app.test_client().post("/service-requests/priorities", data={
        "priority_key": "URGENT", "priority_label": "Urgent", "sort_order": "5",
    })
    assert response.status_code == 400


def test_priority_create_route_passes_validated_values(monkeypatch):
    from itoms.web import service_requests as web

    app = _app_with_identity()
    calls = []
    monkeypatch.setattr(web, "create_priority", lambda **kwargs: calls.append(kwargs) or "URGENT")
    client = app.test_client()
    with client.session_transaction() as state:
        state["csrf_token"] = "expected-token"
    response = client.post("/service-requests/priorities", data={
        "csrf_token": "expected-token", "priority_key": "urgent",
        "priority_label": "Urgent", "sort_order": "5",
    })
    assert response.status_code == 302
    assert calls == [{
        "actor_employee_id": 10, "priority_key": "urgent",
        "priority_label": "Urgent", "sort_order": 5,
    }]


def test_priority_update_route_passes_active_state(monkeypatch):
    from itoms.web import service_requests as web

    app = _app_with_identity()
    calls = []
    monkeypatch.setattr(web, "update_priority", lambda **kwargs: calls.append(kwargs) or True)
    client = app.test_client()
    with client.session_transaction() as state:
        state["csrf_token"] = "expected-token"
    response = client.post("/service-requests/priorities/URGENT/update", data={
        "csrf_token": "expected-token", "priority_label": "Urgent",
        "sort_order": "5", "is_active": "0",
    })
    assert response.status_code == 302
    assert calls == [{
        "actor_employee_id": 10, "priority_key": "URGENT",
        "priority_label": "Urgent", "sort_order": 5, "is_active": False,
    }]


def test_advanced_search_route_passes_filters_and_visible_page_offset(monkeypatch):
    from itoms.web import service_requests as web

    app = _app_with_identity()
    calls = []
    _mock_index_dependencies(monkeypatch, web)
    monkeypatch.setattr(web, "list_requests", lambda **kwargs: calls.append(kwargs) or [])
    response = app.test_client().get(
        "/service-requests/?search=VPN&category_id=7&status=OPEN&priority=NORMAL"
        "&created_from=2026-11-01&created_to=2026-11-28&page=2"
    )
    assert response.status_code == 200
    assert calls == [{
        "actor_employee_id": 10, "status": "OPEN", "priority": "NORMAL",
        "search": "VPN", "category_id": 7, "created_from": "2026-11-01",
        "created_to": "2026-11-28", "visible_offset": 25, "limit": 26,
    }]
    assert "Page 2" in response.get_data(as_text=True)

def test_every_service_request_mutation_route_rejects_missing_csrf(monkeypatch):
    from itoms.web import service_requests as web

    app = _app_with_identity()
    for name in (
        "create_request", "create_category", "set_category_active", "assign_request",
        "transition_request", "add_comment", "create_priority", "update_priority",
    ):
        monkeypatch.setattr(
            web, name,
            lambda _name=name, **_: pytest.fail(f"{_name} must not run without CSRF"),
        )
    client = app.test_client()
    paths = (
        ("/service-requests/", {}),
        ("/service-requests/categories", {}),
        ("/service-requests/categories/7/active", {"is_active": "1"}),
        ("/service-requests/7/assignment", {}),
        ("/service-requests/7/status", {"status": "ON_HOLD"}),
        ("/service-requests/7/comments", {"body": "test"}),
        ("/service-requests/priorities", {"priority_key": "URGENT", "priority_label": "Urgent"}),
        ("/service-requests/priorities/URGENT/update", {"priority_label": "Urgent"}),
    )
    for path, data in paths:
        response = client.post(path, data=data)
        assert response.status_code == 400, path


def test_service_request_index_requires_login():
    app = create_app(TestConfig)
    response = app.test_client().get("/service-requests/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

