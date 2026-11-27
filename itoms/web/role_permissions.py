"""Role-to-permission administration UI."""
from __future__ import annotations
import hmac
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.identity_admin import (
    IdentityAdministrationError, grant_role_permission,
    list_role_permission_options, revoke_role_permission,
)

role_permissions_bp = Blueprint("role_permissions", __name__, url_prefix="/admin/role-permissions")


@role_permissions_bp.get("/")
@login_required
def index():
    if not has_permission(g.employee_id, "identity.roles.permissions.manage"):
        abort(403)
    try:
        data = list_role_permission_options(
            actor_employee_id=g.employee_id,
            role_id=request.args.get("role_id", type=int),
        )
    except IdentityAdministrationError:
        abort(403)
    return render_template(
        "admin/role_permissions.html",
        **data,
        csrf_token_value=session.get("csrf_token", ""),
    )


@role_permissions_bp.post("/")
@login_required
def update():
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))):
        return "Invalid request token", 400
    if not has_permission(g.employee_id, "identity.roles.permissions.manage"):
        abort(403)
    try:
        role_id = int(request.form.get("role_id", ""))
        permission_key = request.form.get("permission_key", "").strip()
        action = request.form.get("action", "").strip().lower()
        if action == "grant":
            changed = grant_role_permission(
                actor_employee_id=g.employee_id, role_id=role_id, permission_key=permission_key
            )
            flash("Permission granted." if changed else "Permission was already granted.", "success")
        elif action == "revoke":
            changed = revoke_role_permission(
                actor_employee_id=g.employee_id, role_id=role_id, permission_key=permission_key
            )
            flash("Permission revoked." if changed else "Permission was already absent.", "success")
        else:
            raise IdentityAdministrationError("Select a valid permission action.")
    except (IdentityAdministrationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid role permission update.", "danger")
    return redirect(url_for("role_permissions.index", role_id=request.form.get("role_id", "")))
