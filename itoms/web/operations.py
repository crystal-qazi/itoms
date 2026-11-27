"""Network, infrastructure and Oracle operations routes."""
from __future__ import annotations

import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.operations import (
    DOMAINS, ORACLE_LIFECYCLE, PRIORITIES, WORK_STATUSES, OperationsError,
    create_operational_work_item, create_oracle_database, list_operation_teams,
    list_operational_work_items, list_oracle_databases, update_oracle_lifecycle,
    update_work_status,
)

operations_bp = Blueprint("operations", __name__, url_prefix="/operations")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@operations_bp.get("/")
@login_required
def index():
    domain = request.args.get("domain", "").strip().upper() or None
    status = request.args.get("status", "").strip().upper() or None
    try:
        work_items = list_operational_work_items(
            actor_employee_id=g.employee_id, domain=domain, status=status,
        )
    except OperationsError:
        return "Invalid operations filter.", 400
    teams = list_operation_teams(actor_employee_id=g.employee_id)
    oracle_rows = list_oracle_databases(actor_employee_id=g.employee_id)
    return render_template(
        "operations/index.html", work_items=work_items, teams=teams,
        oracle_rows=oracle_rows, domains=sorted(DOMAINS), priorities=sorted(PRIORITIES),
        work_statuses=sorted(WORK_STATUSES), oracle_lifecycle=sorted(ORACLE_LIFECYCLE),
        selected_domain=domain or "", selected_status=status or "",
        csrf_token_value=session.get("csrf_token", ""),
    )


@operations_bp.post("/work")
@login_required
def work_create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_operational_work_item(
            actor_employee_id=g.employee_id,
            domain=request.form.get("domain", ""),
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            owner_team_id=int(request.form.get("owner_team_id", "")),
            priority=request.form.get("priority", "MEDIUM"),
            external_reference=request.form.get("external_reference", ""),
        )
        flash("Operations work item created.", "success")
    except (OperationsError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid operations work item.", "danger")
    return redirect(url_for("operations.index"))


@operations_bp.post("/work/<int:work_item_id>/status")
@login_required
def work_status(work_item_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        update_work_status(
            actor_employee_id=g.employee_id, work_item_id=work_item_id,
            new_status=request.form.get("status", "").strip().upper(),
        )
        flash("Operations work status updated.", "success")
    except OperationsError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("operations.index"))


@operations_bp.post("/oracle")
@login_required
def oracle_create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_oracle_database(
            actor_employee_id=g.employee_id,
            service_id=int(request.form.get("service_id", "")),
            environment_name=request.form.get("environment_name", ""),
            database_name=request.form.get("database_name", ""),
            host_reference=request.form.get("host_reference", ""),
            version_label=request.form.get("version_label", ""),
            criticality=request.form.get("criticality", "MEDIUM"),
            notes=request.form.get("notes", ""),
        )
        flash("Oracle database reference registered.", "success")
    except (OperationsError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid Oracle database details.", "danger")
    return redirect(url_for("operations.index"))


@operations_bp.post("/oracle/<int:oracle_database_id>/lifecycle")
@login_required
def oracle_lifecycle(oracle_database_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        update_oracle_lifecycle(
            actor_employee_id=g.employee_id, oracle_database_id=oracle_database_id,
            new_status=request.form.get("status", "").strip().upper(),
        )
        flash("Oracle database lifecycle updated.", "success")
    except OperationsError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("operations.index"))
