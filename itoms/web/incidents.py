"""Authenticated Helpdesk incident queue and creation routes."""
from __future__ import annotations
import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.incidents import IncidentError, create_incident, list_incidents

incidents_bp = Blueprint("incidents", __name__, url_prefix="/incidents")

@incidents_bp.get("/")
@login_required
def index():
    rows = list_incidents(actor_employee_id=g.employee_id)
    can_create = has_permission(g.employee_id, "incident.create")
    return render_template("incidents/index.html", incidents=rows, can_create=can_create,
                           csrf_token_value=session.get("csrf_token", ""))

@incidents_bp.post("/")
@login_required
def create():
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))):
        return "Invalid request token", 400
    try:
        ticket_id = create_incident(
            actor_employee_id=g.employee_id,
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            priority=request.form.get("priority", "MEDIUM"),
        )
    except IncidentError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("incidents.index"))
    flash("Incident created successfully.", "success")
    return redirect(url_for("incidents.index"))
