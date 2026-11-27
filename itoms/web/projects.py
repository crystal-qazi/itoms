"""Project portfolio and milestone routes."""
from __future__ import annotations

import hmac
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.projects import (
    PROJECT_STATUSES, MILESTONE_STATUSES, ProjectError, create_project,
    create_milestone, get_project_detail, list_projects, update_milestone_status,
)

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@projects_bp.get("/")
@login_required
def index():
    status = request.args.get("status", "").strip().upper() or None
    try:
        projects = list_projects(actor_employee_id=g.employee_id, status=status)
    except ProjectError:
        abort(400)
    can_create = has_permission(g.employee_id, "project.create")
    teams = []
    if can_create:
        from itoms.db.connection import get_connection
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                """SELECT t.team_id,t.team_name,t.department_id
                   FROM teams t JOIN departments d ON d.department_id=t.department_id
                   WHERE t.is_active=TRUE AND d.is_active=TRUE ORDER BY t.team_name"""
            )
            candidates = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        from itoms.services.authorization import ResourceContext
        teams = [team for team in candidates if has_permission(
            g.employee_id, "project.create",
            ResourceContext(team_id=team["team_id"], department_id=team["department_id"])
        )]
    return render_template(
        "projects/index.html", projects=projects, teams=teams,
        can_create=bool(teams), statuses=sorted(PROJECT_STATUSES),
        selected_status=status or "", csrf_token_value=session.get("csrf_token", ""),
    )


@projects_bp.post("/")
@login_required
def create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        team_ids = [int(value) for value in request.form.getlist("team_ids")]
        project_id = create_project(
            actor_employee_id=g.employee_id,
            project_key=request.form.get("project_key", ""),
            project_name=request.form.get("project_name", ""),
            description=request.form.get("description", ""),
            team_ids=team_ids,
            manager_employee_id=int(request.form["manager_employee_id"])
            if request.form.get("manager_employee_id", "").strip() else None,
            start_date=request.form.get("start_date"),
            target_end_date=request.form.get("target_end_date"),
        )
    except (ProjectError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid project details.", "danger")
        return redirect(url_for("projects.index"))
    flash("Project created.", "success")
    return redirect(url_for("projects.detail", project_id=project_id))


@projects_bp.get("/<int:project_id>")
@login_required
def detail(project_id: int):
    try:
        project = get_project_detail(actor_employee_id=g.employee_id, project_id=project_id)
    except ProjectError:
        abort(404)
    return render_template(
        "projects/detail.html", project=project,
        milestone_statuses=sorted(MILESTONE_STATUSES),
        csrf_token_value=session.get("csrf_token", ""),
    )


@projects_bp.post("/<int:project_id>/milestones")
@login_required
def milestone_create(project_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_milestone(
            actor_employee_id=g.employee_id, project_id=project_id,
            title=request.form.get("title", ""), due_date=request.form.get("due_date"),
        )
        flash("Milestone added.", "success")
    except ProjectError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("projects.detail", project_id=project_id))


@projects_bp.post("/milestones/<int:milestone_id>/status")
@login_required
def milestone_status(milestone_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        update_milestone_status(
            actor_employee_id=g.employee_id, milestone_id=milestone_id,
            new_status=request.form.get("status", "").strip().upper(),
        )
        flash("Milestone status updated.", "success")
    except ProjectError as exc:
        flash(str(exc), "danger")
        return redirect(request.referrer or url_for("projects.index"))
    return redirect(request.referrer or url_for("projects.index"))
