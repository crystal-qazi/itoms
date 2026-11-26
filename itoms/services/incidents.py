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
        ticket_number = "INC-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + secrets.token_hex(3).upper()
        cur.execute("""INSERT INTO incident_tickets
            (ticket_number,title,description,category_id,requester_employee_id,assigned_team_id,
             priority,source,external_source,external_event_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (ticket_number,title,description,category_id,requester,assigned_team_id,
             priority,source,external_source,external_event_id))
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

def transition_incident(*, actor_employee_id: int, ticket_id: int, new_status: str) -> None:
    """Apply an allowed state transition after checking resource-scoped permission."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT status,requester_employee_id,assigned_team_id
            FROM incident_tickets WHERE ticket_id=%s FOR UPDATE""", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise IncidentError("Incident not found.")
        old_status, requester_id, team_id = row
        context = ResourceContext(owner_employee_id=requester_id, team_id=team_id)
        if not has_permission(actor_employee_id, "incident.update", context):
            raise IncidentError("Not authorized to update this incident.")
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
