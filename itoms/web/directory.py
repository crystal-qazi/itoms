"""Department-scoped employee directory administration routes."""
from __future__ import annotations

import hmac

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.directory_admin import (
    DirectoryAdministrationError, assign_team_manager, assign_team_membership,
    create_directory_employee, list_directory, remove_team_manager,
    remove_team_membership,
)

directory_bp = Blueprint("directory", __name__, url_prefix="/admin/directory")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@directory_bp.get("/")
@login_required
def index():
    if not has_permission(g.employee_id, "identity.directory.manage"):
        abort(403)
    try:
        data = list_directory(actor_employee_id=g.employee_id)
    except DirectoryAdministrationError:
        abort(403)
    return render_template(
        "admin/directory.html",
        **data,
        can_create_accounts=has_permission(g.employee_id, "identity.accounts.create"),
        csrf_token_value=session.get("csrf_token", ""),
    )


@directory_bp.post("/employees")
@login_required
def create_employee():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        primary_team = request.form.get("primary_team_id", "").strip()
        employee_id = create_directory_employee(
            actor_employee_id=g.employee_id,
            employee_code=request.form.get("employee_code", ""),
            full_name=request.form.get("full_name", ""),
            username=request.form.get("username", ""),
            initial_password=request.form.get("initial_password", ""),
            email=request.form.get("email", "").strip() or None,
            job_title=request.form.get("job_title", "").strip() or None,
            primary_team_id=int(primary_team) if primary_team else None,
        )
        flash(f"Employee account created (employee ID {employee_id}).", "success")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid employee details.", "danger")
    return redirect(url_for("directory.index"))


@directory_bp.post("/employees/<int:employee_id>/memberships")
@login_required
def membership(employee_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        team_id = int(request.form.get("team_id", ""))
        action = request.form.get("action", "").strip().lower()
        if action == "assign":
            assign_team_membership(
                actor_employee_id=g.employee_id, employee_id=employee_id,
                team_id=team_id, primary=request.form.get("is_primary") == "1",
            )
            flash("Team membership saved.", "success")
        elif action == "remove":
            remove_team_membership(
                actor_employee_id=g.employee_id, employee_id=employee_id, team_id=team_id,
            )
            flash("Team membership removed.", "success")
        else:
            raise DirectoryAdministrationError("Select a valid membership action.")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid team membership request.", "danger")
    return redirect(url_for("directory.index"))


@directory_bp.post("/managers")
@directory_bp.post("/employees/<int:employee_id>/manager")
@login_required
def manager_assignment(employee_id: int | None = None):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        team_id = int(request.form.get("team_id", ""))
        action = request.form.get("action", "").strip().lower()
        target_employee_id = (
            int(request.form.get("manager_employee_id", "")) if action == "assign"
            else employee_id
        )
        if not target_employee_id:
            raise DirectoryAdministrationError("Select a valid manager employee.")
        if action == "assign":
            changed = assign_team_manager(
                actor_employee_id=g.employee_id, manager_employee_id=target_employee_id,
                team_id=team_id,
            )
            flash("Team manager assigned." if changed else "Manager assignment already exists.", "success")
        elif action == "remove":
            changed = remove_team_manager(
                actor_employee_id=g.employee_id, manager_employee_id=target_employee_id,
                team_id=team_id,
            )
            flash("Team manager assignment removed." if changed else "Manager assignment was already absent.", "success")
        else:
            raise DirectoryAdministrationError("Select a valid manager action.")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid manager assignment request.", "danger")
    return redirect(url_for("directory.index"))
