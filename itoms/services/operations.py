"""Team-scoped network, infrastructure and Oracle operations work queues."""
from __future__ import annotations

import re
import secrets

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission, has_permission_in_transaction


class OperationsError(ValueError):
    """Invalid or unauthorized operations request."""


DOMAINS = {"NETWORK", "INFRASTRUCTURE", "ORACLE"}
PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
WORK_STATUSES = {"OPEN", "IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED"}
WORK_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "BLOCKED", "CANCELLED"},
    "IN_PROGRESS": {"OPEN", "BLOCKED", "COMPLETED", "CANCELLED"},
    "BLOCKED": {"OPEN", "IN_PROGRESS", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}
ORACLE_LIFECYCLE = {"ACTIVE", "MAINTENANCE", "RETIRED"}


def list_operation_teams(*, actor_employee_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT t.team_id,t.team_name,t.department_id FROM teams t
               JOIN departments d ON d.department_id=t.department_id
               WHERE t.is_active=TRUE AND d.is_active=TRUE ORDER BY t.team_name"""
        )
        teams = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return [team for team in teams if has_permission(
        actor_employee_id, "operations.create",
        ResourceContext(team_id=team["team_id"], department_id=team["department_id"])
    )]


def list_operational_work_items(
    *, actor_employee_id: int, domain: str | None = None, status: str | None = None,
) -> list[dict]:
    if domain and domain not in DOMAINS:
        raise OperationsError("Invalid operations domain filter.")
    if status and status not in WORK_STATUSES:
        raise OperationsError("Invalid operations status filter.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT w.work_item_id,w.work_number,w.domain,w.title,w.description,
                      w.owner_team_id,w.assigned_to,w.priority,w.status,w.external_reference,
                      w.created_at,t.team_name,t.department_id,e.full_name AS assignee_name
               FROM operational_work_items w
               JOIN teams t ON t.team_id=w.owner_team_id
               JOIN departments d ON d.department_id=t.department_id
               LEFT JOIN employees e ON e.employee_id=w.assigned_to
               WHERE t.is_active=TRUE AND d.is_active=TRUE
                 AND (%s IS NULL OR w.domain=%s) AND (%s IS NULL OR w.status=%s)
               ORDER BY FIELD(w.priority,'CRITICAL','HIGH','MEDIUM','LOW'),
                        w.created_at DESC,w.work_item_id DESC LIMIT 500""",
            (domain, domain, status, status),
        )
        rows = cur.fetchall()
        visible = []
        for row in rows:
            context = ResourceContext(
                team_id=row["owner_team_id"], department_id=row["department_id"],
                resource_type="operational_work_item", resource_id=str(row["work_item_id"]),
            )
            if has_permission(actor_employee_id, "operations.read", context):
                row["can_update"] = has_permission(actor_employee_id, "operations.update", context)
                visible.append(row)
        return visible
    finally:
        cur.close()
        conn.close()


def create_operational_work_item(
    *, actor_employee_id: int, domain: str, title: str, description: str,
    owner_team_id: int, priority: str = "MEDIUM",
    assigned_to: int | None = None, external_reference: str = "",
) -> int:
    domain = (domain or "").strip().upper()
    name = (title or "").strip()
    detail = (description or "").strip()
    priority = (priority or "").strip().upper()
    reference = (external_reference or "").strip()
    if domain not in DOMAINS:
        raise OperationsError("Select a valid operations domain.")
    if not name or len(name) > 240 or not detail or len(detail) > 20000:
        raise OperationsError("A title (maximum 240) and description (maximum 20,000) are required.")
    if priority not in PRIORITIES:
        raise OperationsError("Select a valid priority.")
    if len(reference) > 150:
        raise OperationsError("External reference must be 150 characters or fewer.")
    if type(owner_team_id) is not int or owner_team_id <= 0:
        raise OperationsError("Select a valid owner team.")
    if assigned_to is not None and (type(assigned_to) is not int or assigned_to <= 0):
        raise OperationsError("Select a valid assignee.")

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
            raise OperationsError("Owner team is inactive or unavailable.")
        context = ResourceContext(team_id=owner_team_id, department_id=team[0])
        if not has_permission_in_transaction(
            cur, actor_employee_id, "operations.create", context,
            lock_employee_ids=[assigned_to] if assigned_to is not None else None,
        ):
            raise OperationsError("Not authorized to create work for this team.")
        cur.execute(
            "SELECT department_id,is_active FROM teams WHERE team_id=%s FOR UPDATE",
            (owner_team_id,),
        )
        locked_team = cur.fetchone()
        if not locked_team or not locked_team[1] or locked_team[0] != team[0]:
            raise OperationsError("Owner team changed; retry work creation.")
        cur.execute(
            "SELECT is_active FROM departments WHERE department_id=%s FOR UPDATE",
            (team[0],),
        )
        department = cur.fetchone()
        if not department or not department[0]:
            raise OperationsError("Owner department is inactive or unavailable.")
        if assigned_to is not None:
            cur.execute("SELECT is_active FROM employees WHERE employee_id=%s FOR UPDATE", (assigned_to,))
            assignee = cur.fetchone()
            if not assignee or not assignee[0]:
                raise OperationsError("Assignee must be an active member of the owner team.")
            cur.execute(
                """SELECT 1 FROM employee_team_memberships
                   WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
                (assigned_to, owner_team_id),
            )
            if not cur.fetchone():
                raise OperationsError("Assignee must be an active member of the owner team.")

        number = f"OPS-{domain[:3]}-{secrets.token_hex(4).upper()}"
        cur.execute(
            """INSERT INTO operational_work_items
               (work_number,domain,title,description,owner_team_id,assigned_to,
                priority,external_reference,created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (number, domain, name, detail, owner_team_id, assigned_to,
             priority, reference or None, actor_employee_id),
        )
        work_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'OPERATIONS_WORK_CREATED','operational_work_item',%s,'SUCCESS',
                       JSON_OBJECT('domain',%s,'work_number',%s))""",
            (actor_employee_id, str(work_id), domain, number),
        )
        conn.commit()
        return work_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def update_work_status(*, actor_employee_id: int, work_item_id: int, new_status: str) -> None:
    if new_status not in WORK_STATUSES:
        raise OperationsError("Invalid operations work status.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT w.status,w.owner_team_id,t.department_id
               FROM operational_work_items w JOIN teams t ON t.team_id=w.owner_team_id
               WHERE w.work_item_id=%s""",
            (work_item_id,),
        )
        snapshot = cur.fetchone()
        if not snapshot:
            raise OperationsError("Operations work item was not found.")
        context = ResourceContext(
            team_id=snapshot["owner_team_id"], department_id=snapshot["department_id"],
            resource_type="operational_work_item", resource_id=str(work_item_id),
        )
        if not has_permission_in_transaction(
            cur, actor_employee_id, "operations.update", context
        ):
            raise OperationsError("Not authorized to update this work item.")
        cur.execute(
            """SELECT status,owner_team_id FROM operational_work_items
               WHERE work_item_id=%s FOR UPDATE""",
            (work_item_id,),
        )
        row = cur.fetchone()
        if (not row or row["status"] != snapshot["status"]
                or row["owner_team_id"] != snapshot["owner_team_id"]):
            raise OperationsError("Operations work item changed; reload and try again.")
        old_status = row["status"]
        if new_status not in WORK_TRANSITIONS[old_status]:
            raise OperationsError(f"Cannot move work from {old_status} to {new_status}.")
        cur.execute(
            "UPDATE operational_work_items SET status=%s WHERE work_item_id=%s",
            (new_status, work_item_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'OPERATIONS_WORK_STATUS_CHANGED','operational_work_item',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(work_item_id), old_status, new_status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def list_manageable_services(*, actor_employee_id: int) -> list[dict]:
    """Return services for which the actor has explicit Oracle inventory management scope."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT s.service_id,s.service_key,s.service_name,s.owner_team_id,t.department_id
               FROM service_records s
               JOIN teams t ON t.team_id=s.owner_team_id
               JOIN departments d ON d.department_id=t.department_id
               WHERE t.is_active=TRUE AND d.is_active=TRUE
               ORDER BY s.service_name"""
        )
        rows = cur.fetchall()
        return [row for row in rows if has_permission(
            actor_employee_id, "oracle.inventory.manage",
            ResourceContext(
                team_id=row["owner_team_id"], department_id=row["department_id"],
                resource_type="service", resource_id=str(row["service_id"]),
            )
        )]
    finally:
        cur.close()
        conn.close()


def list_oracle_databases(*, actor_employee_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT o.oracle_database_id,o.service_id,o.environment_name,o.database_name,
                      o.host_reference,o.version_label,o.criticality,o.lifecycle_status,o.notes,
                      s.service_key,s.service_name,s.owner_team_id,t.department_id
               FROM oracle_database_inventory o
               JOIN service_records s ON s.service_id=o.service_id
               JOIN teams t ON t.team_id=s.owner_team_id
               JOIN departments d ON d.department_id=t.department_id
               WHERE t.is_active=TRUE AND d.is_active=TRUE
               ORDER BY s.service_name,o.environment_name,o.database_name LIMIT 500"""
        )
        rows = cur.fetchall()
        visible = []
        for row in rows:
            context = ResourceContext(
                team_id=row["owner_team_id"], department_id=row["department_id"],
                resource_type="service", resource_id=str(row["service_id"]),
            )
            if has_permission(actor_employee_id, "oracle.inventory.read", context):
                row["can_update"] = has_permission(actor_employee_id, "oracle.inventory.manage", context)
                visible.append(row)
        return visible
    finally:
        cur.close()
        conn.close()


def create_oracle_database(
    *, actor_employee_id: int, service_id: int, environment_name: str,
    database_name: str, host_reference: str, version_label: str = "",
    criticality: str = "MEDIUM", notes: str = "",
) -> int:
    environment = (environment_name or "").strip()
    database = (database_name or "").strip()
    host = (host_reference or "").strip()
    version = (version_label or "").strip()
    detail = (notes or "").strip()
    criticality = (criticality or "").strip().upper()
    if type(service_id) is not int or service_id <= 0:
        raise OperationsError("Select a valid owning service.")
    if not environment or len(environment) > 80:
        raise OperationsError("Environment name is required (maximum 80 characters).")
    if not database or len(database) > 128:
        raise OperationsError("Database name is required (maximum 128 characters).")
    secret_pattern = re.compile(r"(?i)(password\\s*=|passwd\\s*=|token\\s*=|secret\\s*=|://[^/\\s]+:[^/@\\s]+@)")
    if (not host or len(host) > 255
            or any(secret_pattern.search(value) for value in (host, detail, environment, database, version))):
        raise OperationsError("Oracle inventory fields cannot contain credentials and secrets, including tokens.")
    if len(version) > 80 or len(detail) > 10000:
        raise OperationsError("Version or notes exceed the allowed length.")
    if criticality not in PRIORITIES:
        raise OperationsError("Select a valid criticality.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT s.owner_team_id,t.department_id FROM service_records s
               JOIN teams t ON t.team_id=s.owner_team_id
               JOIN departments d ON d.department_id=t.department_id
               WHERE s.service_id=%s AND t.is_active=TRUE AND d.is_active=TRUE""",
            (service_id,),
        )
        service = cur.fetchone()
        if not service:
            raise OperationsError("Owning service is unavailable.")
        context = ResourceContext(
            team_id=service[0], department_id=service[1],
            resource_type="service", resource_id=str(service_id),
        )
        if not has_permission_in_transaction(
            cur, actor_employee_id, "oracle.inventory.manage", context
        ):
            raise OperationsError("Not authorized to manage Oracle inventory for this service.")
        cur.execute(
            """SELECT s.owner_team_id,t.department_id FROM service_records s
               JOIN teams t ON t.team_id=s.owner_team_id
               WHERE s.service_id=%s FOR UPDATE""",
            (service_id,),
        )
        locked_service = cur.fetchone()
        if not locked_service or locked_service[0] != service[0] or locked_service[1] != service[1]:
            raise OperationsError("Owning service changed; retry Oracle registration.")
        cur.execute(
            "SELECT is_active FROM departments WHERE department_id=%s FOR UPDATE",
            (service[1],),
        )
        department = cur.fetchone()
        if not department or not department[0]:
            raise OperationsError("Owning service department is inactive.")
        cur.execute(
            """INSERT INTO oracle_database_inventory
               (service_id,environment_name,database_name,host_reference,version_label,
                criticality,notes)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (service_id, environment, database, host, version or None, criticality, detail or None),
        )
        database_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'ORACLE_DATABASE_REGISTERED','oracle_database',%s,'SUCCESS')""",
            (actor_employee_id, str(database_id)),
        )
        conn.commit()
        return database_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()



def update_oracle_lifecycle(
    *, actor_employee_id: int, oracle_database_id: int, new_status: str,
) -> None:
    if new_status not in ORACLE_LIFECYCLE:
        raise OperationsError("Invalid Oracle database lifecycle status.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT o.lifecycle_status,o.service_id,s.owner_team_id,t.department_id
               FROM oracle_database_inventory o
               JOIN service_records s ON s.service_id=o.service_id
               JOIN teams t ON t.team_id=s.owner_team_id
               WHERE o.oracle_database_id=%s""",
            (oracle_database_id,),
        )
        snapshot = cur.fetchone()
        if not snapshot:
            raise OperationsError("Oracle database record was not found.")
        context = ResourceContext(
            team_id=snapshot["owner_team_id"], department_id=snapshot["department_id"],
            resource_type="service", resource_id=str(snapshot["service_id"]),
        )
        if not has_permission_in_transaction(
            cur, actor_employee_id, "oracle.inventory.manage", context
        ):
            raise OperationsError("Not authorized to update this Oracle database.")
        cur.execute(
            """SELECT lifecycle_status,service_id FROM oracle_database_inventory
               WHERE oracle_database_id=%s FOR UPDATE""",
            (oracle_database_id,),
        )
        row = cur.fetchone()
        if (not row or row["lifecycle_status"] != snapshot["lifecycle_status"]
                or row["service_id"] != snapshot["service_id"]):
            raise OperationsError("Oracle database record changed; reload and try again.")
        old_status = row["lifecycle_status"]
        if old_status == "RETIRED" and new_status != "RETIRED":
            raise OperationsError("Retired Oracle database records cannot be reactivated.")
        cur.execute(
            "UPDATE oracle_database_inventory SET lifecycle_status=%s WHERE oracle_database_id=%s",
            (new_status, oracle_database_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'ORACLE_DATABASE_LIFECYCLE_CHANGED','oracle_database',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(oracle_database_id), old_status, new_status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
