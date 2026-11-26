"""Service and software inventory operations with team-scoped access."""
from __future__ import annotations
import re
from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission

class ServiceInventoryError(ValueError):
    """Invalid or unauthorized service inventory operation."""

SERVICE_TYPES = {"APPLICATION", "DATABASE", "NETWORK", "INFRASTRUCTURE", "PLATFORM", "OTHER"}
SERVICE_STATUSES = {"PLANNED", "ACTIVE", "DEGRADED", "RETIRED"}
SERVICE_CRITICALITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

def list_service_teams(*, actor_employee_id: int, permission_key: str = "service.inventory.read") -> list[dict]:
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT team_id,team_name FROM teams WHERE is_active=TRUE ORDER BY team_name")
        teams = cur.fetchall()
    finally:
        cur.close(); conn.close()
    return [team for team in teams if has_permission(actor_employee_id, permission_key, ResourceContext(team_id=team["team_id"]))]

def list_service_records(*, actor_employee_id: int, lifecycle_status: str | None = None) -> list[dict]:
    clauses, params = [], []
    if lifecycle_status in SERVICE_STATUSES:
        clauses.append("s.lifecycle_status=%s"); params.append(lifecycle_status)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = get_connection(); cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT s.service_id,s.service_key,s.service_name,s.service_type,s.description,s.owner_team_id,s.criticality,s.lifecycle_status,s.created_at,t.team_name FROM service_records s LEFT JOIN teams t ON t.team_id=s.owner_team_id" + where + " ORDER BY s.service_name LIMIT 500", tuple(params))
        rows = cur.fetchall()
    finally:
        cur.close(); conn.close()
    visible = []
    for item in rows:
        context = ResourceContext(team_id=item["owner_team_id"], resource_type="service", resource_id=str(item["service_id"]))
        if has_permission(actor_employee_id, "service.inventory.read", context):
            item["can_update"] = has_permission(actor_employee_id, "service.inventory.update", context)
            visible.append(item)
    return visible

def create_service_record(*, actor_employee_id: int, service_key: str, service_name: str, service_type: str, owner_team_id: int, criticality: str = "MEDIUM", description: str = "") -> int:
    context = ResourceContext(team_id=owner_team_id)
    if not has_permission(actor_employee_id, "service.inventory.create", context):
        raise ServiceInventoryError("Not authorized to register services for this team.")
    service_key = service_key.strip().upper()
    service_name = service_name.strip()
    service_type = service_type.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{1,79}", service_key):
        raise ServiceInventoryError("Service key must be 2-80 characters using letters, numbers, dot, underscore or hyphen.")
    if not service_name or len(service_name) > 200: raise ServiceInventoryError("Service name is required (maximum 200 characters).")
    if service_type not in SERVICE_TYPES: raise ServiceInventoryError("Select a valid service type.")
    if criticality not in SERVICE_CRITICALITIES: raise ServiceInventoryError("Select a valid criticality.")
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM teams WHERE team_id=%s AND is_active=TRUE", (owner_team_id,))
        if not cur.fetchone(): raise ServiceInventoryError("Owner team is inactive or unavailable.")
        cur.execute("INSERT INTO service_records (service_key,service_name,service_type,description,owner_team_id,criticality) VALUES (%s,%s,%s,%s,%s,%s)", (service_key,service_name,service_type,description.strip(),owner_team_id,criticality))
        service_id = int(cur.lastrowid)
        cur.execute("INSERT INTO audit_events (actor_employee_id,event_key,target_type,target_id,outcome) VALUES (%s,'SERVICE_RECORD_CREATED','service_record',%s,'SUCCESS')", (actor_employee_id,str(service_id)))
        conn.commit(); return service_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()

def update_service_lifecycle(*, actor_employee_id: int, service_id: int, lifecycle_status: str) -> None:
    if lifecycle_status not in SERVICE_STATUSES: raise ServiceInventoryError("Invalid lifecycle status.")
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT owner_team_id,lifecycle_status FROM service_records WHERE service_id=%s", (service_id,))
        snapshot = cur.fetchone()
    finally:
        cur.close(); conn.close()
    if not snapshot: raise ServiceInventoryError("Service record not found.")
    team_id, old_status = snapshot
    context = ResourceContext(team_id=team_id, resource_type="service", resource_id=str(service_id))
    if not has_permission(actor_employee_id, "service.inventory.update", context): raise ServiceInventoryError("Not authorized to update this service.")
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT lifecycle_status,owner_team_id FROM service_records WHERE service_id=%s FOR UPDATE", (service_id,))
        row = cur.fetchone()
        if not row or row[0] != old_status or row[1] != team_id: raise ServiceInventoryError("Service record changed; reload and try again.")
        cur.execute("UPDATE service_records SET lifecycle_status=%s WHERE service_id=%s", (lifecycle_status,service_id))
        cur.execute("INSERT INTO audit_events (actor_employee_id,event_key,target_type,target_id,outcome) VALUES (%s,'SERVICE_LIFECYCLE_CHANGED','service_record',%s,'SUCCESS')", (actor_employee_id,str(service_id)))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()