"""Engineering task queue and lifecycle routes."""
from __future__ import annotations
import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from itoms.security.decorators import login_required
from itoms.services.engineering_tasks import (TaskError, TASK_TRANSITIONS, create_task, change_task_status, get_task_detail, list_accessible_task_teams, list_task_assignees, list_tasks)

engineering_tasks_bp = Blueprint("engineering_tasks", __name__, url_prefix="/engineering/tasks")

@engineering_tasks_bp.get("/")
@login_required
def index():
    raw_team = request.args.get("team", "").strip()
    team_id = int(raw_team) if raw_team.isdigit() and int(raw_team) > 0 else None
    status = request.args.get("status", "").strip().upper() or None
    priority = request.args.get("priority", "").strip().upper() or None
    teams = list_accessible_task_teams(actor_employee_id=g.employee_id)
    if team_id and team_id not in {item["team_id"] for item in teams}: team_id = None
    tasks = list_tasks(actor_employee_id=g.employee_id, team_id=team_id, status=status, priority=priority)
    create_teams = list_accessible_task_teams(actor_employee_id=g.employee_id, permission_key="engineering.tasks.create")
    assignees = list_task_assignees(actor_employee_id=g.employee_id)
    return render_template("engineering_tasks/index.html", tasks=tasks, teams=teams, create_teams=create_teams, assignees=assignees, selected_team=team_id, selected_status=status or "", selected_priority=priority or "", csrf_token_value=session.get("csrf_token", ""))

@engineering_tasks_bp.post("/")
@login_required
def create():
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))): return "Invalid request token", 400
    try:
        team_id = int(request.form.get("team_id", ""))
        raw_assignee = request.form.get("assigned_to", "").strip()
        assigned_to = int(raw_assignee) if raw_assignee else None
        due_at = request.form.get("due_at", "").strip() or None
        task_id = create_task(actor_employee_id=g.employee_id, team_id=team_id, title=request.form.get("title", ""), description=request.form.get("description", ""), assigned_to=assigned_to, priority=request.form.get("priority", "MEDIUM"), due_at=due_at)
    except (ValueError, TypeError, TaskError) as exc:
        flash(str(exc) or "Invalid task details.", "danger")
        return redirect(url_for("engineering_tasks.index"))
    flash("Engineering task created.", "success")
    return redirect(url_for("engineering_tasks.detail", task_id=task_id))

@engineering_tasks_bp.get("/<int:task_id>")
@login_required
def detail(task_id: int):
    try: task = get_task_detail(actor_employee_id=g.employee_id, task_id=task_id)
    except TaskError: return "Task not found.", 404
    transitions = sorted(TASK_TRANSITIONS.get(task["status"], set()))
    return render_template("engineering_tasks/detail.html", task=task, transitions=transitions, csrf_token_value=session.get("csrf_token", ""))

@engineering_tasks_bp.post("/<int:task_id>/status")
@login_required
def update_status(task_id: int):
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))): return "Invalid request token", 400
    try:
        change_task_status(actor_employee_id=g.employee_id, task_id=task_id, new_status=request.form.get("status", "").strip().upper())
        flash("Task status updated.", "success")
    except TaskError as exc: flash(str(exc), "danger")
    return redirect(url_for("engineering_tasks.detail", task_id=task_id))
