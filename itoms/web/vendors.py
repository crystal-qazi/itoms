"""Vendor support-contact directory routes."""
from __future__ import annotations

import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.vendors import VendorError, create_vendor, list_vendors, set_vendor_active

vendors_bp = Blueprint("vendors", __name__, url_prefix="/vendors")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@vendors_bp.get("/")
@login_required
def index():
    can_manage = has_permission(g.employee_id, "vendor.directory.manage")
    try:
        vendors = list_vendors(actor_employee_id=g.employee_id, include_inactive=can_manage)
    except VendorError:
        return "Not authorized to view vendors.", 403
    return render_template(
        "vendors/index.html", vendors=vendors, can_manage=can_manage,
        csrf_token_value=session.get("csrf_token", ""),
    )


@vendors_bp.post("/")
@login_required
def create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_vendor(
            actor_employee_id=g.employee_id,
            vendor_name=request.form.get("vendor_name", ""),
            service_description=request.form.get("service_description", ""),
            support_email=request.form.get("support_email", ""),
            support_phone=request.form.get("support_phone", ""),
            support_portal_url=request.form.get("support_portal_url", ""),
        )
        flash("Vendor support contact added.", "success")
    except VendorError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("vendors.index"))


@vendors_bp.post("/<int:vendor_id>/active")
@login_required
def active(vendor_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        set_vendor_active(
            actor_employee_id=g.employee_id, vendor_id=vendor_id,
            is_active=request.form.get("is_active") == "1",
        )
        flash("Vendor directory entry updated.", "success")
    except VendorError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("vendors.index"))
