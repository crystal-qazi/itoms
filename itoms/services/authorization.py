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

def has_permissions_in_transaction(
    cur, employee_id: int, permission_key: str,
    resources: list[ResourceContext | None],
    *, lock_employee_ids: list[int] | None = None,
) -> bool:
    """Require one permission grant for every resource in a single transaction.

    Lock order: actor/target employee rows in ascending employee_id ->
    resource teams in ascending team_id -> membership/manager-mapping rows in
    ascending team_id -> sorted application roles -> actor role assignments ->
    exact role-permission rows. Callers lock protected resource rows only after
    this function and revalidate snapshots.
    """
    if (not isinstance(employee_id, int) or isinstance(employee_id, bool)
            or employee_id <= 0 or not permission_key or not resources):
        return False

    employee_ids = sorted({
        employee_id,
        *(int(value) for value in (lock_employee_ids or [])),
    })
    if any(value <= 0 for value in employee_ids):
        return False
    marks = ",".join(["%s"] * len(employee_ids))
    cur.execute(
        f"""SELECT employee_id,department_id,is_active FROM employees
            WHERE employee_id IN ({marks})
            ORDER BY employee_id FOR UPDATE""",
        tuple(employee_ids),
    )
    locked_employees = {
        int(row[0]): row for row in cur.fetchall()
    }
    actor = locked_employees.get(employee_id)
    if not actor or not actor[2] or len(locked_employees) != len(employee_ids):
        return False
    actor_department_id = actor[1]

    # Lock all team scopes in a single deterministic order. This matters for
    # mutations such as assignment that authorize both the existing request
    # scope and a separately selected destination team.
    team_ids = sorted({
        int(resource.team_id)
        for resource in resources
        if resource is not None and resource.team_id is not None
    })
    active_team_ids: set[int] = set()
    member_team_ids: set[int] = set()
    managed_team_ids: set[int] = set()
    for team_id in team_ids:
        cur.execute(
            "SELECT is_active FROM teams WHERE team_id=%s FOR UPDATE",
            (team_id,),
        )
        team = cur.fetchone()
        if team and team[0]:
            active_team_ids.add(team_id)
            cur.execute(
                """SELECT 1 FROM employee_team_memberships
                   WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
                (employee_id, team_id),
            )
            if cur.fetchone():
                member_team_ids.add(team_id)
            cur.execute(
                """SELECT 1 FROM team_management_assignments
                   WHERE manager_employee_id=%s AND team_id=%s FOR UPDATE""",
                (employee_id, team_id),
            )
            if cur.fetchone():
                managed_team_ids.add(team_id)

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
        return False

    cur.execute(
        "SELECT permission_id FROM permissions WHERE permission_key=%s",
        (permission_key,),
    )
    permission = cur.fetchone()
    if not permission:
        return False
    permission_id = int(permission[0])

    granted_role_ids: set[int] = set()
    for role_id in sorted(active_role_ids):
        cur.execute(
            """SELECT 1 FROM role_permissions
               WHERE role_id=%s AND permission_id=%s FOR UPDATE""",
            (role_id, permission_id),
        )
        if cur.fetchone():
            granted_role_ids.add(role_id)

    def resource_is_authorized(resource: ResourceContext | None) -> bool:
        if resource is None:
            return bool(granted_role_ids)
        for _assignment_id, raw_role_id, scope_type, scope_reference in assignments:
            role_id = int(raw_role_id)
            if role_id not in granted_role_ids:
                continue
            in_scope = False
            if scope_type == "OWN":
                in_scope = resource.owner_employee_id == employee_id
            elif scope_type == "TEAM":
                in_scope = (
                    resource.team_id in member_team_ids
                    and resource.team_id in active_team_ids
                    and (scope_reference is None
                         or str(scope_reference) == str(resource.team_id))
                )
            elif scope_type == "MANAGED_TEAMS":
                in_scope = (
                    resource.team_id in managed_team_ids
                    and resource.team_id in active_team_ids
                )
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
            if in_scope:
                return True
        return False

    return all(resource_is_authorized(resource) for resource in resources)


def has_permission_in_transaction(
    cur, employee_id: int, permission_key: str,
    resource: ResourceContext | None = None,
    *, lock_employee_ids: list[int] | None = None,
) -> bool:
    """Transaction-bound permission check for one trusted resource/action.

    Additional employee rows are locked in the same sorted employee-first
    phase when the protected mutation also changes a target employee (for
    example, assigning a task to another employee).
    """
    return has_permissions_in_transaction(
        cur, employee_id, permission_key, [resource],
        lock_employee_ids=lock_employee_ids,
    )
