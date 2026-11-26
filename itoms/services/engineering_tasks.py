"""Team-scoped engineering task operations."""
from __future__ import annotations
from datetime import datetime, timezone
import secrets
from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission

class TaskError(ValueError):
    """Task operation is invalid or unauthorized."""

TASK_TRANSITIONS={
 "BACKLOG":{"READY","CANCELLED"},
 "READY":{"IN_PROGRESS","CANCELLED"},
 "IN_PROGRESS":{"BLOCKED","IN_REVIEW","DONE","READY"},
 "BLOCKED":{"IN_PROGRESS","CANCELLED"},
 "IN_REVIEW":{"IN_PROGRESS","DONE"},
 "DONE":set(),"CANCELLED":set()
}

def create_task(*,actor_employee_id:int,team_id:int,title:str,description:str="",
                assigned_to:int|None=None,priority:str="MEDIUM",due_at=None)->int:
    if not has_permission(actor_employee_id,"engineering.tasks.create",ResourceContext(team_id=team_id)):
        raise TaskError("Not authorized to create tasks for this team.")
    title=title.strip()
    if not title or len(title)>240: raise TaskError("Task title is required (maximum 240 characters).")
    if priority not in {"LOW","MEDIUM","HIGH","CRITICAL"}: raise TaskError("Invalid priority.")
    conn=get_connection();cur=conn.cursor()
    try:
        cur.execute("SELECT 1 FROM teams WHERE team_id=%s AND is_active=TRUE",(team_id,))
        if not cur.fetchone(): raise TaskError("Team is inactive or unavailable.")
        if assigned_to is not None:
            cur.execute("""SELECT 1 FROM employee_team_memberships m
                JOIN employees e ON e.employee_id=m.employee_id AND e.is_active=TRUE
                WHERE m.employee_id=%s AND m.team_id=%s""",(assigned_to,team_id))
            if not cur.fetchone(): raise TaskError("Assignee must be a member of the task team.")
        number="TASK-"+datetime.now(timezone.utc).strftime("%Y%m%d")+"-"+secrets.token_hex(3).upper()
        cur.execute("""INSERT INTO engineering_tasks
            (task_number,title,description,team_id,created_by,assigned_to,priority,due_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (number,title,description,team_id,actor_employee_id,assigned_to,priority,due_at))
        task_id=int(cur.lastrowid)
        cur.execute("""INSERT INTO engineering_task_activity
            (task_id,actor_employee_id,action_key,new_value)
            VALUES (%s,%s,'TASK_CREATED',%s)""",(task_id,actor_employee_id,number))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'ENGINEERING_TASK_CREATED','engineering_task',%s,'SUCCESS')""",
            (actor_employee_id,str(task_id)))
        conn.commit();return task_id
    except Exception:
        conn.rollback();raise
    finally:
        cur.close();conn.close()

def change_task_status(*,actor_employee_id:int,task_id:int,new_status:str)->None:
    # Resolve the trusted team scope before permission evaluation; do not hold
    # the task row lock while the authorization service opens its own connection.
    conn=get_connection();cur=conn.cursor()
    try:
        cur.execute("SELECT team_id FROM engineering_tasks WHERE task_id=%s",(task_id,))
        snapshot=cur.fetchone()
    finally:
        cur.close();conn.close()
    if not snapshot: raise TaskError("Task not found.")
    team_id=snapshot[0]
    if not has_permission(actor_employee_id,"engineering.tasks.update",ResourceContext(team_id=team_id)):
        raise TaskError("Not authorized to update this task.")
    conn=get_connection();cur=conn.cursor()
    try:
        cur.execute("SELECT status,team_id FROM engineering_tasks WHERE task_id=%s FOR UPDATE",(task_id,))
        row=cur.fetchone()
        if not row or row[1]!=team_id: raise TaskError("Task changed; reload and try again.")
        old_status=row[0]
        if new_status not in TASK_TRANSITIONS.get(old_status,set()):
            raise TaskError(f"Transition from {old_status} to {new_status} is not allowed.")
        cur.execute("UPDATE engineering_tasks SET status=%s WHERE task_id=%s",(new_status,task_id))
        cur.execute("""INSERT INTO engineering_task_activity
            (task_id,actor_employee_id,action_key,old_value,new_value)
            VALUES (%s,%s,'STATUS_CHANGED',%s,%s)""",(task_id,actor_employee_id,old_status,new_status))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'ENGINEERING_TASK_STATUS_CHANGED','engineering_task',%s,'SUCCESS')""",
            (actor_employee_id,str(task_id)))
        conn.commit()
    except Exception:
        conn.rollback();raise
    finally:
        cur.close();conn.close()


def list_accessible_task_teams(*, actor_employee_id: int, permission_key: str = "engineering.tasks.read") -> list[dict]:
    """Return active teams visible to the actor for a specific task permission."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT team_id,team_name FROM teams WHERE is_active=TRUE ORDER BY team_name")
        teams = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return [team for team in teams if has_permission(actor_employee_id, permission_key, ResourceContext(team_id=team["team_id"]))]


def list_tasks(*, actor_employee_id: int, team_id: int | None = None, status: str | None = None, priority: str | None = None, limit: int = 100) -> list[dict]:
    """List tasks only when the actor has read access to each task's team."""
    limit = max(1, min(int(limit), 200))
    clauses, params = [], []
    if team_id is not None:
        clauses.append("team_id=%s"); params.append(team_id)
    if status in {"BACKLOG", "READY", "IN_PROGRESS", "BLOCKED", "IN_REVIEW", "DONE", "CANCELLED"}:
        clauses.append("status=%s"); params.append(status)
    if priority in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        clauses.append("priority=%s"); params.append(priority)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT task_id,task_number,title,team_id,assigned_to,priority,status,due_at,created_at FROM engineering_tasks" + where + " ORDER BY created_at DESC,task_id DESC LIMIT %s", tuple(params + [limit * 3]))
        candidates = cur.fetchall()
        cur.execute("SELECT team_id,team_name FROM teams")
        team_names = {row["team_id"]: row["team_name"] for row in cur.fetchall()}
    finally:
        cur.close(); conn.close()
    visible = []
    for item in candidates:
        if has_permission(actor_employee_id, "engineering.tasks.read", ResourceContext(team_id=item["team_id"])):
            item["team_name"] = team_names.get(item["team_id"], "Unknown team")
            visible.append(item)
            if len(visible) >= limit: break
    return visible


def get_task_detail(*, actor_employee_id: int, task_id: int) -> dict:
    """Fetch task and activity after checking the trusted team scope."""
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT t.task_id,t.task_number,t.title,t.description,t.team_id,t.assigned_to,t.priority,t.status,t.due_at,t.created_at,t.updated_at,tm.team_name,creator.full_name AS creator_name,assignee.full_name AS assignee_name FROM engineering_tasks t JOIN teams tm ON tm.team_id=t.team_id JOIN employees creator ON creator.employee_id=t.created_by LEFT JOIN employees assignee ON assignee.employee_id=t.assigned_to WHERE t.task_id=%s", (task_id,))
        task = cur.fetchone()
        if not task or not has_permission(actor_employee_id, "engineering.tasks.read", ResourceContext(team_id=task["team_id"])):
            raise TaskError("Task not found.")
        cur.execute("SELECT a.action_key,a.old_value,a.new_value,a.created_at,e.full_name AS actor_name FROM engineering_task_activity a JOIN employees e ON e.employee_id=a.actor_employee_id WHERE a.task_id=%s ORDER BY a.created_at,a.activity_id", (task_id,))
        task["activity"] = cur.fetchall()
        return task
    finally:
        cur.close(); conn.close()

def list_task_assignees(*, actor_employee_id: int) -> list[dict]:
    """List active employees only from teams where the actor may create tasks."""
    allowed_teams = list_accessible_task_teams(actor_employee_id=actor_employee_id, permission_key="engineering.tasks.create")
    team_ids = [item["team_id"] for item in allowed_teams]
    if not team_ids: return []
    placeholders = ",".join(["%s"] * len(team_ids))
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT e.employee_id,e.full_name,m.team_id FROM employees e JOIN employee_team_memberships m ON m.employee_id=e.employee_id WHERE e.is_active=TRUE AND m.team_id IN (" + placeholders + ") ORDER BY e.full_name", tuple(team_ids))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()