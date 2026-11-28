"""Basic service request workflow with scoped access and audited history."""
from __future__ import annotations

from datetime import date, datetime, timezone
import secrets

from itoms.db.connection import get_connection
from itoms.services.authorization import (
    ResourceContext, has_permission, has_permission_in_transaction,
    has_permissions_in_transaction,
)


class ServiceRequestError(ValueError):
    """Service request operation is invalid or not authorized."""


TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "ON_HOLD", "CANCELLED"},
    "IN_PROGRESS": {"OPEN", "ON_HOLD", "COMPLETED", "CANCELLED"},
    "ON_HOLD": {"OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def _queue_request_notification(
    cur, *, recipient_employee_id: int | None, actor_employee_id: int,
    notification_type: str, title: str, body: str, request_id: int,
) -> None:
    """Queue an in-app notification inside the owning request transaction."""
    if not recipient_employee_id or recipient_employee_id == actor_employee_id:
        return
    cur.execute(
        "SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE",
        (recipient_employee_id,),
    )
    if not cur.fetchone():
        return
    cur.execute(
        """INSERT INTO notifications
           (recipient_employee_id,notification_type,title,body,target_type,target_id)
           VALUES (%s,%s,%s,%s,'service_request',%s)""",
        (recipient_employee_id, notification_type, title[:200], body[:2000], str(request_id)),
    )
    notification_id = int(cur.lastrowid)
    cur.execute(
        "INSERT INTO notification_outbox (notification_id,channel) VALUES (%s,'IN_APP')",
        (notification_id,),
    )


def list_comments(*, actor_employee_id: int, request_id: int) -> list[dict]:
    """List comments only after verifying the actor can read the request."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        context = _context(cur, request_id)
        if not context or not has_permission(actor_employee_id, "service_request.read", context):
            raise ServiceRequestError("Service request was not found.")
        cur.execute(
            """SELECT c.comment_id,c.body,c.created_at,c.author_employee_id,
                      e.full_name AS author_name
               FROM service_request_comments c
               JOIN employees e ON e.employee_id=c.author_employee_id
               WHERE c.request_id=%s
               ORDER BY c.created_at,c.comment_id""",
            (request_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def add_comment(*, actor_employee_id: int, request_id: int, body: str) -> int:
    """Add an escaped plain-text comment and queue an in-app notification atomically."""
    text = (body or "").strip()
    if not text or len(text) > 5000:
        raise ServiceRequestError("Comment must contain 1–5,000 characters.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Read a scope snapshot without taking resource locks. Authorization
        # locks are acquired first; the request row is locked afterwards and
        # its requester/team snapshot is revalidated before the write.
        context = _context(cur, request_id)
        if not context:
            raise ServiceRequestError("Service request was not found.")
        if not has_permission_in_transaction(
            cur, actor_employee_id, "service_request.update", context
        ):
            raise ServiceRequestError("Not authorized to comment on this service request.")
        cur.execute(
            """SELECT requester_employee_id,assigned_team_id,assigned_employee_id
               FROM service_requests WHERE request_id=%s FOR UPDATE""",
            (request_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ServiceRequestError("Service request was not found.")
        if row[0] != context.owner_employee_id or row[1] != context.team_id:
            raise ServiceRequestError("Service request scope changed; retry the operation.")
        assigned_employee_id = row[2]
        cur.execute(
            """INSERT INTO service_request_comments
               (request_id,author_employee_id,body) VALUES (%s,%s,%s)""",
            (request_id, actor_employee_id, text),
        )
        comment_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO service_request_activity
               (request_id,actor_employee_id,activity_key,new_value)
               VALUES (%s,%s,'REQUEST_COMMENTED','Comment added')""",
            (request_id, actor_employee_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'SERVICE_REQUEST_COMMENTED','service_request',%s,'SUCCESS')""",
            (actor_employee_id, str(request_id)),
        )
        _queue_request_notification(
            cur, recipient_employee_id=context.owner_employee_id,
            actor_employee_id=actor_employee_id,
            notification_type="SERVICE_REQUEST_COMMENT",
            title="New comment on your service request",
            body=f"A comment was added to service request #{request_id}.",
            request_id=request_id,
        )
        _queue_request_notification(
            cur, recipient_employee_id=assigned_employee_id,
            actor_employee_id=actor_employee_id,
            notification_type="SERVICE_REQUEST_COMMENT",
            title="New comment on an assigned service request",
            body=f"A comment was added to service request #{request_id}.",
            request_id=request_id,
        )
        conn.commit()
        return comment_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()



def _context(cur, request_id: int, *, lock: bool = False):
    """Load trusted requester, team and department context."""
    cur.execute(
        """SELECT r.requester_employee_id AS requester_employee_id,
                  r.assigned_team_id AS assigned_team_id,
                  COALESCE(t.department_id,e.department_id) AS department_id
           FROM service_requests r
           JOIN employees e ON e.employee_id=r.requester_employee_id
           LEFT JOIN teams t ON t.team_id=r.assigned_team_id
           WHERE r.request_id=%s""" + (" FOR UPDATE" if lock else ""),
        (request_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    if isinstance(row, dict):
        owner_employee_id = row["requester_employee_id"]
        team_id = row["assigned_team_id"]
        department_id = row["department_id"]
    else:
        owner_employee_id, team_id, department_id = row
    return ResourceContext(
        owner_employee_id=owner_employee_id, team_id=team_id, department_id=department_id
    )


def list_categories(*, include_inactive: bool = False) -> list[dict]:
    """List service request categories for request forms."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT category_id,category_name,description,is_active
               FROM service_request_categories
               WHERE (%s=TRUE OR is_active=TRUE)
               ORDER BY category_name""",
            (include_inactive,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def list_category_admin(*, actor_employee_id: int) -> list[dict]:
    """List all categories for an authorized administrator."""
    if not has_permission(actor_employee_id, "service_request.categories.manage"):
        raise ServiceRequestError("Not authorized to manage service request categories.")
    return list_categories(include_inactive=True)


def create_category(*, actor_employee_id: int, category_name: str, description: str = "") -> int:
    """Create an Admin-managed request category and audit the change."""
    name = (category_name or "").strip()
    detail = (description or "").strip()
    if not 2 <= len(name) <= 120 or len(detail) > 500:
        raise ServiceRequestError("Category name must be 2–120 characters and description at most 500.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(
            cur, actor_employee_id, "service_request.categories.manage"
        ):
            raise ServiceRequestError("Not authorized to manage service request categories.")
        cur.execute(
            """INSERT INTO service_request_categories
               (category_name,description,created_by) VALUES (%s,%s,%s)""",
            (name, detail or None, actor_employee_id),
        )
        category_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'SERVICE_REQUEST_CATEGORY_CREATED','service_request_category',%s,'SUCCESS',
                       JSON_OBJECT('category_name',%s))""",
            (actor_employee_id, str(category_id), name),
        )
        conn.commit()
        return category_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def set_category_active(*, actor_employee_id: int, category_id: int, is_active: bool) -> bool:
    """Activate/deactivate a category; existing requests retain their category reference."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(
            cur, actor_employee_id, "service_request.categories.manage"
        ):
            raise ServiceRequestError("Not authorized to manage service request categories.")
        cur.execute(
            "SELECT category_name,is_active FROM service_request_categories WHERE category_id=%s FOR UPDATE",
            (category_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ServiceRequestError("Service request category was not found.")
        if bool(row[1]) == bool(is_active):
            conn.commit()
            return False
        cur.execute(
            "UPDATE service_request_categories SET is_active=%s WHERE category_id=%s",
            (bool(is_active), category_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'SERVICE_REQUEST_CATEGORY_UPDATED','service_request_category',%s,'SUCCESS',
                       JSON_OBJECT('category_name',%s,'is_active',%s))""",
            (actor_employee_id, str(category_id), row[0], bool(is_active)),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def list_priorities(*, include_inactive: bool = False) -> list[dict]:
    """List configured Service Request priorities in their administrator-defined order."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT priority_key,priority_label,sort_order,is_active
               FROM service_request_priorities
               WHERE (%s=TRUE OR is_active=TRUE)
               ORDER BY sort_order,priority_key""",
            (include_inactive,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def list_priority_admin(*, actor_employee_id: int) -> list[dict]:
    """List active and inactive priorities for an authorized administrator."""
    if not has_permission(actor_employee_id, "service_request.priorities.manage"):
        raise ServiceRequestError("Not authorized to manage service request priorities.")
    return list_priorities(include_inactive=True)


def create_priority(
    *, actor_employee_id: int, priority_key: str, priority_label: str, sort_order: int = 100,
) -> str:
    """Create a priority level with transaction-bound authorization and audit."""
    key = (priority_key or "").strip().upper()
    label = (priority_label or "").strip()
    if (not key.isascii() or not 2 <= len(key) <= 30 or not key[0].isalpha()
            or not key.replace("_", "").isalnum()):
        raise ServiceRequestError("Priority key must be 2–30 ASCII letters, numbers or underscores.")
    if not 1 <= len(label) <= 60:
        raise ServiceRequestError("Priority label must contain 1–60 characters.")
    if type(sort_order) is not int or not 0 <= sort_order <= 9999:
        raise ServiceRequestError("Priority sort order must be between 0 and 9,999.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(
            cur, actor_employee_id, "service_request.priorities.manage"
        ):
            raise ServiceRequestError("Not authorized to manage service request priorities.")
        cur.execute(
            """INSERT INTO service_request_priorities
               (priority_key,priority_label,sort_order,created_by)
               VALUES (%s,%s,%s,%s)""",
            (key, label, sort_order, actor_employee_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'SERVICE_REQUEST_PRIORITY_CREATED','service_request_priority',%s,'SUCCESS',
                       JSON_OBJECT('priority_label',%s,'sort_order',%s))""",
            (actor_employee_id, key, label, sort_order),
        )
        conn.commit()
        return key
    except Exception as exc:
        conn.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise ServiceRequestError("Priority key or display label already exists.") from exc
        raise
    finally:
        cur.close()
        conn.close()


def update_priority(
    *, actor_employee_id: int, priority_key: str, priority_label: str,
    sort_order: int, is_active: bool,
) -> bool:
    """Update a priority's label/order/availability without changing its stable key."""
    key = (priority_key or "").strip().upper()
    label = (priority_label or "").strip()
    if not key or len(key) > 30 or not 1 <= len(label) <= 60:
        raise ServiceRequestError("A valid priority key and 1–60 character label are required.")
    if type(sort_order) is not int or not 0 <= sort_order <= 9999:
        raise ServiceRequestError("Priority sort order must be between 0 and 9,999.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(
            cur, actor_employee_id, "service_request.priorities.manage"
        ):
            raise ServiceRequestError("Not authorized to manage service request priorities.")
        # Serialize priority activation changes by locking the complete small
        # catalogue in stable key order before checking the active-count invariant.
        cur.execute(
            """SELECT priority_key,priority_label,sort_order,is_active
               FROM service_request_priorities ORDER BY priority_key FOR UPDATE"""
        )
        catalogue = cur.fetchall()
        row = next((item for item in catalogue if item[0] == key), None)
        if not row:
            raise ServiceRequestError("Service Request priority was not found.")
        if bool(row[3]) and not bool(is_active):
            active_count = sum(1 for item in catalogue if bool(item[3]))
            if active_count <= 1:
                raise ServiceRequestError("At least one active Service Request priority must remain.")
        changed = (row[1] != label or int(row[2]) != sort_order or bool(row[3]) != bool(is_active))
        if not changed:
            conn.commit()
            return False
        cur.execute(
            """UPDATE service_request_priorities
               SET priority_label=%s,sort_order=%s,is_active=%s
               WHERE priority_key=%s""",
            (label, sort_order, bool(is_active), key),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'SERVICE_REQUEST_PRIORITY_UPDATED','service_request_priority',%s,'SUCCESS',
                       JSON_OBJECT('priority_label',%s,'sort_order',%s,'is_active',%s))""",
            (actor_employee_id, key, label, sort_order, bool(is_active)),
        )
        conn.commit()
        return True
    except Exception as exc:
        conn.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise ServiceRequestError("Priority display label already exists.") from exc
        raise
    finally:
        cur.close()
        conn.close()


def create_request(
    *, actor_employee_id: int, title: str, description: str,
    category_id: int | None = None, priority: str | None = None,
    requester_employee_id: int | None = None,
) -> int:
    """Submit a basic request; no catalog, approval, SLA or fulfillment automation."""
    name, detail = (title or "").strip(), (description or "").strip()
    if not name or len(name) > 240 or not detail or len(detail) > 20000:
        raise ServiceRequestError("A title (maximum 240) and description (maximum 20,000) are required.")
    priority_key = (priority or "").strip().upper() or None
    if priority_key and (len(priority_key) > 30 or not priority_key.isascii()):
        raise ServiceRequestError("Invalid service request priority.")
    requester_id = requester_employee_id or actor_employee_id
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT department_id FROM employees WHERE employee_id=%s AND is_active=TRUE",
            (requester_id,),
        )
        requester = cur.fetchone()
        if not requester:
            raise ServiceRequestError("Requester does not exist or is inactive.")
        if category_id is not None:
            cur.execute(
                "SELECT 1 FROM service_request_categories WHERE category_id=%s AND is_active=TRUE",
                (category_id,),
            )
            if not cur.fetchone():
                raise ServiceRequestError("Category does not exist or is inactive.")
        context = ResourceContext(
            owner_employee_id=requester_id,
            department_id=requester[0],
        )
        if not has_permission_in_transaction(
            cur, actor_employee_id, "service_request.create", context
        ):
            raise ServiceRequestError("Not authorized to submit a request for this employee.")
        if priority_key is None:
            cur.execute(
                """SELECT priority_key FROM service_request_priorities
                   WHERE is_active=TRUE ORDER BY sort_order,priority_key LIMIT 1 FOR UPDATE"""
            )
            default_priority = cur.fetchone()
            if not default_priority:
                raise ServiceRequestError("No active Service Request priority is configured.")
            priority_key = default_priority[0]
        cur.execute(
            """SELECT 1 FROM service_request_priorities
               WHERE priority_key=%s AND is_active=TRUE FOR UPDATE""",
            (priority_key,),
        )
        if not cur.fetchone():
            raise ServiceRequestError("Service Request priority does not exist or is inactive.")
        request_id = None
        for attempt in range(5):
            request_number = (
                "SR-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-"
                + secrets.token_hex(8).upper()
            )
            try:
                cur.execute(
                    """INSERT INTO service_requests
                       (request_number,title,description,category_id,requester_employee_id,priority,created_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (request_number, name, detail, category_id, requester_id, priority_key, actor_employee_id),
                )
            except Exception as exc:
                # The only unique key on this insert is request_number. Retry
                # that collision only; propagate every other database error.
                if getattr(exc, "errno", None) == 1062 and attempt < 4:
                    continue
                if getattr(exc, "errno", None) == 1062:
                    raise ServiceRequestError("Could not allocate a unique request number; retry the submission.") from exc
                raise
            request_id = int(cur.lastrowid)
            break
        if request_id is None:
            raise ServiceRequestError("Could not allocate a unique request number; retry the submission.")
        cur.execute(
            """INSERT INTO service_request_activity
               (request_id,actor_employee_id,activity_key,new_value)
               VALUES (%s,%s,'REQUEST_SUBMITTED',%s)""",
            (request_id, actor_employee_id, request_number),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'SERVICE_REQUEST_CREATED','service_request',%s,'SUCCESS')""",
            (actor_employee_id, str(request_id)),
        )
        conn.commit()
        return request_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def list_requests(
    *, actor_employee_id: int, status: str | None = None, priority: str | None = None,
    search: str | None = None, category_id: int | None = None,
    created_from: str | date | None = None, created_to: str | date | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return scoped requests with bounded keyword, category and date filters."""
    limit = max(1, min(int(limit), 200))
    if status and status not in TRANSITIONS:
        raise ServiceRequestError("Invalid service request status filter.")
    if priority and (len(priority) > 30 or not priority.isascii()):
        raise ServiceRequestError("Invalid service request priority filter.")
    search_text = (search or "").strip()
    if len(search_text) > 120:
        raise ServiceRequestError("Service Request search text must be at most 120 characters.")
    if category_id is not None and (type(category_id) is not int or category_id <= 0):
        raise ServiceRequestError("Invalid Service Request category filter.")

    def parse_date(value: str | date | None, label: str) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except ValueError as exc:
            raise ServiceRequestError(f"Invalid {label} date filter.") from exc

    start_date = parse_date(created_from, "start")
    end_date = parse_date(created_to, "end")
    if start_date and end_date and start_date > end_date:
        raise ServiceRequestError("Start date must not be later than end date.")

    search_pattern = f"%{search_text}%" if search_text else None
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    visible: list[dict] = []
    offset = 0
    try:
        if priority:
            cur.execute(
                "SELECT 1 FROM service_request_priorities WHERE priority_key=%s AND is_active=TRUE",
                (priority,),
            )
            if not cur.fetchone():
                raise ServiceRequestError("Invalid or inactive service request priority filter.")
        while len(visible) < limit:
            cur.execute(
                """SELECT r.request_id,r.request_number,r.title,r.priority,r.status,
                          r.requester_employee_id,e.full_name AS requester_name,
                          r.assigned_team_id,t.team_name,r.assigned_employee_id,
                          a.full_name AS assignee_name,c.category_id,c.category_name,
                          r.created_at,
                          COALESCE(t.department_id,e.department_id) AS department_id
                   FROM service_requests r
                   JOIN employees e ON e.employee_id=r.requester_employee_id
                   LEFT JOIN teams t ON t.team_id=r.assigned_team_id
                   LEFT JOIN employees a ON a.employee_id=r.assigned_employee_id
                   LEFT JOIN service_request_categories c ON c.category_id=r.category_id
                   WHERE (%s IS NULL OR r.status=%s)
                     AND (%s IS NULL OR r.priority=%s)
                     AND (%s IS NULL OR r.category_id=%s)
                     AND (%s IS NULL OR r.created_at >= %s)
                     AND (%s IS NULL OR r.created_at < DATE_ADD(%s, INTERVAL 1 DAY))
                     AND (%s IS NULL OR r.request_number LIKE %s
                          OR r.title LIKE %s OR r.description LIKE %s)
                   ORDER BY r.created_at DESC,r.request_id DESC
                   LIMIT 200 OFFSET %s""",
                (
                    status, status, priority, priority,
                    category_id, category_id,
                    start_date, start_date, end_date, end_date,
                    search_pattern, search_pattern, search_pattern, search_pattern,
                    offset,
                ),
            )
            batch = cur.fetchall()
            for row in batch:
                context = ResourceContext(
                    owner_employee_id=row["requester_employee_id"],
                    team_id=row["assigned_team_id"],
                    department_id=row["department_id"],
                )
                if has_permission(actor_employee_id, "service_request.read", context):
                    visible.append(row)
                    if len(visible) >= limit:
                        break
            if len(batch) < 200:
                break
            offset += 200
        return visible
    finally:
        cur.close()
        conn.close()


def get_request_detail(*, actor_employee_id: int, request_id: int) -> dict:
    """Fetch a request and its activity after a trusted resource-scope check."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT r.*,e.full_name AS requester_name,
                      a.full_name AS assignee_name,t.team_name,c.category_name,
                      COALESCE(t.department_id,e.department_id) AS department_id
               FROM service_requests r
               JOIN employees e ON e.employee_id=r.requester_employee_id
               LEFT JOIN employees a ON a.employee_id=r.assigned_employee_id
               LEFT JOIN teams t ON t.team_id=r.assigned_team_id
               LEFT JOIN service_request_categories c ON c.category_id=r.category_id
               WHERE r.request_id=%s""",
            (request_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ServiceRequestError("Service request was not found.")
        context = ResourceContext(
            owner_employee_id=row["requester_employee_id"],
            team_id=row["assigned_team_id"],
            department_id=row["department_id"],
        )
        if not has_permission(actor_employee_id, "service_request.read", context):
            raise ServiceRequestError("Service request was not found.")
        cur.execute(
            """SELECT h.activity_key,h.old_value,h.new_value,h.created_at,
                      e.full_name AS actor_name
               FROM service_request_activity h
               LEFT JOIN employees e ON e.employee_id=h.actor_employee_id
               WHERE h.request_id=%s ORDER BY h.created_at,h.activity_id""",
            (request_id,),
        )
        row["activity"] = cur.fetchall()
        return row
    finally:
        cur.close()
        conn.close()


def list_assignable_teams(*, actor_employee_id: int, request_id: int) -> list[dict]:
    """List only teams the actor may assign this particular request to."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        context = _context(cur, request_id)
        if not context or not has_permission(actor_employee_id, "service_request.assign", context):
            return []
        cur.execute(
            """SELECT t.team_id,t.team_name,t.department_id
               FROM teams t JOIN departments d ON d.department_id=t.department_id
               WHERE t.is_active=TRUE AND d.is_active=TRUE ORDER BY t.team_name"""
        )
        teams = cur.fetchall()
        return [
            team for team in teams
            if has_permission(
                actor_employee_id, "service_request.assign",
                ResourceContext(team_id=team["team_id"], department_id=team["department_id"]),
            )
        ]
    finally:
        cur.close()
        conn.close()


def list_assignable_members(
    *, actor_employee_id: int, request_id: int
) -> list[dict]:
    """List active employees in teams the actor may assign the request to."""
    teams = list_assignable_teams(actor_employee_id=actor_employee_id, request_id=request_id)
    team_ids = [int(team["team_id"]) for team in teams]
    if not team_ids:
        return []
    marks = ",".join(["%s"] * len(team_ids))
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""SELECT e.employee_id,e.full_name,m.team_id,t.team_name
                FROM employees e
                JOIN employee_team_memberships m ON m.employee_id=e.employee_id
                JOIN teams t ON t.team_id=m.team_id
                WHERE e.is_active=TRUE AND t.is_active=TRUE
                  AND m.team_id IN ({marks})
                ORDER BY t.team_name,e.full_name""",
            tuple(team_ids),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def assign_request(
    *, actor_employee_id: int, request_id: int,
    assigned_team_id: int | None, assigned_employee_id: int | None = None,
) -> None:
    """Assign a request to a team and optional active member of that team."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        context = _context(cur, request_id)
        if not context:
            raise ServiceRequestError("Service request was not found.")
        resources = [context]
        team_department_id = None
        if assigned_team_id is not None:
            cur.execute(
                """SELECT t.department_id FROM teams t
                   JOIN departments d ON d.department_id=t.department_id AND d.is_active=TRUE
                   WHERE t.team_id=%s AND t.is_active=TRUE""",
                (assigned_team_id,),
            )
            team = cur.fetchone()
            if not team:
                raise ServiceRequestError("Assigned team does not exist or is inactive.")
            team_department_id = team[0]
            resources.append(
                ResourceContext(team_id=assigned_team_id, department_id=team_department_id)
            )
        if not has_permissions_in_transaction(
            cur, actor_employee_id, "service_request.assign", resources
        ):
            raise ServiceRequestError("Not authorized to assign this service request or selected team.")
        if assigned_team_id is not None:
            cur.execute(
                """SELECT t.department_id,t.is_active,d.is_active
                   FROM teams t JOIN departments d ON d.department_id=t.department_id
                   WHERE t.team_id=%s FOR UPDATE""",
                (assigned_team_id,),
            )
            locked_team = cur.fetchone()
            if (not locked_team or not locked_team[1] or not locked_team[2]
                    or locked_team[0] != team_department_id):
                raise ServiceRequestError("Assigned team or department changed; retry the operation.")
        if assigned_employee_id is not None:
            if assigned_team_id is None:
                raise ServiceRequestError("An individual assignee must belong to an assigned team.")
            cur.execute(
                """SELECT 1 FROM employees e
                   JOIN employee_team_memberships m ON m.employee_id=e.employee_id
                   WHERE e.employee_id=%s AND e.is_active=TRUE AND m.team_id=%s""",
                (assigned_employee_id, assigned_team_id),
            )
            if not cur.fetchone():
                raise ServiceRequestError("Assignee must be an active member of the selected team.")
        cur.execute(
            """SELECT status,requester_employee_id,assigned_team_id
               FROM service_requests WHERE request_id=%s FOR UPDATE""",
            (request_id,),
        )
        current = cur.fetchone()
        if not current:
            raise ServiceRequestError("Service request was not found.")
        if current[1] != context.owner_employee_id or current[2] != context.team_id:
            raise ServiceRequestError("Service request scope changed; retry the operation.")
        if current[0] in {"COMPLETED", "CANCELLED"}:
            raise ServiceRequestError("Closed requests cannot be reassigned.")
        cur.execute(
            """UPDATE service_requests SET assigned_team_id=%s,assigned_employee_id=%s
               WHERE request_id=%s""",
            (assigned_team_id, assigned_employee_id, request_id),
        )
        new_value = f"team={assigned_team_id or ''};employee={assigned_employee_id or ''}"
        cur.execute(
            """INSERT INTO service_request_activity
               (request_id,actor_employee_id,activity_key,old_value,new_value)
               VALUES (%s,%s,'REQUEST_ASSIGNED',%s,%s)""",
            (request_id, actor_employee_id, "", new_value),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'SERVICE_REQUEST_ASSIGNED','service_request',%s,'SUCCESS',
                       JSON_OBJECT('team_id',%s,'employee_id',%s))""",
            (actor_employee_id, str(request_id), assigned_team_id, assigned_employee_id),
        )
        _queue_request_notification(
            cur, recipient_employee_id=context.owner_employee_id,
            actor_employee_id=actor_employee_id,
            notification_type="SERVICE_REQUEST_ASSIGNMENT",
            title="Your service request was assigned",
            body=f"Service request #{request_id} has been assigned to a team.",
            request_id=request_id,
        )
        _queue_request_notification(
            cur, recipient_employee_id=assigned_employee_id,
            actor_employee_id=actor_employee_id,
            notification_type="SERVICE_REQUEST_ASSIGNMENT",
            title="A service request was assigned to you",
            body=f"Service request #{request_id} has been assigned to you.",
            request_id=request_id,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def transition_request(
    *, actor_employee_id: int, request_id: int, new_status: str,
    resolution_notes: str = "", pending_reason: str = "",
) -> None:
    """Move a request through the basic handling lifecycle and record closure details."""
    if new_status not in TRANSITIONS:
        raise ServiceRequestError("Invalid service request status.")
    notes = (resolution_notes or "").strip()
    hold_reason = (pending_reason or "").strip()
    if new_status == "COMPLETED" and not notes:
        raise ServiceRequestError("Resolution notes are required to complete a service request.")
    if new_status == "ON_HOLD" and not hold_reason:
        raise ServiceRequestError("A pending reason is required to put a service request on hold.")
    if len(notes) > 20000:
        raise ServiceRequestError("Resolution notes must be at most 20,000 characters.")
    if len(hold_reason) > 2000:
        raise ServiceRequestError("Pending reason must be at most 2,000 characters.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        context = _context(cur, request_id)
        if not context:
            raise ServiceRequestError("Service request was not found.")
        if not has_permission_in_transaction(
            cur, actor_employee_id, "service_request.update", context
        ):
            raise ServiceRequestError("Not authorized to update this service request.")
        cur.execute(
            """SELECT status,pending_reason,requester_employee_id,assigned_team_id
               FROM service_requests WHERE request_id=%s FOR UPDATE""",
            (request_id,),
        )
        row = cur.fetchone()
        if not row:
            raise ServiceRequestError("Service request was not found.")
        if row[2] != context.owner_employee_id or row[3] != context.team_id:
            raise ServiceRequestError("Service request scope changed; retry the operation.")
        old_status, current_pending_reason, requester_employee_id, _assigned_team_id = row
        next_pending_reason = (
            hold_reason if new_status == "ON_HOLD"
            else (None if old_status == "ON_HOLD" else current_pending_reason)
        )
        if new_status not in TRANSITIONS[old_status]:
            raise ServiceRequestError(f"Cannot move a service request from {old_status} to {new_status}.")
        cur.execute(
            """UPDATE service_requests
               SET status=%s,pending_reason=%s,
                   resolution_notes=CASE WHEN %s='COMPLETED' THEN %s ELSE resolution_notes END,
                   completed_at=CASE WHEN %s='COMPLETED' THEN UTC_TIMESTAMP() ELSE completed_at END,
                   cancelled_at=CASE WHEN %s='CANCELLED' THEN UTC_TIMESTAMP() ELSE cancelled_at END
               WHERE request_id=%s""",
            (new_status, next_pending_reason, new_status, notes or None,
             new_status, new_status, request_id),
        )
        cur.execute(
            """INSERT INTO service_request_activity
               (request_id,actor_employee_id,activity_key,old_value,new_value,reason)
               VALUES (%s,%s,'REQUEST_STATUS_CHANGED',%s,%s,%s)""",
            (request_id, actor_employee_id, old_status, new_status,
             hold_reason if new_status == "ON_HOLD" else None),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'SERVICE_REQUEST_STATUS_CHANGED','service_request',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(request_id), old_status, new_status),
        )
        _queue_request_notification(
            cur, recipient_employee_id=requester_employee_id,
            actor_employee_id=actor_employee_id,
            notification_type="SERVICE_REQUEST_STATUS",
            title="Your service request was updated",
            body=f"Service request #{request_id} is now {new_status.replace('_', ' ')}.",
            request_id=request_id,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
