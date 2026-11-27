"""Incident service with permission checks, scoped access and transactional activity."""
from __future__ import annotations
from datetime import datetime, timezone
import secrets
from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission

class IncidentError(ValueError):
    """Incident operation is invalid or not permitted."""


def _incident_context(cur, ticket_id: int):
    """Load trusted requester, team and department attributes for authorization."""
    cur.execute("""SELECT i.requester_employee_id,i.assigned_team_id,
        COALESCE(t.department_id,e.department_id)
        FROM incident_tickets i
        LEFT JOIN employees e ON e.employee_id=i.requester_employee_id
        LEFT JOIN teams t ON t.team_id=i.assigned_team_id
        WHERE i.ticket_id=%s""", (ticket_id,))
    row = cur.fetchone()
    if not row:
        return None
    return ResourceContext(owner_employee_id=row[0], team_id=row[1], department_id=row[2])


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
    if not title or not description or len(title) > 240 or len(description) > 20000:
        raise IncidentError("A title (maximum 240 characters) and description (maximum 20,000 characters) are required.")
    if priority not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        raise IncidentError("Invalid incident priority.")
    if source not in {"PORTAL", "EMAIL", "PHONE", "GRAFANA", "ADMIN"}:
        raise IncidentError("Invalid incident source.")
    if bool(external_source) != bool(external_event_id):
        raise IncidentError("External source and event ID must be supplied together.")
    if external_source and (len(external_source) > 80 or len(external_event_id or "") > 190):
        raise IncidentError("External event identifiers exceed their supported lengths.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        requester = requester_employee_id or actor_employee_id
        cur.execute("SELECT department_id FROM employees WHERE employee_id=%s AND is_active=TRUE", (requester,))
        requester_row = cur.fetchone()
        if not requester_row:
            raise IncidentError("Requester does not exist or is inactive.")
        requester_department_id = requester_row[0]
        team_department_id = None
        if assigned_team_id is not None:
            cur.execute("""SELECT t.department_id FROM teams t
                JOIN departments d ON d.department_id=t.department_id AND d.is_active=TRUE
                WHERE t.team_id=%s AND t.is_active=TRUE""", (assigned_team_id,))
            team_row = cur.fetchone()
            if not team_row:
                raise IncidentError("Assigned team does not exist or is inactive.")
            team_department_id = team_row[0]
        create_context = ResourceContext(
            owner_employee_id=requester,
            team_id=assigned_team_id,
            department_id=team_department_id if assigned_team_id is not None else requester_department_id,
        )
        if not has_permission(actor_employee_id, "incident.create", create_context):
            raise IncidentError("Not authorized to create incidents for this requester or team.")
        if assigned_team_id is not None and not has_permission(
            actor_employee_id, "incident.assign",
            ResourceContext(team_id=assigned_team_id, department_id=team_department_id),
        ):
            raise IncidentError("Not authorized to assign new incidents to the selected team.")
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


def list_incidents(*, actor_employee_id: int, limit: int = 50, team_id: int | None = None, status: str | None = None, priority: str | None = None) -> list[dict]:
    """Return only incidents readable under the caller's OWN/TEAM/DEPARTMENT scopes."""
    limit = max(1, min(int(limit), 100))
    scope_clauses, scope_params = [], []
    if has_permission(actor_employee_id, "incident.read",
                      ResourceContext(owner_employee_id=actor_employee_id)):
        scope_clauses.append("i.requester_employee_id=%s")
        scope_params.append(actor_employee_id)

    accessible_teams = list_accessible_incident_teams(actor_employee_id=actor_employee_id)
    team_ids = [item["team_id"] for item in accessible_teams]
    if team_ids:
        scope_clauses.append("i.assigned_team_id IN (" + ",".join(["%s"] * len(team_ids)) + ")")
        scope_params.extend(team_ids)

    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT department_id FROM employees WHERE employee_id=%s AND is_active=TRUE",
                    (actor_employee_id,))
        actor_row = cur.fetchone()
        actor_department_id = actor_row[0] if actor_row else None
    finally:
        cur.close(); conn.close()
    if actor_department_id is not None and has_permission(
        actor_employee_id, "incident.read",
        ResourceContext(department_id=actor_department_id),
    ):
        scope_clauses.append("COALESCE(t.department_id,e.department_id)=%s")
        scope_params.append(actor_department_id)
    if not scope_clauses:
        return []

    filters, filter_params = [], []
    if team_id is not None:
        if team_id not in team_ids:
            return []
        filters.append("i.assigned_team_id=%s"); filter_params.append(team_id)
    if status in {"NEW", "OPEN", "IN_PROGRESS", "PENDING", "RESOLVED", "CLOSED", "CANCELLED"}:
        filters.append("i.status=%s"); filter_params.append(status)
    if priority in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        filters.append("i.priority=%s"); filter_params.append(priority)
    where = " WHERE (" + " OR ".join(scope_clauses) + ")"
    if filters:
        where += " AND " + " AND ".join(filters)

    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT i.ticket_id,i.ticket_number,i.title,i.status,i.priority,
            i.requester_employee_id,i.assigned_team_id,
            COALESCE(t.department_id,e.department_id) AS department_id,
            i.created_at,i.updated_at
            FROM incident_tickets i
            LEFT JOIN employees e ON e.employee_id=i.requester_employee_id
            LEFT JOIN teams t ON t.team_id=i.assigned_team_id""" + where +
            " ORDER BY i.created_at DESC,i.ticket_id DESC LIMIT %s",
            tuple(scope_params + filter_params + [limit]))
        candidates = cur.fetchall()
    finally:
        cur.close(); conn.close()

    visible = []
    for item in candidates:
        context = ResourceContext(
            owner_employee_id=item["requester_employee_id"],
            team_id=item["assigned_team_id"],
            department_id=item["department_id"],
        )
        if has_permission(actor_employee_id, "incident.read", context):
            visible.append(item)
    return visible

def transition_incident(*, actor_employee_id: int, ticket_id: int, new_status: str) -> None:
    """Apply an allowed state transition after checking trusted resource scope."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        context = _incident_context(cur, ticket_id)
    finally:
        cur.close()
        conn.close()
    if not context:
        raise IncidentError("Incident not found.")
    if not has_permission(actor_employee_id, "incident.update", context):
        raise IncidentError("Not authorized to update this incident.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT i.status,i.requester_employee_id,i.assigned_team_id,
            COALESCE(t.department_id,e.department_id)
            FROM incident_tickets i
            LEFT JOIN employees e ON e.employee_id=i.requester_employee_id
            LEFT JOIN teams t ON t.team_id=i.assigned_team_id
            WHERE i.ticket_id=%s FOR UPDATE""", (ticket_id,))
        row = cur.fetchone()
        if not row or row[1] != context.owner_employee_id or row[2] != context.team_id or row[3] != context.department_id:
            raise IncidentError("Incident changed; reload and try again.")
        if not has_permission(actor_employee_id, "incident.update", context):
            raise IncidentError("Not authorized to update this incident.")
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
            i.requester_employee_id,i.assigned_employee_id,i.assigned_team_id,
            COALESCE(t.department_id,e.department_id) AS department_id,
            i.first_response_due_at,i.resolution_due_at,i.first_responded_at,
            i.resolved_at,i.closed_at,i.created_at,i.updated_at
            FROM incident_tickets i
            LEFT JOIN employees e ON e.employee_id=i.requester_employee_id
            LEFT JOIN teams t ON t.team_id=i.assigned_team_id
            WHERE i.ticket_id=%s""", (ticket_id,))
        ticket = cur.fetchone()
        if not ticket:
            raise IncidentError("Incident not found.")
        context = ResourceContext(owner_employee_id=ticket["requester_employee_id"],
                                  team_id=ticket["assigned_team_id"],
                                  department_id=ticket["department_id"])
        if not has_permission(actor_employee_id, "incident.read", context):
            raise IncidentError("Incident not found.")
        cur.execute("""SELECT c.comment_id,c.author_employee_id,c.comment_body,c.is_internal,c.created_at,
            COALESCE(e.full_name,'Former or inactive user') AS author_name
            FROM incident_comments c
            LEFT JOIN employees e ON e.employee_id=c.author_employee_id AND e.is_active=TRUE
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
    if not body or len(body) > 20000:
        raise IncidentError("Comment is required and must be 20,000 characters or fewer.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT i.requester_employee_id,i.assigned_team_id,
            COALESCE(t.department_id,e.department_id)
            FROM incident_tickets i
            LEFT JOIN employees e ON e.employee_id=i.requester_employee_id
            LEFT JOIN teams t ON t.team_id=i.assigned_team_id
            WHERE i.ticket_id=%s""", (ticket_id,))
        row = cur.fetchone()
        if not row:
            raise IncidentError("Incident not found.")
        context = ResourceContext(owner_employee_id=row[0],team_id=row[1],department_id=row[2])
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
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'INCIDENT_COMMENT_ADDED','incident',%s,'SUCCESS')""",
            (actor_employee_id, str(ticket_id)))
        conn.commit()
        return comment_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def assign_incident(*, actor_employee_id: int, ticket_id: int,
                    assigned_team_id: int | None,
                    assigned_employee_id: int | None = None) -> None:
    """Assign an incident to an authorized team/member and audit the change."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT i.requester_employee_id,i.assigned_team_id,
            i.assigned_employee_id,COALESCE(t.department_id,e.department_id)
            FROM incident_tickets i
            LEFT JOIN employees e ON e.employee_id=i.requester_employee_id
            LEFT JOIN teams t ON t.team_id=i.assigned_team_id
            WHERE i.ticket_id=%s""", (ticket_id,))
        snapshot = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not snapshot:
        raise IncidentError("Incident not found.")
    requester_id, old_team_id, old_employee_id, old_department_id = snapshot
    old_context = ResourceContext(owner_employee_id=requester_id, team_id=old_team_id,
                                  department_id=old_department_id)
    if old_team_id is not None and not has_permission(actor_employee_id, "incident.assign", old_context):
        raise IncidentError("Not authorized to reassign this incident.")
    if assigned_team_id is None and old_team_id is None:
        raise IncidentError("Incident has no current team assignment.")
    if assigned_team_id is not None:
        check = get_connection()
        check_cur = check.cursor()
        try:
            check_cur.execute("""SELECT t.department_id FROM teams t
                JOIN departments d ON d.department_id=t.department_id AND d.is_active=TRUE
                WHERE t.team_id=%s AND t.is_active=TRUE""", (assigned_team_id,))
            team_row = check_cur.fetchone()
            if not team_row:
                raise IncidentError("Selected team is inactive or unavailable.")
            new_context = ResourceContext(owner_employee_id=requester_id,
                team_id=assigned_team_id, department_id=team_row[0])
            if not has_permission(actor_employee_id, "incident.assign", new_context):
                raise IncidentError("Not authorized to assign incidents to the selected team.")
            if assigned_employee_id is not None:
                check_cur.execute("""SELECT 1 FROM employees e
                    JOIN employee_team_memberships m ON m.employee_id=e.employee_id
                    WHERE e.employee_id=%s AND e.is_active=TRUE AND m.team_id=%s""",
                    (assigned_employee_id, assigned_team_id))
                if not check_cur.fetchone():
                    raise IncidentError("Assignee must be an active member of the selected team.")
        finally:
            check_cur.close()
            check.close()
    elif assigned_employee_id is not None:
        raise IncidentError("An individual assignee requires a team.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT i.requester_employee_id,i.assigned_team_id,
            i.assigned_employee_id,COALESCE(t.department_id,e.department_id)
            FROM incident_tickets i
            LEFT JOIN employees e ON e.employee_id=i.requester_employee_id
            LEFT JOIN teams t ON t.team_id=i.assigned_team_id
            WHERE i.ticket_id=%s FOR UPDATE""", (ticket_id,))
        row = cur.fetchone()
        if not row or row != snapshot:
            raise IncidentError("Incident assignment changed; reload and try again.")
        if old_team_id is not None and not has_permission(actor_employee_id, "incident.assign", old_context):
            raise IncidentError("Not authorized to reassign this incident.")
        if assigned_team_id is not None and not has_permission(actor_employee_id, "incident.assign", new_context):
            raise IncidentError("Not authorized to assign incidents to the selected team.")
        cur.execute("""UPDATE incident_tickets SET assigned_team_id=%s,assigned_employee_id=%s
            WHERE ticket_id=%s""", (assigned_team_id, assigned_employee_id, ticket_id))
        cur.execute("""INSERT INTO incident_activity
            (ticket_id,actor_employee_id,activity_key,old_value,new_value)
            VALUES (%s,%s,'ASSIGNMENT_CHANGED',%s,%s)""",
            (ticket_id, actor_employee_id,
             f"team={old_team_id};employee={old_employee_id}",
             f"team={assigned_team_id};employee={assigned_employee_id}"))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'INCIDENT_ASSIGNED','incident',%s,'SUCCESS')""",
            (actor_employee_id, str(ticket_id)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def list_assignable_teams(*, actor_employee_id: int, ticket_id: int) -> list[dict]:
    """List only active teams the actor may assign this incident to."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT i.requester_employee_id FROM incident_tickets i
            WHERE i.ticket_id=%s""", (ticket_id,))
        ticket = cur.fetchone()
        if not ticket:
            raise IncidentError("Incident not found.")
        cur.execute("""SELECT t.team_id,t.team_name,t.department_id FROM teams t
            JOIN departments d ON d.department_id=t.department_id AND d.is_active=TRUE
            WHERE t.is_active=TRUE ORDER BY t.team_name""")
        teams = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return [team for team in teams if has_permission(
        actor_employee_id, "incident.assign",
        ResourceContext(owner_employee_id=ticket["requester_employee_id"],
                        team_id=team["team_id"], department_id=team["department_id"]))]



def list_accessible_incident_teams(*, actor_employee_id: int) -> list[dict]:
    """Return active teams where the actor can read incident records."""
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT t.team_id,t.team_name,t.department_id FROM teams t
            JOIN departments d ON d.department_id=t.department_id AND d.is_active=TRUE
            WHERE t.is_active=TRUE ORDER BY t.team_name""")
        teams = cur.fetchall()
    finally:
        cur.close(); conn.close()
    return [team for team in teams if has_permission(actor_employee_id, "incident.read", ResourceContext(team_id=team["team_id"], department_id=team["department_id"]))]