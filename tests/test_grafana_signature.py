"""Tests for Grafana webhook signature validation."""
import hashlib
import hmac
import time
from flask import Flask
from itoms.web.grafana import _valid_signature

def test_grafana_signature_accepts_valid_recent_payload():
    app = Flask(__name__)
    app.config["GRAFANA_WEBHOOK_SECRET"] = "test-secret"
    body = b'{"alerts":[]}'
    timestamp = str(int(time.time()))
    signature = hmac.new(b"test-secret", timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    with app.test_request_context(
        "/integrations/grafana/webhook",
        headers={"X-ITOMS-Timestamp": timestamp, "X-ITOMS-Signature": signature},
        data=body,
    ):
        assert _valid_signature(body)

def test_grafana_signature_rejects_stale_timestamp():
    app = Flask(__name__)
    app.config["GRAFANA_WEBHOOK_SECRET"] = "test-secret"
    body = b'{"alerts":[]}'
    timestamp = str(int(time.time()) - 600)
    signature = hmac.new(b"test-secret", timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    with app.test_request_context(
        "/integrations/grafana/webhook",
        headers={"X-ITOMS-Timestamp": timestamp, "X-ITOMS-Signature": signature},
        data=body,
    ):
        assert not _valid_signature(body)

def _signed_client(monkeypatch, payload, create_stub):
    import json
    from flask import Flask
    from itoms.web import grafana

    monkeypatch.setattr(grafana, "create_incident", create_stub)
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        GRAFANA_WEBHOOK_SECRET="test-secret",
        GRAFANA_SERVICE_EMPLOYEE_ID=9001,
        MAX_CONTENT_LENGTH=1024 * 1024,
    )
    app.register_blueprint(grafana.grafana_bp)
    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = hmac.new(
        b"test-secret", timestamp.encode("ascii") + b"." + body, hashlib.sha256
    ).hexdigest()
    return app.test_client().post(
        "/integrations/grafana/webhook",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-ITOMS-Timestamp": timestamp,
            "X-ITOMS-Signature": signature,
        },
    )


def test_grafana_webhook_handles_malformed_annotations_without_partial_failure(monkeypatch):
    created = []

    def create_stub(**kwargs):
        created.append(kwargs)
        return 77

    response = _signed_client(monkeypatch, {
        "alerts": [{
            "status": "firing",
            "fingerprint": "fp-123",
            "startsAt": "2026-11-27T08:00:00Z",
            "labels": {"alertname": "DiskFull"},
            "annotations": ["malformed", "but ignored safely"],
        }]
    }, create_stub)

    assert response.status_code == 202
    assert created[0]["title"] == "DiskFull"
    assert created[0]["description"] == "DiskFull"


def test_grafana_webhook_rejects_overlong_event_identity_before_creating(monkeypatch):
    created = []
    response = _signed_client(monkeypatch, {
        "alerts": [{
            "status": "firing",
            "fingerprint": "f" * 170,
            "startsAt": "2026-11-27T08:00:00Z",
            "labels": {"alertname": "DiskFull"},
            "annotations": {},
        }]
    }, lambda **kwargs: created.append(kwargs) or 88)

    assert response.status_code == 400
    assert created == []


def test_grafana_webhook_rejects_oversized_alert_batch_before_creating(monkeypatch):
    created = []
    response = _signed_client(monkeypatch, {
        "alerts": [{"status": "resolved"}] * 101
    }, lambda **kwargs: created.append(kwargs) or 99)

    assert response.status_code == 413
    assert created == []

