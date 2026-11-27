"""Asset register and basic maintenance routes."""
from __future__ import annotations

import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.assets import (
    ASSET_STATUSES, MAINTENANCE_STATUSES, AssetError, create_asset,
    create_maintenance, list_asset_teams, list_assets, list_maintenance,
    update_asset_status, update_maintenance_status,
)

assets_bp = Blueprint("assets", __name__, url_prefix="/assets")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@assets_bp.get("/")
@login_required
def index():
    status = request.args.get("status", "").strip().upper() or None
    try:
        assets = list_assets(actor_employee_id=g.employee_id, status=status)
    except AssetError:
        return "Invalid asset filter.", 400
    teams = list_asset_teams(actor_employee_id=g.employee_id)
    maintenance = list_maintenance(actor_employee_id=g.employee_id)
    return render_template(
        "assets/index.html", assets=assets, teams=teams, maintenance=maintenance,
        asset_statuses=sorted(ASSET_STATUSES),
        maintenance_statuses=sorted(MAINTENANCE_STATUSES),
        selected_status=status or "", csrf_token_value=session.get("csrf_token", ""),
    )


@assets_bp.post("/")
@login_required
def create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        asset_id = create_asset(
            actor_employee_id=g.employee_id,
            asset_tag=request.form.get("asset_tag", ""),
            asset_name=request.form.get("asset_name", ""),
            asset_type=request.form.get("asset_type", ""),
            owner_team_id=int(request.form.get("owner_team_id", "")),
            serial_number=request.form.get("serial_number", ""),
            manufacturer=request.form.get("manufacturer", ""),
            model=request.form.get("model", ""),
            location_label=request.form.get("location_label", ""),
            acquired_on=request.form.get("acquired_on", ""),
            assigned_employee_id=int(request.form["assigned_employee_id"])
            if request.form.get("assigned_employee_id", "").strip() else None,
        )
        flash("Asset registered.", "success")
    except (AssetError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid asset details.", "danger")
    return redirect(url_for("assets.index"))


@assets_bp.post("/<int:asset_id>/status")
@login_required
def asset_status(asset_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        update_asset_status(
            actor_employee_id=g.employee_id, asset_id=asset_id,
            new_status=request.form.get("status", "").strip().upper(),
        )
        flash("Asset status updated.", "success")
    except AssetError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("assets.index"))


@assets_bp.post("/<int:asset_id>/maintenance")
@login_required
def maintenance_create(asset_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_maintenance(
            actor_employee_id=g.employee_id, asset_id=asset_id,
            issue_description=request.form.get("issue_description", ""),
            assigned_to=int(request.form["assigned_to"])
            if request.form.get("assigned_to", "").strip() else None,
        )
        flash("Maintenance ticket opened.", "success")
    except (AssetError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid maintenance details.", "danger")
    return redirect(url_for("assets.index"))


@assets_bp.post("/maintenance/<int:maintenance_id>/status")
@login_required
def maintenance_status(maintenance_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        update_maintenance_status(
            actor_employee_id=g.employee_id, maintenance_id=maintenance_id,
            new_status=request.form.get("status", "").strip().upper(),
        )
        flash("Maintenance ticket updated.", "success")
    except AssetError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("assets.index"))
