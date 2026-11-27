"""Server-side permission and data-scope evaluation."""
from __future__ import annotations
from dataclasses import dataclass
from itoms.db.connection import get_connection

@dataclass(frozen=True)
class ResourceContext:
    """Trusted resource attributes loaded by the owning service, never client claims."""
    owner_employee_id: int | None = None
    team_id: int | None = None
    department_id: int | None = None
    resource_type: str | None = None
    resource_id: str | None = None

def has_permission(employee_id: int, permission_key: str,
                   resource: ResourceContext | None = None) -> bool:
    """Return true only when an active assignment grants permission in this scope."""
    if employee_id <= 0 or not permission_key:
        return False
    has_resource_context = resource is not None
    resource = resource or ResourceContext()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT DISTINCT a.scope_type, a.scope_reference
            FROM employee_role_assignments a
            JOIN application_roles r ON r.role_id=a.role_id AND r.is_active=TRUE
            JOIN role_permissions rp ON rp.role_id=r.role_id
            JOIN permissions p ON p.permission_id=rp.permission_id
            WHERE a.employee_id=%s AND a.is_active=TRUE
              AND (a.expires_at IS NULL OR a.expires_at>UTC_TIMESTAMP())
              AND p.permission_key=%s""", (employee_id, permission_key))
        assignments = cur.fetchall()
        if not assignments:
            return False
        # A check without a resource context authorizes the action itself.
        # Resource reads and mutations must pass trusted resource attributes
        # and continue through the scope-specific checks below.
        if not has_resource_context:
            return True
        for scope_type, scope_reference in assignments:
            if scope_type == "OWN" and resource.owner_employee_id == employee_id:
                return True
            if scope_type == "TEAM" and resource.team_id is not None:
                cur.execute("""SELECT 1 FROM employee_team_memberships m
                    JOIN teams t ON t.team_id=m.team_id AND t.is_active=TRUE
                    WHERE m.employee_id=%s AND m.team_id=%s
                    AND (%s IS NULL OR %s=CAST(m.team_id AS CHAR)) LIMIT 1""",
                    (employee_id, resource.team_id, scope_reference, scope_reference))
                if cur.fetchone():
                    return True
            if scope_type == "MANAGED_TEAMS" and resource.team_id is not None:
                cur.execute("""SELECT 1 FROM team_management_assignments
                    WHERE manager_employee_id=%s AND team_id=%s LIMIT 1""", (employee_id, resource.team_id))
                if cur.fetchone():
                    return True
            if scope_type == "DEPARTMENT" and resource.department_id is not None:
                cur.execute("""SELECT department_id FROM employees WHERE employee_id=%s
                    AND is_active=TRUE AND department_id=%s""", (employee_id, resource.department_id))
                row = cur.fetchone()
                if row and (scope_reference is None or scope_reference == str(resource.department_id)):
                    return True
            if scope_type == "RESOURCE" and resource.resource_type and resource.resource_id:
                if scope_reference == f"{resource.resource_type}:{resource.resource_id}":
                    return True
        return False
    finally:
        cur.close()
        conn.close()
