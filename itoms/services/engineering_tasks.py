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
    if not isinstance(team_id, int) or team_id <= 0:
        raise TaskError("Select a valid task team.")
    title=title.strip()
    if not title or len(title)>240: raise TaskError("Task title is required (maximum 240 characters).")
    priority=priority.strip().upper()
    description=description.strip()
    if priority not in {"LOW","MEDIUM","HIGH","CRITICAL"}: raise TaskError("Invalid priority.")
    if len(description)>20000: raise TaskError("Task description must be 20,000 characters or fewer.")
    conn=get_connection();cur=conn.cursor()
    try:
        cur.execute("""SELECT t.department_id FROM teams t
            JOIN departments d ON d.department_id=t.department_id
            WHERE t.team_id=%s AND t.is_active=TRUE AND d.is_active=TRUE""",(team_id,))
        team=cur.fetchone()
        if not team: raise TaskError("Team is inactive or unavailable.")
        context=ResourceContext(team_id=team_id,department_id=team[0])
        if not has_permission(actor_employee_id,"engineering.tasks.create",context):
            raise TaskError("Not authorized to create tasks for this team.")
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
        cur.execute("""SELECT t.team_id,tm.department_id
            FROM engineering_tasks t JOIN teams tm ON tm.team_id=t.team_id
            WHERE t.task_id=%s""",(task_id,))
        snapshot=cur.fetchone()
    finally:
        cur.close();conn.close()
    if not snapshot: raise TaskError("Task not found.")
    team_id,department_id=snapshot
    context=ResourceContext(team_id=team_id,department_id=department_id)
    if not has_permission(actor_employee_id,"engineering.tasks.update",context):
        raise TaskError("Not authorized to update this task.")
    conn=get_connection();cur=conn.cursor()
    try:
        cur.execute("""SELECT t.status,t.team_id,tm.department_id
            FROM engineering_tasks t JOIN teams tm ON tm.team_id=t.team_id
            WHERE t.task_id=%s FOR UPDATE""",(task_id,))
        row=cur.fetchone()
        if not row or row[1]!=team_id or row[2]!=department_id:
            raise TaskError("Task changed; reload and try again.")
        if not has_permission(actor_employee_id,"engineering.tasks.update",context):
            raise TaskError("Not authorized to update this task.")
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
        cur.execute("""SELECT t.team_id,t.team_name,t.department_id
            FROM teams t JOIN departments d ON d.department_id=t.department_id
            WHERE t.is_active=TRUE AND d.is_active=TRUE ORDER BY t.team_name""")
        teams = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return [team for team in teams if has_permission(actor_employee_id, permission_key, ResourceContext(team_id=team["team_id"], department_id=team["department_id"]))]


def list_tasks(*, actor_employee_id: int, team_id: int | None = None, status: str | None = None, priority: str | None = None, limit: int = 100) -> list[dict]:
    """List tasks only from teams the actor can read, before applying pagination."""
    limit = max(1, min(int(limit), 200))
    accessible_teams = list_accessible_task_teams(actor_employee_id=actor_employee_id)
    accessible_by_id = {item["team_id"]: item for item in accessible_teams}
    if team_id is not None:
        if team_id not in accessible_by_id:
            return []
        selected_team_ids = [team_id]
    else:
        selected_team_ids = list(accessible_by_id)
    if not selected_team_ids:
        return []

    clauses = ["team_id IN (" + ",".join(["%s"] * len(selected_team_ids)) + ")"]
    params = list(selected_team_ids)
    if status in {"BACKLOG", "READY", "IN_PROGRESS", "BLOCKED", "IN_REVIEW", "DONE", "CANCELLED"}:
        clauses.append("status=%s"); params.append(status)
    if priority in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        clauses.append("priority=%s"); params.append(priority)
    where = " WHERE " + " AND ".join(clauses)
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT task_id,task_number,title,team_id,assigned_to,priority,status,due_at,created_at "
            "FROM engineering_tasks" + where +
            " ORDER BY created_at DESC,task_id DESC LIMIT %s",
            tuple(params + [limit]),
        )
        rows = cur.fetchall()
    finally:
        cur.close(); conn.close()
    for item in rows:
        item["team_name"] = accessible_by_id[item["team_id"]]["team_name"]
    return rows

def get_task_detail(*, actor_employee_id: int, task_id: int) -> dict:
    """Fetch task and activity after checking the trusted team scope."""
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT t.task_id,t.task_number,t.title,t.description,t.team_id,
            t.assigned_to,t.priority,t.status,t.due_at,t.created_at,t.updated_at,
            tm.team_name,tm.department_id,
            creator.full_name AS creator_name,assignee.full_name AS assignee_name
            FROM engineering_tasks t
            JOIN teams tm ON tm.team_id=t.team_id AND tm.is_active=TRUE
            JOIN departments d ON d.department_id=tm.department_id AND d.is_active=TRUE
            LEFT JOIN employees creator ON creator.employee_id=t.created_by AND creator.is_active=TRUE
            LEFT JOIN employees assignee ON assignee.employee_id=t.assigned_to AND assignee.is_active=TRUE
            WHERE t.task_id=%s""", (task_id,))
        task = cur.fetchone()
        if not task or not has_permission(actor_employee_id, "engineering.tasks.read",
            ResourceContext(team_id=task["team_id"],department_id=task["department_id"])):
            raise TaskError("Task not found.")
        cur.execute("""SELECT a.action_key,a.old_value,a.new_value,a.created_at,
            COALESCE(e.full_name,'Former or inactive user') AS actor_name
            FROM engineering_task_activity a
            LEFT JOIN employees e ON e.employee_id=a.actor_employee_id AND e.is_active=TRUE
            WHERE a.task_id=%s ORDER BY a.created_at,a.activity_id""", (task_id,))
        task["activity"] = cur.fetchall()
        return task
    finally:
        cur.close()
        conn.close()

def list_task_assignees(*, actor_employee_id: int) -> list[dict]:
    """List active employees grouped by active teams where the actor may create tasks."""
    allowed_teams = list_accessible_task_teams(
        actor_employee_id=actor_employee_id,
        permission_key="engineering.tasks.create",
    )
    team_ids = [item["team_id"] for item in allowed_teams]
    if not team_ids:
        return []
    placeholders = ",".join(["%s"] * len(team_ids))
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT DISTINCT e.employee_id,e.full_name,m.team_id,t.team_name
               FROM employees e
               JOIN employee_team_memberships m ON m.employee_id=e.employee_id
               JOIN teams t ON t.team_id=m.team_id AND t.is_active=TRUE
               JOIN departments d ON d.department_id=t.department_id AND d.is_active=TRUE
               WHERE e.is_active=TRUE AND m.team_id IN (""" + placeholders + """)
               ORDER BY t.team_name,e.full_name,e.employee_id""",
            tuple(team_ids),
        )
        return cur.fetchall()
    finally:
        cur.close(); conn.close()
