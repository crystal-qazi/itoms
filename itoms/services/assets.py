"""Scoped asset register and basic repair-ticket workflows."""
from __future__ import annotations

import re
from mysql.connector import IntegrityError

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission


class AssetError(ValueError):
    """Invalid or unauthorized asset operation."""


ASSET_STATUSES = {"IN_USE", "IN_STOCK", "UNDER_REPAIR", "RETIRED", "LOST"}
MAINTENANCE_STATUSES = {"OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"}
MAINTENANCE_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "ON_HOLD", "CANCELLED"},
    "IN_PROGRESS": {"OPEN", "ON_HOLD", "COMPLETED", "CANCELLED"},
    "ON_HOLD": {"OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def list_asset_teams(*, actor_employee_id: int, permission: str = "asset.create") -> list[dict]:
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
        actor_employee_id, permission,
        ResourceContext(team_id=team["team_id"], department_id=team["department_id"])
    )]


def _asset_context(cur, asset_id: int, *, lock: bool = False):
    cur.execute(
        """SELECT a.asset_id,a.asset_status,a.owner_team_id,t.department_id
           FROM asset_records a JOIN teams t ON t.team_id=a.owner_team_id
           JOIN departments d ON d.department_id=t.department_id
           WHERE a.asset_id=%s AND t.is_active=TRUE AND d.is_active=TRUE"""
        + (" FOR UPDATE" if lock else ""),
        (asset_id,),
    )
    row = cur.fetchone()
    if not row:
        return None
    return row


def _context_value(row, key: str, index: int):
    return row[key] if isinstance(row, dict) else row[index]


def list_assets(*, actor_employee_id: int, status: str | None = None) -> list[dict]:
    if status and status not in ASSET_STATUSES:
        raise AssetError("Invalid asset status filter.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT a.asset_id,a.asset_tag,a.asset_name,a.asset_type,a.serial_number,
                      a.manufacturer,a.model,a.assigned_employee_id,a.owner_team_id,
                      a.location_label,a.asset_status,a.acquired_on,a.created_at,
                      t.team_name,t.department_id,e.full_name AS assignee_name
               FROM asset_records a
               JOIN teams t ON t.team_id=a.owner_team_id
               JOIN departments d ON d.department_id=t.department_id
               LEFT JOIN employees e ON e.employee_id=a.assigned_employee_id
               WHERE t.is_active=TRUE AND d.is_active=TRUE
                 AND (%s IS NULL OR a.asset_status=%s)
               ORDER BY a.asset_tag LIMIT 500""",
            (status, status),
        )
        rows = cur.fetchall()
        visible = []
        for row in rows:
            context = ResourceContext(
                team_id=row["owner_team_id"], department_id=row["department_id"],
                resource_type="asset", resource_id=str(row["asset_id"]),
            )
            if has_permission(actor_employee_id, "asset.read", context):
                row["can_update"] = has_permission(actor_employee_id, "asset.update", context)
                visible.append(row)
        return visible
    finally:
        cur.close()
        conn.close()


def create_asset(
    *, actor_employee_id: int, asset_tag: str, asset_name: str, asset_type: str,
    owner_team_id: int, serial_number: str = "", manufacturer: str = "",
    model: str = "", location_label: str = "", acquired_on: str | None = None,
    assigned_employee_id: int | None = None,
) -> int:
    tag = (asset_tag or "").strip().upper()
    name = (asset_name or "").strip()
    kind = (asset_type or "").strip()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{1,99}", tag):
        raise AssetError("Asset tag must be 2–100 letters, numbers, dots, underscores or hyphens.")
    if not name or len(name) > 200:
        raise AssetError("Asset name is required (maximum 200 characters).")
    if not kind or len(kind) > 80:
        raise AssetError("Asset type is required (maximum 80 characters).")
    fields = [serial_number, manufacturer, model, location_label]
    limits = [150, 150, 150, 200]
    if any(len((value or "").strip()) > limit for value, limit in zip(fields, limits)):
        raise AssetError("One or more optional asset fields exceed their allowed length.")
    date_value = (acquired_on or "").strip() or None
    if date_value:
        import datetime
        try:
            datetime.date.fromisoformat(date_value)
        except ValueError:
            raise AssetError("Acquired date must be a valid ISO date.") from None
    if type(owner_team_id) is not int or owner_team_id <= 0:
        raise AssetError("Select a valid owner team.")
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
            raise AssetError("Owner team is inactive or unavailable.")
        context = ResourceContext(team_id=owner_team_id, department_id=team[0])
        if not has_permission(actor_employee_id, "asset.create", context):
            raise AssetError("Not authorized to register assets for this team.")
        if assigned_employee_id is not None:
            cur.execute(
                """SELECT 1 FROM employees e JOIN employee_team_memberships m
                   ON m.employee_id=e.employee_id
                   WHERE e.employee_id=%s AND e.is_active=TRUE AND m.team_id=%s""",
                (assigned_employee_id, owner_team_id),
            )
            if not cur.fetchone():
                raise AssetError("Assignee must be an active member of the owner team.")
        cur.execute(
            """INSERT INTO asset_records
               (asset_tag,asset_name,asset_type,serial_number,manufacturer,model,
                assigned_employee_id,owner_team_id,location_label,acquired_on)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (tag, name, kind, (serial_number or "").strip() or None,
             (manufacturer or "").strip() or None, (model or "").strip() or None,
             assigned_employee_id, owner_team_id, (location_label or "").strip() or None,
             date_value),
        )
        asset_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'ASSET_CREATED','asset',%s,'SUCCESS')""",
            (actor_employee_id, str(asset_id)),
        )
        conn.commit()
        return asset_id
    except IntegrityError as exc:
        conn.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise AssetError("An asset with this tag already exists.") from None
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def update_asset_status(*, actor_employee_id: int, asset_id: int, new_status: str) -> None:
    if new_status not in ASSET_STATUSES:
        raise AssetError("Invalid asset status.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        row = _asset_context(cur, asset_id)
        if not row:
            raise AssetError("Asset was not found.")
        team_id = _context_value(row, "owner_team_id", 2)
        department_id = _context_value(row, "department_id", 3)
        context = ResourceContext(
            team_id=team_id, department_id=department_id,
            resource_type="asset", resource_id=str(asset_id),
        )
        if not has_permission(actor_employee_id, "asset.update", context):
            raise AssetError("Not authorized to update this asset.")
        old_status = _context_value(row, "asset_status", 1)
        cur.execute("SELECT asset_status FROM asset_records WHERE asset_id=%s FOR UPDATE", (asset_id,))
        current = cur.fetchone()
        current_status = current["asset_status"] if isinstance(current, dict) else current[0]
        if current_status != old_status:
            raise AssetError("Asset changed; reload and try again.")
        cur.execute("UPDATE asset_records SET asset_status=%s WHERE asset_id=%s", (new_status, asset_id))
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'ASSET_STATUS_CHANGED','asset',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(asset_id), old_status, new_status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def list_maintenance(*, actor_employee_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT m.maintenance_id,m.asset_id,m.issue_description,m.status,
                      m.opened_at,m.completed_at,m.assigned_to,a.asset_tag,a.asset_name,
                      a.owner_team_id,t.department_id,e.full_name AS reporter_name,
                      assignee.full_name AS assignee_name
               FROM asset_maintenance m
               JOIN asset_records a ON a.asset_id=m.asset_id
               JOIN teams t ON t.team_id=a.owner_team_id
               JOIN departments d ON d.department_id=t.department_id
               LEFT JOIN employees e ON e.employee_id=m.reported_by
               LEFT JOIN employees assignee ON assignee.employee_id=m.assigned_to
               WHERE t.is_active=TRUE AND d.is_active=TRUE
               ORDER BY m.opened_at DESC,m.maintenance_id DESC LIMIT 500"""
        )
        rows = cur.fetchall()
        visible = []
        for row in rows:
            context = ResourceContext(
                team_id=row["owner_team_id"], department_id=row["department_id"],
                resource_type="asset", resource_id=str(row["asset_id"]),
            )
            if has_permission(actor_employee_id, "asset.read", context):
                row["can_update"] = has_permission(actor_employee_id, "asset.maintenance.update", context)
                visible.append(row)
        return visible
    finally:
        cur.close()
        conn.close()


def create_maintenance(
    *, actor_employee_id: int, asset_id: int, issue_description: str,
    assigned_to: int | None = None,
) -> int:
    detail = (issue_description or "").strip()
    if not detail or len(detail) > 20000:
        raise AssetError("Repair issue description is required (maximum 20,000 characters).")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        row = _asset_context(cur, asset_id, lock=True)
        if not row:
            raise AssetError("Asset was not found.")
        team_id = _context_value(row, "owner_team_id", 2)
        department_id = _context_value(row, "department_id", 3)
        previous_status = _context_value(row, "asset_status", 1)
        if previous_status not in {"IN_USE", "IN_STOCK"}:
            raise AssetError("Only IN_USE or IN_STOCK assets can enter maintenance.")
        cur.execute(
            """SELECT maintenance_id FROM asset_maintenance
               WHERE asset_id=%s AND status IN ('OPEN','IN_PROGRESS','ON_HOLD')
               LIMIT 1 FOR UPDATE""",
            (asset_id,),
        )
        if cur.fetchone():
            raise AssetError("This asset already has an active maintenance ticket.")
        context = ResourceContext(
            team_id=team_id, department_id=department_id,
            resource_type="asset", resource_id=str(asset_id),
        )
        if not has_permission(actor_employee_id, "asset.maintenance.create", context):
            raise AssetError("Not authorized to report maintenance for this asset.")
        if assigned_to is not None:
            cur.execute(
                """SELECT 1 FROM employees e JOIN employee_team_memberships m
                   ON m.employee_id=e.employee_id
                   WHERE e.employee_id=%s AND e.is_active=TRUE AND m.team_id=%s""",
                (assigned_to, team_id),
            )
            if not cur.fetchone():
                raise AssetError("Maintenance assignee must be an active member of the owner team.")
        cur.execute(
            """INSERT INTO asset_maintenance
               (asset_id,reported_by,assigned_to,issue_description,previous_asset_status)
               VALUES (%s,%s,%s,%s,%s)""",
            (asset_id, actor_employee_id, assigned_to, detail, previous_status),
        )
        maintenance_id = int(cur.lastrowid)
        cur.execute("UPDATE asset_records SET asset_status='UNDER_REPAIR' WHERE asset_id=%s", (asset_id,))
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'ASSET_MAINTENANCE_OPENED','asset_maintenance',%s,'SUCCESS')""",
            (actor_employee_id, str(maintenance_id)),
        )
        conn.commit()
        return maintenance_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def update_maintenance_status(
    *, actor_employee_id: int, maintenance_id: int, new_status: str,
) -> None:
    if new_status not in MAINTENANCE_STATUSES:
        raise AssetError("Invalid maintenance status.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT m.asset_id,m.status,m.previous_asset_status,
                      a.owner_team_id,t.department_id
               FROM asset_maintenance m JOIN asset_records a ON a.asset_id=m.asset_id
               JOIN teams t ON t.team_id=a.owner_team_id
               WHERE m.maintenance_id=%s FOR UPDATE""",
            (maintenance_id,),
        )
        row = cur.fetchone()
        if not row:
            raise AssetError("Maintenance ticket was not found.")
        context = ResourceContext(
            team_id=row["owner_team_id"], department_id=row["department_id"],
            resource_type="asset", resource_id=str(row["asset_id"]),
        )
        if not has_permission(actor_employee_id, "asset.maintenance.update", context):
            raise AssetError("Not authorized to update this maintenance ticket.")
        old_status = row["status"]
        if new_status not in MAINTENANCE_TRANSITIONS[old_status]:
            raise AssetError(f"Cannot move maintenance from {old_status} to {new_status}.")
        cur.execute(
            """UPDATE asset_maintenance SET status=%s,
               completed_at=CASE WHEN %s='COMPLETED' THEN UTC_TIMESTAMP() ELSE NULL END
               WHERE maintenance_id=%s""",
            (new_status, new_status, maintenance_id),
        )
        if new_status == "COMPLETED":
            cur.execute(
                """UPDATE asset_records SET asset_status=%s
                   WHERE asset_id=%s AND asset_status='UNDER_REPAIR'""",
                (row["previous_asset_status"] or "IN_USE", row["asset_id"]),
            )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'ASSET_MAINTENANCE_STATUS_CHANGED','asset_maintenance',%s,'SUCCESS',
                       JSON_OBJECT('old_status',%s,'new_status',%s))""",
            (actor_employee_id, str(maintenance_id), old_status, new_status),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
