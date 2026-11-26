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
            cur.execute("""SELECT 1 FROM employee_team_memberships
                WHERE employee_id=%s AND team_id=%s""",(assigned_to,team_id))
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
    conn=get_connection();cur=conn.cursor()
    try:
        cur.execute("SELECT status,team_id FROM engineering_tasks WHERE task_id=%s FOR UPDATE",(task_id,))
        row=cur.fetchone()
        if not row: raise TaskError("Task not found.")
        old_status,team_id=row
        if not has_permission(actor_employee_id,"engineering.tasks.update",ResourceContext(team_id=team_id)):
            raise TaskError("Not authorized to update this task.")
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
