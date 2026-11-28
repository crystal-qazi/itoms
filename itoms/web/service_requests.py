"""Authenticated Service Requests inbox and category administration."""
from __future__ import annotations

import hmac
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.authorization import ResourceContext, has_permission
from itoms.services.service_requests import (
    ServiceRequestError, add_comment, assign_request, create_category, create_request,
    get_request_detail, list_categories, list_category_admin, list_requests, list_comments,
    set_category_active, transition_request, list_assignable_teams, list_assignable_members,
)

service_requests_bp = Blueprint("service_requests", __name__, url_prefix="/service-requests")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@service_requests_bp.get("/")
@login_required
def index():
    status = request.args.get("status", "").strip().upper() or None
    priority = request.args.get("priority", "").strip().upper() or None
    try:
        rows = list_requests(actor_employee_id=g.employee_id, status=status, priority=priority)
    except ServiceRequestError:
        abort(400)
    can_create = has_permission(g.employee_id, "service_request.create")
    can_manage_categories = has_permission(g.employee_id, "service_request.categories.manage")
    categories = list_categories()
    category_admin = list_category_admin(actor_employee_id=g.employee_id) if can_manage_categories else []
    return render_template(
        "service_requests/index.html", requests=rows, categories=categories,
        category_admin=category_admin, can_create=can_create,
        can_manage_categories=can_manage_categories,
        csrf_token_value=session.get("csrf_token", ""),
        selected_status=status or "", selected_priority=priority or "",
    )


@service_requests_bp.post("/")
@login_required
def create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        raw_category = request.form.get("category_id", "").strip()
        category_id = int(raw_category) if raw_category else None
        request_id = create_request(
            actor_employee_id=g.employee_id,
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            category_id=category_id,
            priority=request.form.get("priority", "MEDIUM"),
        )
    except (ServiceRequestError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid service request.", "danger")
        return redirect(url_for("service_requests.index"))
    flash("Service request submitted.", "success")
    return redirect(url_for("service_requests.detail", request_id=request_id))


@service_requests_bp.get("/<int:request_id>")
@login_required
def detail(request_id: int):
    try:
        item = get_request_detail(actor_employee_id=g.employee_id, request_id=request_id)
    except ServiceRequestError:
        return "Service request not found.", 404
    request_context = ResourceContext(
        owner_employee_id=item["requester_employee_id"],
        team_id=item["assigned_team_id"],
        department_id=item["department_id"],
    )
    can_assign = has_permission(g.employee_id, "service_request.assign", request_context)
    teams = list_assignable_teams(actor_employee_id=g.employee_id, request_id=request_id)
    members = list_assignable_members(actor_employee_id=g.employee_id, request_id=request_id)
    comments = list_comments(actor_employee_id=g.employee_id, request_id=request_id)
    return render_template(
        "service_requests/detail.html", item=item, can_assign=can_assign,
        can_update=has_permission(g.employee_id, "service_request.update", request_context),
        teams=teams, members=members, comments=comments,
        csrf_token_value=session.get("csrf_token", ""),
    )


@service_requests_bp.post("/<int:request_id>/assignment")
@login_required
def assignment(request_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        raw_team = request.form.get("assigned_team_id", "").strip()
        raw_employee = request.form.get("assigned_employee_id", "").strip()
        assign_request(
            actor_employee_id=g.employee_id, request_id=request_id,
            assigned_team_id=int(raw_team) if raw_team else None,
            assigned_employee_id=int(raw_employee) if raw_employee else None,
        )
        flash("Service request assignment updated.", "success")
    except (ServiceRequestError, ValueError, TypeError) as exc:
        flash(str(exc) or "Select a valid assignment.", "danger")
    return redirect(url_for("service_requests.detail", request_id=request_id))


@service_requests_bp.post("/<int:request_id>/status")
@login_required
def status(request_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        transition_request(
            actor_employee_id=g.employee_id, request_id=request_id,
            new_status=request.form.get("status", ""),
            resolution_notes=request.form.get("resolution_notes", ""),
            pending_reason=request.form.get("pending_reason", ""),
        )
        flash("Service request status updated.", "success")
    except ServiceRequestError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("service_requests.detail", request_id=request_id))


@service_requests_bp.post("/categories")
@login_required
def category_create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_category(
            actor_employee_id=g.employee_id,
            category_name=request.form.get("category_name", ""),
            description=request.form.get("description", ""),
        )
        flash("Service request category created.", "success")
    except ServiceRequestError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("service_requests.index"))


@service_requests_bp.post("/categories/<int:category_id>/active")
@login_required
def category_active(category_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    active = request.form.get("is_active") == "1"
    try:
        set_category_active(
            actor_employee_id=g.employee_id, category_id=category_id, is_active=active
        )
        flash("Service request category updated.", "success")
    except ServiceRequestError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("service_requests.index"))



@service_requests_bp.post("/<int:request_id>/comments")
@login_required
def comment_create(request_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        add_comment(
            actor_employee_id=g.employee_id,
            request_id=request_id,
            body=request.form.get("body", ""),
        )
        flash("Comment added.", "success")
    except ServiceRequestError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("service_requests.detail", request_id=request_id))
