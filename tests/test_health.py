"""Basic application smoke tests."""
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


def test_health_endpoint() -> None:
    app = create_app(TestConfig)
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "ok", "application": "ITOMS"}
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_app_factory_accepts_test_configuration() -> None:
    app = create_app(TestConfig)
    assert app.config["TESTING"] is True


def test_engineering_task_blueprint_is_registered() -> None:
    app = create_app(TestConfig)
    assert "engineering_tasks.index" in app.view_functions
    assert "engineering_tasks.create" in app.view_functions
    assert "engineering_tasks.detail" in app.view_functions
    assert "engineering_tasks.update_status" in app.view_functions


def test_service_inventory_blueprint_is_registered() -> None:
    app = create_app(TestConfig)
    assert "service_inventory.index" in app.view_functions
    assert "service_inventory.create" in app.view_functions
    assert "service_inventory.lifecycle" in app.view_functions


def test_notifications_blueprint_is_registered() -> None:
    app = create_app(TestConfig)
    assert "notifications.index" in app.view_functions
    assert "notifications.read" in app.view_functions


def test_change_management_blueprint_is_registered() -> None:
    app = create_app(TestConfig)
    assert "changes.index" in app.view_functions
    assert "changes.create" in app.view_functions
    assert "changes.detail" in app.view_functions
    assert "changes.status" in app.view_functions


def test_release_management_blueprint_is_registered() -> None:
    app = create_app(TestConfig)
    assert "releases.index" in app.view_functions
    assert "releases.create" in app.view_functions
    assert "releases.status" in app.view_functions


def test_approval_inbox_blueprint_is_registered() -> None:
    app = create_app(TestConfig)
    assert "approvals.inbox" in app.view_functions
    assert "approvals.decision" in app.view_functions



def test_service_worker_is_root_scoped_and_shell_only() -> None:
    app = create_app(TestConfig)
    response = app.test_client().get("/service-worker.js")
    assert response.status_code == 200
    assert response.headers["Service-Worker-Allowed"] == "/"
    assert response.mimetype == "application/javascript"
    body = response.get_data(as_text=True)
    assert "/static/css/app.css" in body
    assert "/static/vendor/bootstrap/js/bootstrap.bundle.min.js" in body
    assert "request.method !== \"GET\"" in body
    assert "SHELL_ASSETS.includes(url.pathname)" in body


def test_pwa_manifest_is_served() -> None:
    app = create_app(TestConfig)
    response = app.test_client().get("/static/manifest.webmanifest")
    assert response.status_code == 200
    assert response.json["name"].startswith("ITOMS")
    assert response.json["display"] == "standalone"
    assert response.json["scope"] == "/"
