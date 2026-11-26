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
