"""Problem Management with scoped ownership, incident links and known errors."""
from __future__ import annotations

import re
import secrets
from mysql.connector import IntegrityError

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission, has_permission_in_transaction


class ProblemError(ValueError):
    """Invalid or unauthorized problem-management operation."""


PROBLEM_STATUSES = {"OPEN", "INVESTIGATING", "KNOWN_ERROR", "RESOLVED", "CLOSED"}
PROBLEM_TRANSITIONS = {
    "OPEN": {"INVESTIGATING", "KNOWN_ERROR", "RESOLVED", "CLOSED"},
    "INVESTIGATING": {"OPEN", "KNOWN_ERROR", "RESOLVED", "CLOSED"},
    "KNOWN_ERROR": {"INVESTIGATING", "RESOLVED", "CLOSED"},
    "RESOLVED": {"OPEN", "CLOSED"},
    "CLOSED": set(),
}
PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def _problem_context(cur, problem_id: int):
    cur.execute(
        """SELECT p.owner_team_id,t.department_id
           FROM problem_records p JOIN teams t ON t.team_id=p.owner_team_id
           JOIN departments d ON d.department_id=t.department_id
           WHERE p.problem_id=%s AND t.is_active=TRUE AND d.is_active=TRUE""",
        (problem_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        return ResourceContext(team_id=row["owner_team_id"], department_id=row["department_id"])
    return ResourceContext(team_id=row[0], department_id=row[1])


def create_problem(
    *, actor_employee_id: int, title: str, description: str,
    owner_team_id: int, priority: str = "MEDIUM", assigned_to: int | None = None,
) -> int:
    name = (title or "").strip()
    detail = (description or "").strip()
    priority = (priority or "").strip().upper()
    if not name or len(name) > 240 or not detail or len(detail) > 20000:
        raise ProblemError("A problem title (maximum 240) and description (maximum 20,000) are required.")
    if priority not in PRIORITIES:
        raise ProblemError("Select a valid problem priority.")
    if type(owner_team_id) is not int or owner_team_id <= 0:
        raise ProblemError("Select a valid owner team.")
    if assigned_to is not None and (type(assigned_to) is not int or assigned_to <= 0):
        raise ProblemError("Select a valid assignee.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT t.department_id FROM teams t JOIN departments d
               ON d.department_id=t.department_id
               WHERE t.team_id=%s AND t.is_active=TRUE AND d.is_active=TRUE""",
            (owner_team_id,),
        )
        team = cur.fetchone()
        if not team:
            raise ProblemError("Owner team is inactive or unavailable.")
        context = ResourceContext(team_id=owner_team_id, department_id=team[0])
        if not has_permission_in_transaction(
            cur, actor_employee_id, "problem.create", context,
            lock_employee_ids=[assigned_to] if assigned_to is not None else None,
        ):
            raise ProblemError("Not authorized to create problems for this team.")
        cur.execute(
            "SELECT department_id,is_active FROM teams WHERE team_id=%s FOR UPDATE",
            (owner_team_id,),
        )
        locked_team = cur.fetchone()
        if not locked_team or not locked_team[1] or locked_team[0] != team[0]:
            raise ProblemError("Owner team changed; retry problem creation.")
        cur.execute(
            "SELECT is_active FROM departments WHERE department_id=%s FOR UPDATE",
            (team[0],),
        )
        department = cur.fetchone()
        if not department or not department[0]:
            raise ProblemError("Owner department is inactive or unavailable.")
        if assigned_to is not None:
            cur.execute("SELECT is_active FROM employees WHERE employee_id=%s FOR UPDATE", (assigned_to,))
            assignee = cur.fetchone()
            if not assignee or not assignee[0]:
                raise ProblemError("Assignee must be an active member of the owner team.")
            cur.execute(
                """SELECT 1 FROM employee_team_memberships
                   WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
                (assigned_to, owner_team_id),
            )
            if not cur.fetchone():
                raise ProblemError("Assignee must be an active member of the owner team.")
        problem_key = f"PRB-{secrets.token_hex(4).upper()}"
        cur.execute(
            """INSERT INTO problem_records
               (problem_key,title,description,owner_team_id,assigned_to,priority,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (problem_key, name, detail, owner_team_id, assigned_to, priority, actor_employee_id),
        )
        problem_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'PROBLEM_CREATED','problem',%s,'SUCCESS',
                       JSON_OBJECT('problem_key',%s))""",
            (actor_employee_id, str(problem_id), problem_key),
        )
        conn.commit()
        return problem_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def list_problems(*, actor_employee_id: int, status: str | None = None) -> list[dict]:
    if status and status not in PROBLEM_STATUSES:
        raise ProblemError("Invalid problem status filter.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT p.problem_id,p.problem_key,p.title,p.priority,p.status,
                      p.owner_team_id,p.assigned_to,p.created_at,p.updated_at,
                      t.team_name,t.department_id,e.full_name AS assignee_name,
                      COUNT(l.ticket_id) AS linked_incident_count
               FROM problem_records p
               JOIN teams t ON t.team_id=p.owner_team_id
               JOIN departments d ON d.department_id=t.department_id
               LEFT JOIN employees e ON e.employee_id=p.assigned_to
               LEFT JOIN problem_incident_links l ON l.problem_id=p.problem_id
               WHERE t.is_active=TRUE AND d.is_active=TRUE
                 AND (%s IS NULL OR p.status=%s)
               GROUP BY p.problem_id,p.problem_key,p.title,p.priority,p.status,
                        p.owner_team_id,p.assigned_to,p.created_at,p.updated_at,
                        t.team_name,t.department_id,e.full_name
               ORDER BY p.updated_at DESC,p.problem_id DESC LIMIT 500""",
            (status, status),
        )
        rows = cur.fetchall()
        visible = []
        for row in rows:
            context = ResourceContext(
                team_id=row["owner_team_id"], department_id=row["department_id"],
                resource_type="problem", resource_id=str(row["problem_id"]),
            )
            if has_permission(actor_employee_id, "problem.read", context):
                row["can_update"] = has_permission(actor_employee_id, "problem.update", context)
                visible.append(row)
        return visible
    finally:
        cur.close()
        conn.close()


def get_problem_detail(*, actor_employee_id: int, problem_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT p.*,t.team_name,t.department_id,e.full_name AS assignee_name,
                      creator.full_name AS creator_name
               FROM problem_records p
               JOIN teams t ON t.team_id=p.owner_team_id
               JOIN employees e ON e.employee_id=p.assigned_to
               LEFT JOIN employees creator ON creator.employee_id=p.created_by
               WHERE p.problem_id=%s""",
            (problem_id,),
        )
        problem = cur.fetchone()
        if not problem:
            # Assigned employee is optional; repeat without an inner assignee join.
            cur.execute(
                """SELECT p.*,t.team_name,t.department_id,e.full_name AS assignee_name,
                          creator.full_name AS creator_name
                   FROM problem_records p
                   JOIN teams t ON t.team_id=p.owner_team_id
                   LEFT JOIN employees e ON e.employee_id=p.assigned_to
                   LEFT JOIN employees creator ON creator.employee_id=p.created_by
                   WHERE p.problem_id=%s""",
                (problem_id,),
            )
            problem = cur.fetchone()
        if not problem:
            raise ProblemError("Problem was not found.")
        context = ResourceContext(
            team_id=problem["owner_team_id"], department_id=problem["department_id"],
            resource_type="problem", resource_id=str(problem_id),
        )
        if not has_permission(actor_employee_id, "problem.read", context):
            raise ProblemError("Problem was not found.")
        problem["can_update"] = has_permission(actor_employee_id, "problem.update", context)
        cur.execute(
            """SELECT i.ticket_id,i.ticket_number,i.title,i.status,i.priority,i.created_at
               FROM problem_incident_links l
               JOIN incident_tickets i ON i.ticket_id=l.ticket_id
               WHERE l.problem_id=%s ORDER BY l.linked_at,i.ticket_id""",
            (problem_id,),
        )
        linked = []
        for incident in cur.fetchall():
            try:
                get_incident_detail(actor_employee_id=actor_employee_id, ticket_id=incident["ticket_id"])
                linked.append(incident)
            except Exception:
                continue
        problem["incidents"] = linked
        cur.execute(
            """SELECT known_error_id,title,symptoms,workaround,is_active,created_at
               FROM known_error_records WHERE problem_id=%s""",
            (problem_id,),
        )
        problem["known_error"] = cur.fetchone()
        return problem
    finally:
        cur.close()
        conn.close()


def transition_problem(*, actor_employee_id: int, problem_id: int, new_status: str,
                       root_cause: str = "") -> None:
    if new_status not in PROBLEM_STATUSES:
        raise ProblemError("Invalid problem status.")
    cause = (root_cause or "").strip()
    if len(cause) > 20000:
        raise ProblemError("Root cause must be 20,000 characters or fewer.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT p.status,p.owner_team_id,t.department_id
               FROM problem_records p JOIN teams t ON t.team_id=p.owner_team_id
               JOIN departments d ON d.department_id=t.department_id
               WHERE p.problem_id=%s""",
            (problem_id,),
        )
        snapshot = cur.fetchone()
        if not snapshot:
            raise ProblemError("Problem was not found.")
        context = ResourceContext(
            team_id=snapshot["owner_team_id"], department_id=snapshot["department_id"],
        )
        if not has_permission_in_transaction(
            cur, actor_employee_id, "problem.update", context
        ):
            raise ProblemError("Not authorized to update this problem.")
        cur.execute(
            "SELECT status,owner_team_id FROM problem_records WHERE problem_id=%s FOR UPDATE",
            (problem_id,),
        )
        row = cur.fetchone()
        if (not row or row["status"] != snapshot["status"]
                or row["owner_team_id"] != snapshot["owner_team_id"]):
            raise ProblemError("Problem changed; reload and try again.")
        old_status = row["status"]
        if new_status not in PROBLEM_TRANSITIONS[old_status]:
            raise ProblemError(f"Cannot move a problem from {old_status} to {new_status}.")
        cur.execute(
            """UPDATE problem_records SET status=%s,
               root_cause=CASE WHEN %s<>'' THEN %s ELSE root_cause END,
               resolved_at=CASE WHEN %s IN ('RESOLVED','CLOSED') THEN COALESCE(resolved_at,UTC_TIMESTAMP()) ELSE NULL END
               WHERE problem_id=%s""",
            (new_status, cause, cause or None, new_status, problem_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'PROBLEM_STATUS_CHANGED','problem',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(problem_id), old_status, new_status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def link_incident(*, actor_employee_id: int, problem_id: int, ticket_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        problem_context = _problem_context(cur, problem_id)
        if not problem_context:
            raise ProblemError("Problem was not found.")
        cur.execute(
            """SELECT i.requester_employee_id,i.assigned_team_id,
                      COALESCE(t.department_id,e.department_id) AS department_id
               FROM incident_tickets i
               JOIN employees e ON e.employee_id=i.requester_employee_id
               LEFT JOIN teams t ON t.team_id=i.assigned_team_id
               WHERE i.ticket_id=%s""",
            (ticket_id,),
        )
        incident = cur.fetchone()
        if not incident:
            raise ProblemError("Incident was not found or is outside your access scope.")
        incident_context = ResourceContext(
            owner_employee_id=incident["requester_employee_id"],
            team_id=incident["assigned_team_id"],
            department_id=incident["department_id"],
            resource_type="incident", resource_id=str(ticket_id),
        )
        if not has_permission_in_transaction(
            cur, actor_employee_id, "incident.read", incident_context,
            lock_employee_ids=[incident["requester_employee_id"]],
        ):
            raise ProblemError("Incident was not found or is outside your access scope.")
        if not has_permission_in_transaction(
            cur, actor_employee_id, "problem.update", problem_context,
            lock_employee_ids=[incident["requester_employee_id"]],
        ):
            raise ProblemError("Not authorized to link incidents to this problem.")
        cur.execute(
            "SELECT owner_team_id FROM problem_records WHERE problem_id=%s FOR UPDATE",
            (problem_id,),
        )
        current_problem = cur.fetchone()
        if (not current_problem
                or current_problem["owner_team_id"] != problem_context.team_id):
            raise ProblemError("Problem scope changed; reload and try again.")
        cur.execute(
            """SELECT requester_employee_id,assigned_team_id
               FROM incident_tickets WHERE ticket_id=%s FOR UPDATE""",
            (ticket_id,),
        )
        current_incident = cur.fetchone()
        if (not current_incident
                or current_incident["requester_employee_id"] != incident["requester_employee_id"]
                or current_incident["assigned_team_id"] != incident["assigned_team_id"]):
            raise ProblemError("Incident changed; reload and try again.")
        cur.execute(
            "INSERT INTO problem_incident_links (problem_id,ticket_id,linked_by) VALUES (%s,%s,%s)",
            (problem_id, ticket_id, actor_employee_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'PROBLEM_INCIDENT_LINKED','problem',%s,'SUCCESS')""",
            (actor_employee_id, str(problem_id)),
        )
        conn.commit()
    except IntegrityError as exc:
        conn.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise ProblemError("This incident is already linked to the problem.") from None
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def create_known_error(
    *, actor_employee_id: int, problem_id: int, title: str,
    symptoms: str, workaround: str,
) -> int:
    name = (title or "").strip()
    symptom_text = (symptoms or "").strip()
    workaround_text = (workaround or "").strip()
    if not name or len(name) > 200 or not symptom_text or len(symptom_text) > 10000:
        raise ProblemError("Known error title and symptoms are required within the supported limits.")
    if not workaround_text or len(workaround_text) > 10000:
        raise ProblemError("A workaround is required (maximum 10,000 characters).")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        context = _problem_context(cur, problem_id)
        if not context:
            raise ProblemError("Problem was not found.")
        if not has_permission_in_transaction(
            cur, actor_employee_id, "problem.update", context
        ):
            raise ProblemError("Not authorized to manage known errors for this problem.")
        cur.execute(
            "SELECT status FROM problem_records WHERE problem_id=%s FOR UPDATE",
            (problem_id,),
        )
        row = cur.fetchone()
        if not row or row["status"] != "KNOWN_ERROR":
            raise ProblemError("Move the problem to KNOWN_ERROR before publishing its workaround.")
        cur.execute(
            """INSERT INTO known_error_records
               (problem_id,title,symptoms,workaround,created_by)
               VALUES (%s,%s,%s,%s,%s)""",
            (problem_id, name, symptom_text, workaround_text, actor_employee_id),
        )
        known_error_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'KNOWN_ERROR_CREATED','known_error',%s,'SUCCESS')""",
            (actor_employee_id, str(known_error_id)),
        )
        conn.commit()
        return known_error_id
    except IntegrityError as exc:
        conn.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise ProblemError("A known error already exists for this problem.") from None
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
