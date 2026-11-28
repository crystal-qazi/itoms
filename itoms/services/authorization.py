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
                cur.execute("""SELECT 1 FROM team_management_assignments tm
                    JOIN teams t ON t.team_id=tm.team_id AND t.is_active=TRUE
                    WHERE tm.manager_employee_id=%s AND tm.team_id=%s LIMIT 1""",
                    (employee_id, resource.team_id))
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

def has_permission_in_transaction(
    cur, employee_id: int, permission_key: str,
    resource: ResourceContext | None = None,
) -> bool:
    """Evaluate permission using locks held by the caller's mutation transaction.

    Lock order for this evaluator is: actor employee -> resource team and
    membership/manager mapping (when applicable) -> sorted application roles
    -> actor role assignments -> exact role-permission rows. Runtime writers
    that change an actor's role assignments lock that employee first; directory
    membership/manager writers use employee -> team -> membership/mapping.
    The caller must lock its protected resource only after this function returns
    and revalidate the resource's scope snapshot before writing.
    """
    if (not isinstance(employee_id, int) or isinstance(employee_id, bool)
            or employee_id <= 0 or not permission_key):
        return False

    cur.execute(
        """SELECT department_id FROM employees
           WHERE employee_id=%s AND is_active=TRUE FOR UPDATE""",
        (employee_id,),
    )
    actor = cur.fetchone()
    if not actor:
        return False
    actor_department_id = actor[0]

    resource = resource or ResourceContext()
    team_member = False
    managed_team = False
    if resource.team_id is not None:
        cur.execute(
            """SELECT department_id FROM teams
               WHERE team_id=%s AND is_active=TRUE FOR UPDATE""",
            (resource.team_id,),
        )
        team = cur.fetchone()
        if team:
            cur.execute(
                """SELECT 1 FROM employee_team_memberships
                   WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
                (employee_id, resource.team_id),
            )
            team_member = cur.fetchone() is not None
            cur.execute(
                """SELECT 1 FROM team_management_assignments
                   WHERE manager_employee_id=%s AND team_id=%s FOR UPDATE""",
                (employee_id, resource.team_id),
            )
            managed_team = cur.fetchone() is not None

    # The employee row serializes all supported runtime role-assignment writers
    # for this actor. Discover role IDs, lock them deterministically, then lock
    # and revalidate the exact active assignments.
    cur.execute(
        """SELECT DISTINCT role_id FROM employee_role_assignments
           WHERE employee_id=%s AND is_active=TRUE
             AND (expires_at IS NULL OR expires_at>UTC_TIMESTAMP())""",
        (employee_id,),
    )
    candidate_role_ids = sorted({int(row[0]) for row in cur.fetchall()})
    active_role_ids: set[int] = set()
    for role_id in candidate_role_ids:
        cur.execute(
            "SELECT is_active FROM application_roles WHERE role_id=%s FOR UPDATE",
            (role_id,),
        )
        role = cur.fetchone()
        if role and role[0]:
            active_role_ids.add(role_id)

    cur.execute(
        """SELECT assignment_id,role_id,scope_type,scope_reference
           FROM employee_role_assignments
           WHERE employee_id=%s AND is_active=TRUE
             AND (expires_at IS NULL OR expires_at>UTC_TIMESTAMP())
           ORDER BY role_id,assignment_id FOR UPDATE""",
        (employee_id,),
    )
    assignments = cur.fetchall()
    locked_role_ids = {int(row[1]) for row in assignments}
    if locked_role_ids != set(candidate_role_ids):
        # A non-conforming writer or expiry boundary changed the authorization
        # set between discovery and locking. Fail closed; caller can retry.
        return False

    cur.execute(
        "SELECT permission_id FROM permissions WHERE permission_key=%s",
        (permission_key,),
    )
    permission = cur.fetchone()
    if not permission:
        return False
    permission_id = int(permission[0])

    for _assignment_id, raw_role_id, scope_type, scope_reference in assignments:
        role_id = int(raw_role_id)
        if role_id not in active_role_ids:
            continue
        in_scope = False
        if scope_type == "OWN":
            in_scope = resource.owner_employee_id == employee_id
        elif scope_type == "TEAM":
            in_scope = (
                resource.team_id is not None and team_member
                and (scope_reference is None
                     or str(scope_reference) == str(resource.team_id))
            )
        elif scope_type == "MANAGED_TEAMS":
            in_scope = resource.team_id is not None and managed_team
        elif scope_type == "DEPARTMENT":
            in_scope = (
                resource.department_id is not None
                and actor_department_id == resource.department_id
                and (scope_reference is None
                     or str(scope_reference) == str(resource.department_id))
            )
        elif scope_type == "RESOURCE":
            in_scope = (
                bool(resource.resource_type) and bool(resource.resource_id)
                and scope_reference == f"{resource.resource_type}:{resource.resource_id}"
            )
        if not in_scope:
            continue
        cur.execute(
            """SELECT 1 FROM role_permissions
               WHERE role_id=%s AND permission_id=%s FOR UPDATE""",
            (role_id, permission_id),
        )
        if cur.fetchone():
            return True
    return False

