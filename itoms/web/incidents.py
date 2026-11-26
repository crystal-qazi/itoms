"""Authenticated Helpdesk incident queue and creation routes."""
from __future__ import annotations
import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.incidents import (IncidentError, add_comment, create_incident, get_incident_detail, list_incidents, transition_incident)

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

@incidents_bp.get("/<int:ticket_id>")
@login_required
def detail(ticket_id: int):
    try:
        ticket = get_incident_detail(actor_employee_id=g.employee_id, ticket_id=ticket_id)
    except IncidentError:
        return "Incident not found.", 404
    return render_template("incidents/detail.html", ticket=ticket,
                           csrf_token_value=session.get("csrf_token", ""))

@incidents_bp.post("/<int:ticket_id>/status")
@login_required
def update_status(ticket_id: int):
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))):
        return "Invalid request token", 400
    try:
        transition_incident(actor_employee_id=g.employee_id, ticket_id=ticket_id,
                            new_status=request.form.get("status", ""))
    except IncidentError as exc:
        flash(str(exc), "danger")
    else:
        flash("Incident status updated.", "success")
    return redirect(url_for("incidents.detail", ticket_id=ticket_id))

@incidents_bp.post("/<int:ticket_id>/comments")
@login_required
def comment(ticket_id: int):
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))):
        return "Invalid request token", 400
    internal = request.form.get("visibility") == "internal"
    try:
        add_comment(actor_employee_id=g.employee_id, ticket_id=ticket_id,
                    body=request.form.get("body", ""), internal=internal)
    except IncidentError as exc:
        flash(str(exc), "danger")
    else:
        flash("Comment added.", "success")
    return redirect(url_for("incidents.detail", ticket_id=ticket_id))
