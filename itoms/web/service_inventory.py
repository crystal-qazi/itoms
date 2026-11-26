"""Service inventory queue and lifecycle routes."""
from __future__ import annotations
import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from itoms.security.decorators import login_required
from itoms.services.service_inventory import (ServiceInventoryError, SERVICE_STATUSES, create_service_record, list_service_records, list_service_teams, update_service_lifecycle)

service_inventory_bp = Blueprint("service_inventory", __name__, url_prefix="/services")

@service_inventory_bp.get("/")
@login_required
def index():
    status = request.args.get("status", "").strip().upper() or None
    teams = list_service_teams(actor_employee_id=g.employee_id)
    create_teams = list_service_teams(actor_employee_id=g.employee_id, permission_key="service.inventory.create")
    records = list_service_records(actor_employee_id=g.employee_id, lifecycle_status=status)
    return render_template("service_inventory/index.html", records=records, teams=teams, create_teams=create_teams, statuses=sorted(SERVICE_STATUSES), selected_status=status or "", csrf_token_value=session.get("csrf_token", ""))

@service_inventory_bp.post("/")
@login_required
def create():
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))): return "Invalid request token", 400
    try:
        service_id = create_service_record(actor_employee_id=g.employee_id, service_key=request.form.get("service_key", ""), service_name=request.form.get("service_name", ""), service_type=request.form.get("service_type", ""), owner_team_id=int(request.form.get("owner_team_id", "")), criticality=request.form.get("criticality", "MEDIUM"), description=request.form.get("description", ""))
    except (ValueError, TypeError, ServiceInventoryError) as exc:
        flash(str(exc) or "Invalid service details.", "danger")
        return redirect(url_for("service_inventory.index"))
    flash("Service registered.", "success")
    return redirect(url_for("service_inventory.index"))

@service_inventory_bp.post("/<int:service_id>/lifecycle")
@login_required
def lifecycle(service_id: int):
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))): return "Invalid request token", 400
    try:
        update_service_lifecycle(actor_employee_id=g.employee_id, service_id=service_id, lifecycle_status=request.form.get("lifecycle_status", "").strip().upper())
        flash("Service lifecycle updated.", "success")
    except ServiceInventoryError as exc: flash(str(exc), "danger")
    return redirect(url_for("service_inventory.index"))