"""Problem Management queue and known-error routes."""
from __future__ import annotations

import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.authorization import ResourceContext, has_permission
from itoms.services.problems import (
    PROBLEM_STATUSES, PRIORITIES, ProblemError, create_known_error,
    create_problem, get_problem_detail, list_problems, link_incident,
    transition_problem,
)

problems_bp = Blueprint("problems", __name__, url_prefix="/problems")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


def _teams(permission: str) -> list[dict]:
    from itoms.db.connection import get_connection
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT t.team_id,t.team_name,t.department_id FROM teams t
               JOIN departments d ON d.department_id=t.department_id
               WHERE t.is_active=TRUE AND d.is_active=TRUE ORDER BY t.team_name"""
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return [row for row in rows if has_permission(
        g.employee_id, permission,
        ResourceContext(team_id=row["team_id"], department_id=row["department_id"]),
    )]


@problems_bp.get("/")
@login_required
def index():
    status = request.args.get("status", "").strip().upper() or None
    try:
        problems = list_problems(actor_employee_id=g.employee_id, status=status)
    except ProblemError:
        return "Invalid problem filter.", 400
    teams = _teams("problem.create")
    return render_template(
        "problems/index.html", problems=problems, teams=teams,
        statuses=sorted(PROBLEM_STATUSES), priorities=sorted(PRIORITIES),
        selected_status=status or "", csrf_token_value=session.get("csrf_token", ""),
    )


@problems_bp.post("/")
@login_required
def create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        problem_id = create_problem(
            actor_employee_id=g.employee_id,
            title=request.form.get("title", ""),
            description=request.form.get("description", ""),
            owner_team_id=int(request.form.get("owner_team_id", "")),
            priority=request.form.get("priority", "MEDIUM"),
        )
        flash("Problem record created.", "success")
        return redirect(url_for("problems.detail", problem_id=problem_id))
    except (ProblemError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid problem details.", "danger")
        return redirect(url_for("problems.index"))


@problems_bp.get("/<int:problem_id>")
@login_required
def detail(problem_id: int):
    try:
        problem = get_problem_detail(actor_employee_id=g.employee_id, problem_id=problem_id)
    except ProblemError:
        return "Problem not found.", 404
    return render_template(
        "problems/detail.html", problem=problem,
        statuses=sorted(PROBLEM_STATUSES),
        csrf_token_value=session.get("csrf_token", ""),
    )


@problems_bp.post("/<int:problem_id>/status")
@login_required
def status(problem_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        transition_problem(
            actor_employee_id=g.employee_id, problem_id=problem_id,
            new_status=request.form.get("status", "").strip().upper(),
            root_cause=request.form.get("root_cause", ""),
        )
        flash("Problem status updated.", "success")
    except ProblemError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("problems.detail", problem_id=problem_id))


@problems_bp.post("/<int:problem_id>/incidents")
@login_required
def incident_link(problem_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        link_incident(
            actor_employee_id=g.employee_id, problem_id=problem_id,
            ticket_id=int(request.form.get("ticket_id", "")),
        )
        flash("Incident linked to problem.", "success")
    except (ProblemError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid incident link.", "danger")
    return redirect(url_for("problems.detail", problem_id=problem_id))


@problems_bp.post("/<int:problem_id>/known-error")
@login_required
def known_error(problem_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_known_error(
            actor_employee_id=g.employee_id, problem_id=problem_id,
            title=request.form.get("title", ""),
            symptoms=request.form.get("symptoms", ""),
            workaround=request.form.get("workaround", ""),
        )
        flash("Known error and workaround recorded.", "success")
    except ProblemError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("problems.detail", problem_id=problem_id))
