"""Admin-controlled incident SLA escalation policy interface."""
from __future__ import annotations

import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.sla_escalations import (
    SLAEscalationError, list_escalation_policies, upsert_escalation_policy,
)

sla_admin_bp = Blueprint("sla_admin", __name__, url_prefix="/admin/sla")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@sla_admin_bp.get("/escalations")
@login_required
def escalations():
    try:
        policies = list_escalation_policies(actor_employee_id=g.employee_id)
    except SLAEscalationError:
        return "Not authorized to manage SLA policies.", 403
    return render_template(
        "sla/escalations.html", policies=policies,
        csrf_token_value=session.get("csrf_token", ""),
    )


@sla_admin_bp.post("/escalations")
@login_required
def update_escalation():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        upsert_escalation_policy(
            actor_employee_id=g.employee_id,
            priority=request.form.get("priority", ""),
            sla_type=request.form.get("sla_type", ""),
            escalation_level=int(request.form.get("escalation_level", "")),
            after_due_minutes=int(request.form.get("after_due_minutes", "")),
            is_active=request.form.get("is_active") == "1",
        )
        flash("SLA escalation policy saved.", "success")
    except (SLAEscalationError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid SLA escalation policy.", "danger")
    return redirect(url_for("sla_admin.escalations"))
