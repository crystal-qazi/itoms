"""Grafana webhook receiver with timestamped HMAC validation and idempotency."""
from __future__ import annotations
import hashlib
import hmac
import json
import time
from flask import Blueprint, current_app, jsonify, request
from mysql.connector import IntegrityError
from itoms.services.incidents import create_incident, IncidentError

grafana_bp = Blueprint("grafana", __name__, url_prefix="/integrations/grafana")

def _valid_signature(raw_body: bytes) -> bool:
    secret = current_app.config.get("GRAFANA_WEBHOOK_SECRET")
    timestamp = request.headers.get("X-ITOMS-Timestamp", "")
    supplied = request.headers.get("X-ITOMS-Signature", "")
    if not secret or not timestamp.isdigit() or len(timestamp) > 12:
        return False
    if abs(int(time.time()) - int(timestamp)) > 300:
        return False
    signed = timestamp.encode("ascii") + b"." + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)

@grafana_bp.post("/webhook")
def webhook():
    raw_body = request.get_data(cache=True)
    if not _valid_signature(raw_body):
        return jsonify({"error": "Unauthorized"}), 401
    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return jsonify({"error": "Invalid JSON"}), 400
    service_employee_id = current_app.config.get("GRAFANA_SERVICE_EMPLOYEE_ID", 0)
    if not service_employee_id:
        return jsonify({"error": "Integration service identity is not configured"}), 503
    alerts = payload.get("alerts") if isinstance(payload, dict) else None
    if not isinstance(alerts, list):
        return jsonify({"error": "Expected Grafana alerts array"}), 400
    created, ignored, duplicates = [], 0, 0
    for alert in alerts:
        if not isinstance(alert, dict):
            return jsonify({"error": "Invalid alert item"}), 400
        state = str(alert.get("status", "")).lower()
        if state != "firing":
            # A resolved alert must never auto-resolve or close an incident.
            ignored += 1
            continue
        labels = alert.get("labels") if isinstance(alert.get("labels"), dict) else {}
        annotations = alert.get("annotations") if isinstance(alert.get("annotations"), dict) else {}
        fingerprint = str(alert.get("fingerprint", "")).strip()
        starts_at = str(alert.get("startsAt", "")).strip()
        if not fingerprint or not starts_at:
            return jsonify({"error": "Firing alert requires fingerprint and startsAt"}), 400
        event_id = f"{fingerprint}:{starts_at}"
        title = str(annotations.get("summary") or labels.get("alertname") or "Grafana alert")[:240]
        description = str(annotations.get("description") or alert.get("annotations", {}).get("summary") or title)
        severity = str(labels.get("severity", "warning")).lower()
        priority = {"critical": "CRITICAL", "error": "HIGH", "warning": "MEDIUM", "info": "LOW"}.get(severity, "MEDIUM")
        try:
            ticket_id = create_incident(
                actor_employee_id=service_employee_id, title=title, description=description,
                priority=priority, requester_employee_id=service_employee_id,
                source="GRAFANA", external_source="GRAFANA", external_event_id=event_id,
            )
            created.append(ticket_id)
        except IntegrityError:
            duplicates += 1
        except IncidentError as exc:
            current_app.logger.warning("Grafana incident rejected: %s", exc)
            return jsonify({"error": "Incident could not be created"}), 403
    return jsonify({"created_ticket_ids": created, "ignored_non_firing": ignored,
                    "duplicate_events": duplicates}), 202
