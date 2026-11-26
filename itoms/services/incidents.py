"""Incident service with permission checks, scoped access and transactional activity."""
from __future__ import annotations
from datetime import datetime, timezone
import secrets
from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission

class IncidentError(ValueError):
    """Incident operation is invalid or not permitted."""

TRANSITIONS = {
    "NEW": {"OPEN", "CANCELLED"},
    "OPEN": {"IN_PROGRESS", "PENDING", "RESOLVED", "CANCELLED"},
    "IN_PROGRESS": {"PENDING", "RESOLVED", "OPEN"},
    "PENDING": {"IN_PROGRESS", "RESOLVED", "OPEN"},
    "RESOLVED": {"CLOSED", "OPEN"},
    "CLOSED": set(),
    "CANCELLED": set(),
}

def create_incident(*, actor_employee_id: int, title: str, description: str,
                    priority: str = "MEDIUM", requester_employee_id: int | None = None,
                    assigned_team_id: int | None = None, category_id: int | None = None,
                    source: str = "PORTAL", external_source: str | None = None,
                    external_event_id: str | None = None) -> int:
    """Create a ticket; external event identifiers make webhook retries idempotent."""
    if not has_permission(actor_employee_id, "incident.create"):
        raise IncidentError("Not authorized to create incidents.")
    title, description = title.strip(), description.strip()
    if not title or not description or len(title) > 240:
        raise IncidentError("A title (maximum 240 characters) and description are required.")
    if priority not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        raise IncidentError("Invalid incident priority.")
    if source not in {"PORTAL", "EMAIL", "PHONE", "GRAFANA", "ADMIN"}:
        raise IncidentError("Invalid incident source.")
    if bool(external_source) != bool(external_event_id):
        raise IncidentError("External source and event ID must be supplied together.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        requester = requester_employee_id or actor_employee_id
        cur.execute("SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE", (requester,))
        if not cur.fetchone():
            raise IncidentError("Requester does not exist or is inactive.")
        if assigned_team_id is not None:
            cur.execute("SELECT 1 FROM teams WHERE team_id=%s AND is_active=TRUE", (assigned_team_id,))
            if not cur.fetchone():
                raise IncidentError("Assigned team does not exist or is inactive.")
        if category_id is not None:
            cur.execute("SELECT 1 FROM service_categories WHERE category_id=%s AND is_active=TRUE", (category_id,))
            if not cur.fetchone():
                raise IncidentError("Category does not exist or is inactive.")
        cur.execute("""SELECT first_response_minutes,resolution_minutes
            FROM incident_sla_policies WHERE priority=%s AND is_active=TRUE""", (priority,))
        sla = cur.fetchone()
        response_due = resolution_due = None
        if sla:
            cur.execute("SELECT DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s MINUTE), DATE_ADD(UTC_TIMESTAMP(), INTERVAL %s MINUTE)", (sla[0],sla[1]))
            response_due, resolution_due = cur.fetchone()
        ticket_number = "INC-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + secrets.token_hex(3).upper()
        cur.execute("""INSERT INTO incident_tickets
            (ticket_number,title,description,category_id,requester_employee_id,assigned_team_id,
             priority,source,external_source,external_event_id,first_response_due_at,resolution_due_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (ticket_number,title,description,category_id,requester,assigned_team_id,
             priority,source,external_source,external_event_id,response_due,resolution_due))
        ticket_id = int(cur.lastrowid)
        cur.execute("""INSERT INTO incident_activity
            (ticket_id,actor_employee_id,activity_key,new_value)
            VALUES (%s,%s,'TICKET_CREATED',%s)""", (ticket_id,actor_employee_id,ticket_number))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'INCIDENT_CREATED','incident',%s,'SUCCESS')""", (actor_employee_id,str(ticket_id)))
        conn.commit()
        return ticket_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def list_incidents(*, actor_employee_id: int, limit: int = 50) -> list[dict]:
    """Return only incidents readable under the caller's OWN/TEAM scopes."""
    limit = max(1, min(int(limit), 100))
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT ticket_id,ticket_number,title,status,priority,requester_employee_id,
            assigned_team_id,created_at,updated_at
            FROM incident_tickets ORDER BY created_at DESC,ticket_id DESC LIMIT %s""", (limit * 3,))
        candidates = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    visible = []
    for item in candidates:
        context = ResourceContext(owner_employee_id=item["requester_employee_id"],
                                  team_id=item["assigned_team_id"])
        if has_permission(actor_employee_id, "incident.read", context):
            visible.append(item)
            if len(visible) >= limit:
                break
    return visible

def transition_incident(*, actor_employee_id: int, ticket_id: int, new_status: str) -> None:
    """Apply an allowed state transition after checking trusted resource scope."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT requester_employee_id,assigned_team_id
            FROM incident_tickets WHERE ticket_id=%s""", (ticket_id,))
        snapshot = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not snapshot:
        raise IncidentError("Incident not found.")
    requester_id, team_id = snapshot
    context = ResourceContext(owner_employee_id=requester_id, team_id=team_id)
    if not has_permission(actor_employee_id, "incident.update", context):
        raise IncidentError("Not authorized to update this incident.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT status,requester_employee_id,assigned_team_id
            FROM incident_tickets WHERE ticket_id=%s FOR UPDATE""", (ticket_id,))
        row = cur.fetchone()
        if not row or row[1] != requester_id or row[2] != team_id:
            raise IncidentError("Incident changed; reload and try again.")
        old_status = row[0]
        if new_status not in TRANSITIONS.get(old_status, set()):
            raise IncidentError(f"Transition from {old_status} to {new_status} is not allowed.")
        cur.execute("""UPDATE incident_tickets SET status=%s,
            resolved_at=CASE WHEN %s='RESOLVED' THEN UTC_TIMESTAMP() WHEN %s='OPEN' THEN NULL ELSE resolved_at END,
            closed_at=CASE WHEN %s='CLOSED' THEN UTC_TIMESTAMP() ELSE closed_at END
            WHERE ticket_id=%s""", (new_status,new_status,new_status,new_status,ticket_id))
        cur.execute("""INSERT INTO incident_activity
            (ticket_id,actor_employee_id,activity_key,old_value,new_value)
            VALUES (%s,%s,'STATUS_CHANGED',%s,%s)""", (ticket_id,actor_employee_id,old_status,new_status))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'INCIDENT_STATUS_CHANGED','incident',%s,'SUCCESS')""", (actor_employee_id,str(ticket_id)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def get_incident_detail(*, actor_employee_id: int, ticket_id: int) -> dict:
    """Fetch a ticket and only comments visible to the caller's permissions."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT ticket_id,ticket_number,title,description,status,priority,source,
            requester_employee_id,assigned_employee_id,assigned_team_id,first_response_due_at,
            resolution_due_at,first_responded_at,resolved_at,closed_at,created_at,updated_at
            FROM incident_tickets WHERE ticket_id=%s""", (ticket_id,))
        ticket = cur.fetchone()
        if not ticket:
            raise IncidentError("Incident not found.")
        context = ResourceContext(owner_employee_id=ticket["requester_employee_id"],
                                  team_id=ticket["assigned_team_id"])
        if not has_permission(actor_employee_id, "incident.read", context):
            raise IncidentError("Incident not found.")
        cur.execute("""SELECT c.comment_id,c.author_employee_id,c.comment_body,c.is_internal,c.created_at,
            e.full_name AS author_name FROM incident_comments c
            JOIN employees e ON e.employee_id=c.author_employee_id
            WHERE c.ticket_id=%s ORDER BY c.created_at,c.comment_id""", (ticket_id,))
        comments = cur.fetchall()
        if not has_permission(actor_employee_id, "incident.comment.internal", context):
            comments = [item for item in comments if not item["is_internal"]]
        ticket["comments"] = comments
        return ticket
    finally:
        cur.close()
        conn.close()

def add_comment(*, actor_employee_id: int, ticket_id: int, body: str, internal: bool = False) -> int:
    """Add an authorized comment; internal visibility is explicit."""
    body = body.strip()
    if not body:
        raise IncidentError("Comment cannot be empty.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT requester_employee_id,assigned_team_id FROM incident_tickets WHERE ticket_id=%s", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise IncidentError("Incident not found.")
        context = ResourceContext(owner_employee_id=row[0],team_id=row[1])
        permission = "incident.comment.internal" if internal else "incident.comment"
        if not has_permission(actor_employee_id, permission, context):
            raise IncidentError("Not authorized to comment on this incident.")
        cur.execute("""INSERT INTO incident_comments
            (ticket_id,author_employee_id,comment_body,is_internal)
            VALUES (%s,%s,%s,%s)""", (ticket_id,actor_employee_id,body,internal))
        comment_id = int(cur.lastrowid)
        cur.execute("""INSERT INTO incident_activity
            (ticket_id,actor_employee_id,activity_key,new_value)
            VALUES (%s,%s,'COMMENT_ADDED',%s)""", (ticket_id,actor_employee_id,"INTERNAL" if internal else "PUBLIC"))
        conn.commit()
        return comment_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
