"""Unit validation for notification outbox processing and recovery."""
import pytest

from itoms.services import notifications


def test_process_in_app_batch_only_completes_claimed_items(monkeypatch):
    monkeypatch.setattr(
        notifications, "claim_outbox_batch",
        lambda **kwargs: [{"outbox_id": 10}, {"outbox_id": 11}],
    )
    completed = []
    monkeypatch.setattr(
        notifications, "complete_outbox_item",
        lambda **kwargs: completed.append(kwargs),
    )
    assert notifications.process_in_app_outbox_batch(batch_size=2) == 2
    assert [item["outbox_id"] for item in completed] == [10, 11]
    assert all(item["success"] is True for item in completed)


def test_dead_letter_replay_requires_permission_before_database(monkeypatch):
    monkeypatch.setattr(notifications, "has_permission", lambda *_: False)
    monkeypatch.setattr(
        notifications, "get_connection",
        lambda: pytest.fail("database must not be opened for unauthorized replay"),
    )
    with pytest.raises(notifications.NotificationError, match="Not authorized"):
        notifications.replay_dead_letter(actor_employee_id=1, outbox_id=10)


def test_email_outbox_requires_secure_smtp_before_claim(monkeypatch):
    from flask import Flask
    app = Flask(__name__)
    app.config.update(SMTP_HOST="mail.example.invalid", SMTP_FROM="itoms@example.invalid",
                      SMTP_USE_STARTTLS=False, SMTP_USE_SSL=False)
    monkeypatch.setattr(
        notifications, "claim_outbox_batch",
        lambda **kwargs: pytest.fail("unconfigured SMTP must not claim queued email"),
    )
    with app.app_context():
        with pytest.raises(notifications.NotificationError, match="secure SMTP mode"):
            notifications.process_email_outbox_batch()


def test_email_outbox_delivers_and_completes_claimed_rows(monkeypatch):
    from flask import Flask
    app = Flask(__name__)
    app.config.update(SMTP_HOST="mail.example.invalid", SMTP_FROM="itoms@example.invalid",
                      SMTP_USE_STARTTLS=True, SMTP_USE_SSL=False)
    claimed = [{"outbox_id": 21, "notification_id": 9, "channel": "EMAIL"}]
    sent = []
    completed = []
    monkeypatch.setattr(notifications, "claim_outbox_batch", lambda **kwargs: claimed)
    monkeypatch.setattr(notifications, "_send_notification_email", lambda notification_id: sent.append(notification_id))
    monkeypatch.setattr(notifications, "complete_outbox_item", lambda **kwargs: completed.append(kwargs))
    with app.app_context():
        assert notifications.process_email_outbox_batch(batch_size=1) == 1
    assert sent == [9]
    assert completed == [{"outbox_id": 21, "success": True}]


def test_notification_rejects_unsupported_channel_before_database(monkeypatch):
    monkeypatch.setattr(notifications, "has_permission", lambda *_: True)
    monkeypatch.setattr(
        notifications, "get_connection",
        lambda: pytest.fail("database must not be opened for an unsupported channel"),
    )
    with pytest.raises(notifications.NotificationError, match="Unsupported"):
        notifications.create_notification(
            actor_employee_id=1, recipient_employee_id=2,
            notification_type="TEST", title="Title", body="Body", channels=("SMS",),
        )


def test_email_address_validation_rejects_header_injection_and_malformed_values():
    assert notifications._valid_email_address("itoms@example.invalid")
    assert not notifications._valid_email_address("itoms@example.invalid\r\nBcc: attacker@example.invalid")
    assert not notifications._valid_email_address("missing-domain@")
    assert not notifications._valid_email_address("two@@example.invalid")


def test_smtp_sender_uses_starttls_and_plain_text(monkeypatch):
    from flask import Flask

    captured = {}

    class Cursor:
        def execute(self, *_args, **_kwargs):
            return None
        def fetchone(self):
            return ("recipient@example.invalid", "A subject", "Plain text body")
        def close(self):
            return None

    class Connection:
        def cursor(self):
            return Cursor()
        def close(self):
            return None

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            captured["connection"] = (host, port, timeout)
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return None
        def ehlo(self):
            captured["ehlo"] = captured.get("ehlo", 0) + 1
        def starttls(self, context):
            captured["tls"] = context
        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr(notifications, "get_connection", lambda: Connection())
    monkeypatch.setattr(notifications.smtplib, "SMTP", FakeSMTP)
    app = Flask(__name__)
    app.config.update(
        SMTP_HOST="mail.example.invalid", SMTP_PORT=587,
        SMTP_FROM="itoms@example.invalid", SMTP_USE_STARTTLS=True,
        SMTP_USE_SSL=False, SMTP_TIMEOUT=10,
    )
    with app.app_context():
        notifications._send_notification_email(99)
    assert captured["connection"] == ("mail.example.invalid", 587, 10.0)
    assert captured["ehlo"] == 2
    assert captured["tls"] is not None
    assert captured["message"]["To"] == "recipient@example.invalid"
    assert captured["message"]["Subject"] == "A subject"
    assert captured["message"].get_content().strip() == "Plain text body"


def test_email_delivery_failure_is_retried_through_outbox_policy(monkeypatch):
    from flask import Flask
    app = Flask(__name__)
    app.config.update(
        SMTP_HOST="mail.example.invalid", SMTP_FROM="itoms@example.invalid",
        SMTP_USE_STARTTLS=True, SMTP_USE_SSL=False,
    )
    monkeypatch.setattr(
        notifications, "claim_outbox_batch",
        lambda **kwargs: [{"outbox_id": 22, "notification_id": 10, "channel": "EMAIL"}],
    )
    monkeypatch.setattr(
        notifications, "_send_notification_email",
        lambda _notification_id: (_ for _ in ()).throw(OSError("connection details must not leak")),
    )
    completed = []
    monkeypatch.setattr(
        notifications, "complete_outbox_item",
        lambda **kwargs: completed.append(kwargs),
    )
    with app.app_context():
        assert notifications.process_email_outbox_batch() == 0
    assert completed == [{
        "outbox_id": 22, "success": False,
        "error": "SMTP delivery failed (OSError).",
    }]
