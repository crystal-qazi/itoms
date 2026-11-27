"""Authenticated routes remain blocked until MFA enrollment is verified."""
from itoms import create_app


class TestConfig:
    SECRET_KEY = "testing-key"
    TESTING = True
    LOG_LEVEL = "CRITICAL"

    @classmethod
    def validate(cls, config):
        return None


def test_unenrolled_account_is_redirected_to_mfa(monkeypatch):
    from itoms.services import auth as auth_service
    from itoms.web import auth as auth_web

    monkeypatch.setattr(auth_service, "validate_session", lambda token: (12, 34, False))
    monkeypatch.setattr(auth_web, "get_pending_totp_enrollment", lambda account_id: None)
    app = create_app(TestConfig)
    client = app.test_client()
    with client.session_transaction() as state:
        state["server_session_token"] = "valid-test-token"
        state["account_id"] = 12
        state["must_change_password"] = False

    response = client.get("/auth/home")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/mfa/enroll")
    assert client.get("/auth/mfa/enroll").status_code == 200


def test_password_change_precedes_mfa_enrollment(monkeypatch):
    from itoms.services import auth as auth_service

    monkeypatch.setattr(auth_service, "validate_session", lambda token: (12, 34, False))
    app = create_app(TestConfig)
    client = app.test_client()
    with client.session_transaction() as state:
        state["server_session_token"] = "valid-test-token"
        state["account_id"] = 12
        state["must_change_password"] = True

    response = client.get("/auth/home")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/change-password")
    assert client.get("/auth/change-password").status_code == 200
