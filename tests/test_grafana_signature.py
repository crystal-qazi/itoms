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
