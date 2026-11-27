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

MAX_GRAFANA_WEBHOOK_BODY_BYTES = 1024 * 1024
MAX_GRAFANA_ALERTS_PER_REQUEST = 100
MAX_GRAFANA_EVENT_ID_LENGTH = 190
MAX_GRAFANA_DESCRIPTION_LENGTH = 20000


@grafana_bp.post("/webhook")
def webhook():
    raw_body = request.get_data(cache=True)
    if len(raw_body) > MAX_GRAFANA_WEBHOOK_BODY_BYTES:
        return jsonify({"error": "Webhook payload is too large"}), 413
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
    if len(alerts) > MAX_GRAFANA_ALERTS_PER_REQUEST:
        return jsonify({"error": "Too many alerts in one webhook request"}), 413

    # Validate the complete payload before creating any tickets, so a malformed
    # later alert cannot leave an unexpectedly partial batch behind.
    firing_alerts = []
    ignored = 0
    for alert in alerts:
        if not isinstance(alert, dict):
            return jsonify({"error": "Invalid alert item"}), 400
        state = alert.get("status", "")
        if not isinstance(state, str):
            return jsonify({"error": "Alert status must be a string"}), 400
        if state.lower() != "firing":
            # A resolved alert must never auto-resolve or close an incident.
            ignored += 1
            continue
        labels = alert.get("labels") if isinstance(alert.get("labels"), dict) else {}
        annotations = alert.get("annotations") if isinstance(alert.get("annotations"), dict) else {}
        fingerprint = alert.get("fingerprint")
        starts_at = alert.get("startsAt")
        if not isinstance(fingerprint, str) or not isinstance(starts_at, str):
            return jsonify({"error": "Firing alert requires fingerprint and startsAt strings"}), 400
        fingerprint, starts_at = fingerprint.strip(), starts_at.strip()
        if not fingerprint or not starts_at:
            return jsonify({"error": "Firing alert requires fingerprint and startsAt"}), 400
        event_id = f"{fingerprint}:{starts_at}"
        if len(event_id) > MAX_GRAFANA_EVENT_ID_LENGTH:
            return jsonify({"error": "Firing alert event identity is too long"}), 400
        title = str(annotations.get("summary") or labels.get("alertname") or "Grafana alert").strip()[:240]
        description = str(annotations.get("description") or annotations.get("summary") or title).strip()
        if not description or len(description) > MAX_GRAFANA_DESCRIPTION_LENGTH:
            return jsonify({"error": "Alert description must be non-empty and at most 20,000 characters"}), 400
        severity = str(labels.get("severity", "warning")).lower()
        priority = {"critical": "CRITICAL", "error": "HIGH", "warning": "MEDIUM", "info": "LOW"}.get(severity, "MEDIUM")
        firing_alerts.append((event_id, title, description, priority))

    created, duplicates = [], 0
    for event_id, title, description, priority in firing_alerts:
        try:
            ticket_id = create_incident(
                actor_employee_id=service_employee_id, title=title, description=description,
                priority=priority, requester_employee_id=service_employee_id,
                source="GRAFANA", external_source="GRAFANA", external_event_id=event_id,
            )
            created.append(ticket_id)
        except IntegrityError:
            # Treat only an existing matching external identity as a duplicate;
            # other integrity failures must not be silently acknowledged.
            from itoms.db.connection import get_connection
            conn = get_connection()
            cur = conn.cursor()
            try:
                cur.execute("""SELECT ticket_id FROM incident_tickets
                    WHERE external_source='GRAFANA' AND external_event_id=%s""", (event_id,))
                duplicate = cur.fetchone()
            finally:
                cur.close()
                conn.close()
            if duplicate:
                duplicates += 1
            else:
                current_app.logger.exception("Grafana incident insert failed integrity validation")
                return jsonify({"error": "Incident could not be created"}), 500
        except IncidentError as exc:
            current_app.logger.warning("Grafana incident rejected: %s", exc)
            return jsonify({"error": "Incident could not be created"}), 403
    return jsonify({"created_ticket_ids": created, "ignored_non_firing": ignored,
                    "duplicate_events": duplicates}), 202
