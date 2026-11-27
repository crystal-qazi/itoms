"""Employee directory administration routes."""
from __future__ import annotations

import hmac

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.authorization import ResourceContext, has_permission
from itoms.services.directory_admin import (
    DirectoryAdministrationError, assign_team_manager, assign_team_membership,
    create_directory_employee, create_team, deactivate_employee, list_directory,
    remove_team_manager, remove_team_membership, set_team_active,
)
from itoms.services.identity_admin import (
    IdentityAdministrationError, assign_role, revoke_role_assignment,
)

directory_admin_bp = Blueprint(
    "directory_admin", __name__, url_prefix="/admin/directory"
)


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    return bool(token) and hmac.compare_digest(
        str(token), str(request.form.get("csrf_token", ""))
    )


def _directory_redirect():
    return redirect(url_for("directory_admin.index"))


@directory_admin_bp.get("/")
@login_required
def index():
    try:
        data = list_directory(actor_employee_id=g.employee_id)
    except DirectoryAdministrationError:
        abort(403)
    department_context = ResourceContext(department_id=data["department_id"])
    return render_template(
        "admin/directory.html",
        **data,
        can_create=has_permission(g.employee_id, "identity.accounts.create", department_context),
        can_assign_roles=has_permission(g.employee_id, "identity.roles.assign", department_context),
        actor_employee_id=g.employee_id,
        csrf_token_value=session.get("csrf_token", ""),
    )


@directory_admin_bp.post("/teams")
@login_required
def create_team_route():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        team_id = create_team(
            actor_employee_id=g.employee_id,
            team_name=request.form.get("team_name", ""),
        )
        flash(f"Team created (team ID {team_id}).", "success")
    except (DirectoryAdministrationError, ValueError) as exc:
        flash(str(exc) or "Could not create team.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/teams/status")
@login_required
def update_team_status():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        changed = set_team_active(
            actor_employee_id=g.employee_id,
            team_id=int(request.form.get("team_id", "")),
            is_active=request.form.get("is_active") == "1",
        )
        flash("Team status updated." if changed else "Team status was already set.", "success")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not update team status.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/employees")
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
        flash(f"Employee account created (employee ID {employee_id}). First-login password change is required.", "success")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not create employee account.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/employees/deactivate")
@login_required
def deactivate_employee_route():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        changed = deactivate_employee(
            actor_employee_id=g.employee_id,
            employee_id=int(request.form.get("employee_id", "")),
        )
        flash("Employee account and all sessions disabled." if changed else "Employee was already inactive.", "success")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not deactivate employee.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/memberships")
@login_required
def assign_membership():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        assign_team_membership(
            actor_employee_id=g.employee_id,
            employee_id=int(request.form.get("employee_id", "")),
            team_id=int(request.form.get("team_id", "")),
            primary=request.form.get("primary") == "1",
        )
        flash("Team membership saved.", "success")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not update team membership.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/memberships/remove")
@login_required
def remove_membership():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        remove_team_membership(
            actor_employee_id=g.employee_id,
            employee_id=int(request.form.get("employee_id", "")),
            team_id=int(request.form.get("team_id", "")),
        )
        flash("Team membership removed.", "success")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not remove team membership.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/managers")
@login_required
def assign_manager():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        changed = assign_team_manager(
            actor_employee_id=g.employee_id,
            manager_employee_id=int(request.form.get("employee_id", "")),
            team_id=int(request.form.get("team_id", "")),
        )
        flash("Team manager assigned." if changed else "That manager is already assigned to the team.", "success")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not assign team manager.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/managers/remove")
@login_required
def remove_manager():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        changed = remove_team_manager(
            actor_employee_id=g.employee_id,
            manager_employee_id=int(request.form.get("employee_id", "")),
            team_id=int(request.form.get("team_id", "")),
        )
        flash("Team manager assignment removed." if changed else "That manager assignment was already absent.", "success")
    except (DirectoryAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not remove team manager.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/roles/revoke")
@login_required
def revoke_employee_role():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        changed = revoke_role_assignment(
            actor_employee_id=g.employee_id,
            assignment_id=int(request.form.get("assignment_id", "")),
        )
        flash("Role assignment revoked." if changed else "Role assignment was already inactive.", "success")
    except (IdentityAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not revoke role assignment.", "danger")
    return _directory_redirect()


@directory_admin_bp.post("/roles")
@login_required
def assign_employee_role():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        reference = request.form.get("scope_reference", "").strip() or None
        assignment_id = assign_role(
            actor_employee_id=g.employee_id,
            employee_id=int(request.form.get("employee_id", "")),
            role_id=int(request.form.get("role_id", "")),
            scope_type=request.form.get("scope_type", ""),
            scope_reference=reference,
        )
        flash(f"Role assignment created (assignment ID {assignment_id}).", "success")
    except (IdentityAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Could not assign role.", "danger")
    return _directory_redirect()
