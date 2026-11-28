"""Privileged identity administration operations."""
from __future__ import annotations
from itoms.db.connection import get_connection
from itoms.security.password_policy import validate_password
from itoms.services.auth import hash_password
from itoms.services.authorization import ResourceContext, has_permission

class IdentityAdministrationError(ValueError):
    """Identity administration request was invalid or not authorized."""

def create_employee_account(*, actor_employee_id: int, employee_code: str,
                            full_name: str, username: str, initial_password: str,
                            department_id: int | None = None, email: str | None = None,
                            job_title: str | None = None, primary_team_id: int | None = None) -> int:
    """Create an employee and active first-login account after a permission check."""
    if not all((employee_code.strip(), full_name.strip(), username.strip())):
        raise IdentityAdministrationError("Employee code, name and username are required.")
    validate_password(initial_password)
    password_hash = hash_password(initial_password)
    conn = get_connection()
    cur = conn.cursor()
    try:
        team_department_id = None
        if primary_team_id is not None:
            cur.execute("SELECT department_id FROM teams WHERE team_id=%s AND is_active=TRUE", (primary_team_id,))
            team = cur.fetchone()
            if not team:
                raise IdentityAdministrationError("Primary team does not exist or is inactive.")
            team_department_id = team[0]
            if department_id is not None and team_department_id != department_id:
                raise IdentityAdministrationError("Primary team must belong to the employee department.")
            if department_id is None:
                department_id = team_department_id
        if department_id is None:
            raise IdentityAdministrationError("A department or department-owned primary team is required.")
        cur.execute("SELECT 1 FROM departments WHERE department_id=%s AND is_active=TRUE", (department_id,))
        if not cur.fetchone():
            raise IdentityAdministrationError("Department does not exist or is inactive.")
        context = ResourceContext(department_id=department_id, team_id=primary_team_id)
        if not has_permissions_in_transaction(
            cur, actor_employee_id, "identity.accounts.create", [context]
        ):
            raise IdentityAdministrationError("Not authorized to create accounts in this department or team.")
        # Revalidate department/team state after authorization locks. The helper
        # has already locked the actor and any supplied primary-team row.
        cur.execute(
            "SELECT 1 FROM departments WHERE department_id=%s AND is_active=TRUE FOR UPDATE",
            (department_id,),
        )
        if not cur.fetchone():
            raise IdentityAdministrationError("Department does not exist or is inactive.")
        if primary_team_id is not None:
            cur.execute(
                "SELECT department_id,is_active FROM teams WHERE team_id=%s FOR UPDATE",
                (primary_team_id,),
            )
            locked_team = cur.fetchone()
            if (not locked_team or not locked_team[1]
                    or locked_team[0] != department_id):
                raise IdentityAdministrationError("Primary team changed; retry account creation.")
        cur.execute("""INSERT INTO employees
            (employee_code,full_name,email,job_title,department_id)
            VALUES (%s,%s,%s,%s,%s)""",
            (employee_code.strip(),full_name.strip(),email,job_title,department_id))
        employee_id = cur.lastrowid
        cur.execute("""INSERT INTO user_accounts
            (employee_id,username,password_hash,account_status,must_change_password)
            VALUES (%s,%s,%s,'ACTIVE',TRUE)""", (employee_id,username.strip(),password_hash))
        if primary_team_id is not None:
            cur.execute("""INSERT INTO employee_team_memberships
                (employee_id,team_id,is_primary) VALUES (%s,%s,TRUE)""", (employee_id,primary_team_id))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome,details)
            VALUES (%s,'IDENTITY_ACCOUNT_CREATED','employee',%s,'SUCCESS',JSON_OBJECT('username',%s))""",
            (actor_employee_id,str(employee_id),username.strip()))
        conn.commit()
        return int(employee_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def assign_role(*, actor_employee_id: int, employee_id: int, role_id: int,
                scope_type: str, scope_reference: str | None = None,
                expires_at=None) -> int:
    """Assign a role only when the actor has the dedicated administration permission."""
    if employee_id == actor_employee_id:
        raise IdentityAdministrationError("Self-assignment of roles is not permitted.")
    if scope_type not in {"OWN","TEAM","MANAGED_TEAMS","DEPARTMENT","RESOURCE"}:
        raise IdentityAdministrationError("Invalid authorization scope.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Serialize scope validation with directory membership writers. The shared
        # parent-first order is employee -> team -> membership -> role.
        cur.execute(
            "SELECT department_id FROM employees WHERE employee_id=%s AND is_active=TRUE FOR UPDATE",
            (employee_id,),
        )
        employee = cur.fetchone()
        if not employee:
            raise IdentityAdministrationError("Employee does not exist or is inactive.")
        employee_department_id = employee[0]
        team_id = None
        if scope_type == "TEAM":
            if not scope_reference or not scope_reference.isdigit() or int(scope_reference) <= 0:
                raise IdentityAdministrationError("TEAM scope requires a valid team ID reference.")
            team_id = int(scope_reference)
            cur.execute(
                "SELECT department_id FROM teams WHERE team_id=%s AND is_active=TRUE FOR UPDATE",
                (team_id,),
            )
            team = cur.fetchone()
            if not team:
                raise IdentityAdministrationError("The team does not exist or is inactive.")
            cur.execute(
                """SELECT 1 FROM employee_team_memberships
                   WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
                (employee_id, team_id),
            )
            if not cur.fetchone():
                raise IdentityAdministrationError("The employee must belong to the active team in the assignment scope.")
            if employee_department_id is not None and team[0] != employee_department_id:
                raise IdentityAdministrationError("The team must belong to the employee department.")
            employee_department_id = team[0]
        elif scope_type == "DEPARTMENT":
            if employee_department_id is None:
                raise IdentityAdministrationError("Department scope requires an employee department.")
            expected = str(employee_department_id)
            if scope_reference not in (None, "", expected):
                raise IdentityAdministrationError("Department scope must match the employee department.")
            scope_reference = expected
        elif scope_type == "OWN":
            if scope_reference not in (None, ""):
                raise IdentityAdministrationError("OWN scope cannot have a scope reference.")
            scope_reference = None
        elif scope_type == "MANAGED_TEAMS":
            if scope_reference not in (None, ""):
                raise IdentityAdministrationError("MANAGED_TEAMS scope does not accept a reference.")
            scope_reference = None
            cur.execute("""SELECT t.team_id,t.department_id
                FROM team_management_assignments m JOIN teams t ON t.team_id=m.team_id
                WHERE m.manager_employee_id=%s AND t.is_active=TRUE""", (employee_id,))
            managed = cur.fetchall()
            if not managed:
                raise IdentityAdministrationError("The employee has no active managed teams.")
            for managed_team_id, managed_department_id in managed:
                if not has_permission(actor_employee_id, "identity.roles.assign",
                    ResourceContext(team_id=managed_team_id, department_id=managed_department_id)):
                    raise IdentityAdministrationError("Not authorized to assign roles for every managed team.")
        elif scope_type == "RESOURCE":
            if not scope_reference or ":" not in scope_reference or len(scope_reference) > 255:
                raise IdentityAdministrationError("RESOURCE scope requires a resource_type:resource_id reference.")
        context = ResourceContext(
            owner_employee_id=employee_id if scope_type in {"OWN", "RESOURCE"} else None,
            team_id=team_id,
            department_id=employee_department_id,
            resource_type=scope_reference.split(":", 1)[0] if scope_type == "RESOURCE" else None,
            resource_id=scope_reference.split(":", 1)[1] if scope_type == "RESOURCE" else None,
        )
        if scope_type != "MANAGED_TEAMS" and not has_permission(
            actor_employee_id, "identity.roles.assign", context
        ):
            raise IdentityAdministrationError("Not authorized to assign roles within this employee scope.")
        cur.execute("SELECT 1 FROM application_roles WHERE role_id=%s AND is_active=TRUE FOR UPDATE", (role_id,))
        if not cur.fetchone():
            raise IdentityAdministrationError("Role does not exist or is inactive.")
        cur.execute("""INSERT INTO employee_role_assignments
            (employee_id,role_id,scope_type,scope_reference,assigned_by,expires_at)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (employee_id,role_id,scope_type,scope_reference,actor_employee_id,expires_at))
        assignment_id = cur.lastrowid
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome,details)
            VALUES (%s,'IDENTITY_ROLE_ASSIGNED','employee_role_assignment',%s,'SUCCESS',
            JSON_OBJECT('employee_id',%s,'role_id',%s,'scope_type',%s))""",
            (actor_employee_id,str(assignment_id),employee_id,role_id,scope_type))
        conn.commit()
        return int(assignment_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()



def revoke_role_assignment(*, actor_employee_id: int, assignment_id: int) -> bool:
    """Deactivate one scoped role assignment and audit the revocation."""
    if (not isinstance(actor_employee_id, int) or isinstance(actor_employee_id, bool)
            or actor_employee_id <= 0 or not isinstance(assignment_id, int)
            or isinstance(assignment_id, bool) or assignment_id <= 0):
        raise IdentityAdministrationError("Actor and assignment IDs must be positive integers.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT employee_id,role_id,scope_type,scope_reference,is_active
               FROM employee_role_assignments WHERE assignment_id=%s""",
            (assignment_id,),
        )
        assignment = cur.fetchone()
        if not assignment:
            conn.commit()
            return False
        target_employee_id, role_id, scope_type, scope_reference, is_active = assignment
        if int(target_employee_id) == actor_employee_id:
            raise IdentityAdministrationError("Self-revocation of roles is not permitted.")
        cur.execute(
            "SELECT department_id FROM employees WHERE employee_id=%s",
            (target_employee_id,),
        )
        target = cur.fetchone()
        if not target:
            raise IdentityAdministrationError("Assigned employee no longer exists.")
        target_department_id = target[0]

        managed_team_ids = []
        if scope_type == "TEAM":
            if not scope_reference or not str(scope_reference).isdigit():
                raise IdentityAdministrationError("Stored TEAM scope reference is invalid.")
            team_id = int(scope_reference)
            cur.execute(
                "SELECT department_id FROM teams WHERE team_id=%s AND is_active=TRUE",
                (team_id,),
            )
            team = cur.fetchone()
            if not team:
                raise IdentityAdministrationError("The assigned team is no longer active.")
            context = ResourceContext(team_id=team_id, department_id=team[0])
        elif scope_type == "MANAGED_TEAMS":
            cur.execute(
                """SELECT t.team_id,t.department_id FROM team_management_assignments m
                   JOIN teams t ON t.team_id=m.team_id
                   WHERE m.manager_employee_id=%s AND t.is_active=TRUE
                   ORDER BY t.team_id""",
                (target_employee_id,),
            )
            managed_team_rows = cur.fetchall()
            managed_team_ids = [(int(row[0]), row[1]) for row in managed_team_rows]
            context = None
        elif scope_type == "DEPARTMENT":
            if not scope_reference or not str(scope_reference).isdigit():
                raise IdentityAdministrationError("Stored DEPARTMENT scope reference is invalid.")
            context = ResourceContext(department_id=int(scope_reference))
        elif scope_type == "OWN":
            context = ResourceContext(
                owner_employee_id=int(target_employee_id),
                department_id=target_department_id,
            )
        elif scope_type == "RESOURCE":
            if not scope_reference or ":" not in scope_reference:
                raise IdentityAdministrationError("Stored RESOURCE scope reference is invalid.")
            resource_type, resource_id = scope_reference.split(":", 1)
            context = ResourceContext(
                owner_employee_id=int(target_employee_id),
                department_id=target_department_id,
                resource_type=resource_type,
                resource_id=resource_id,
            )
        else:
            raise IdentityAdministrationError("Stored authorization scope is invalid.")

        if scope_type == "MANAGED_TEAMS":
            if managed_team_ids:
                authorized = all(
                    has_permission(
                        actor_employee_id, "identity.roles.assign",
                        ResourceContext(team_id=team_id, department_id=department_id),
                    )
                    for team_id, department_id in managed_team_ids
                )
            else:
                authorized = target_department_id is not None and has_permission(
                    actor_employee_id, "identity.roles.assign",
                    ResourceContext(department_id=target_department_id),
                )
        else:
            authorized = has_permission(
                actor_employee_id, "identity.roles.assign", context
            )
        if not authorized:
            raise IdentityAdministrationError("Not authorized to revoke this role assignment.")

        # Keep the same parent-first ordering as assign_role and directory writers.
        cur.execute(
            "SELECT department_id FROM employees WHERE employee_id=%s FOR UPDATE",
            (target_employee_id,),
        )
        locked_employee = cur.fetchone()
        if not locked_employee:
            raise IdentityAdministrationError("Assigned employee no longer exists.")
        if locked_employee[0] != target_department_id:
            raise IdentityAdministrationError("Employee department changed; retry the revocation.")
        if scope_type == "DEPARTMENT" and str(locked_employee[0]) != str(scope_reference):
            raise IdentityAdministrationError("Department scope changed; retry the revocation.")
        if scope_type == "TEAM":
            cur.execute(
                "SELECT team_id,department_id,is_active FROM teams WHERE team_id=%s FOR UPDATE",
                (team_id,),
            )
            locked_team = cur.fetchone()
            if not locked_team or not locked_team[2] or locked_team[1] != team[0]:
                raise IdentityAdministrationError("The assigned team changed; retry the revocation.")
            cur.execute(
                """SELECT 1 FROM employee_team_memberships
                   WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
                (target_employee_id, team_id),
            )
            if not cur.fetchone():
                raise IdentityAdministrationError("The employee's team membership no longer exists.")
        elif scope_type == "MANAGED_TEAMS":
            for managed_team_id, _department_id in managed_team_ids:
                cur.execute(
                    """SELECT team_id,department_id,is_active FROM teams
                       WHERE team_id=%s FOR UPDATE""",
                    (managed_team_id,),
                )
                locked_team = cur.fetchone()
                if (not locked_team or not locked_team[2]
                        or locked_team[1] != _department_id):
                    raise IdentityAdministrationError("Managed-team scope changed; retry the revocation.")
                cur.execute(
                    """SELECT 1 FROM employee_team_memberships
                       WHERE employee_id=%s AND team_id=%s FOR UPDATE""",
                    (target_employee_id, managed_team_id),
                )
                if not cur.fetchone():
                    raise IdentityAdministrationError("Manager team membership changed; retry the revocation.")
                cur.execute(
                    """SELECT 1 FROM team_management_assignments
                       WHERE manager_employee_id=%s AND team_id=%s FOR UPDATE""",
                    (target_employee_id, managed_team_id),
                )
                if not cur.fetchone():
                    raise IdentityAdministrationError("Managed-team scope changed; retry the revocation.")
        cur.execute(
            "SELECT role_id FROM application_roles WHERE role_id=%s FOR UPDATE",
            (role_id,),
        )
        if not cur.fetchone():
            raise IdentityAdministrationError("Assigned role no longer exists.")
        cur.execute(
            "SELECT is_active FROM employee_role_assignments WHERE assignment_id=%s FOR UPDATE",
            (assignment_id,),
        )
        current = cur.fetchone()
        if not current or not current[0]:
            conn.commit()
            return False
        cur.execute(
            "UPDATE employee_role_assignments SET is_active=FALSE WHERE assignment_id=%s",
            (assignment_id,),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'IDENTITY_ROLE_REVOKED','employee_role_assignment',%s,'SUCCESS',
                       JSON_OBJECT('employee_id',%s,'role_id',%s,'scope_type',%s))""",
            (actor_employee_id, str(assignment_id), target_employee_id, role_id, scope_type),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def _assert_role_permission_scope(
    cur, *, actor_employee_id: int, role_id: int,
    actor_department_id: int | None = None, actor_department_checked: bool = False
) -> None:
    """Allow editing only roles assigned exclusively to active employees in actor's department."""
    department_id = actor_department_id
    if not actor_department_checked and department_id is None:
        cur.execute("SELECT department_id FROM employees WHERE employee_id=%s AND is_active=TRUE",
                    (actor_employee_id,))
        actor = cur.fetchone()
        department_id = actor[0] if actor else None
    if department_id is None:
        raise IdentityAdministrationError("A department-scoped administrator is required.")
    cur.execute("""SELECT
        COUNT(*) AS assignment_count,
        SUM(CASE WHEN e.department_id=%s THEN 0 ELSE 1 END) AS outside_department_count
        FROM employee_role_assignments a
        JOIN employees e ON e.employee_id=a.employee_id AND e.is_active=TRUE
        WHERE a.role_id=%s AND a.is_active=TRUE
          AND (a.expires_at IS NULL OR a.expires_at>UTC_TIMESTAMP())""",
        (department_id, role_id))
    counts = cur.fetchone()
    if not counts or not counts[0]:
        raise IdentityAdministrationError(
            "Unassigned roles are reserved for higher-trust administration."
        )
    if counts[1]:
        raise IdentityAdministrationError(
            "Role permissions can be managed only when all active assignments belong to your department."
        )


def _lock_actor_permission_for_role_change(
    cur, *, actor_employee_id: int, permission_key: str, target_role_id: int
) -> tuple[bool, int | None, set[int], dict[int, str]]:
    """Lock current actor authorization and target role in one transaction.

    Lock order: actor employee -> role rows (ascending ID) -> actor assignment
    rows -> exact role-permission rows. All runtime role-assignment writers must
    lock the affected employee before the role row; role-permission writers
    must use this same helper/order.
    """
    cur.execute(
        "SELECT department_id FROM employees WHERE employee_id=%s AND is_active=TRUE FOR UPDATE",
        (actor_employee_id,),
    )
    actor = cur.fetchone()
    if not actor:
        raise IdentityAdministrationError("An active employee account is required.")

    # The employee row serializes role-assignment writers for this actor.
    cur.execute(
        """SELECT role_id FROM employee_role_assignments
           WHERE employee_id=%s AND is_active=TRUE
             AND (expires_at IS NULL OR expires_at>UTC_TIMESTAMP())
           ORDER BY role_id""",
        (actor_employee_id,),
    )
    candidate_role_ids = {int(row[0]) for row in cur.fetchall()}
    role_ids = sorted(candidate_role_ids | {int(target_role_id)})
    role_names: dict[int, str] = {}
    active_role_ids: set[int] = set()
    for current_role_id in role_ids:
        cur.execute(
            "SELECT role_name,is_active FROM application_roles WHERE role_id=%s FOR UPDATE",
            (current_role_id,),
        )
        role = cur.fetchone()
        if role and role[1]:
            active_role_ids.add(current_role_id)
            role_names[current_role_id] = role[0]

    # Lock and revalidate the actor's assignments after role locks are held.
    cur.execute(
        """SELECT assignment_id,role_id FROM employee_role_assignments
           WHERE employee_id=%s AND is_active=TRUE
             AND (expires_at IS NULL OR expires_at>UTC_TIMESTAMP())
           ORDER BY role_id,assignment_id FOR UPDATE""",
        (actor_employee_id,),
    )
    locked_assignments = cur.fetchall()
    actor_role_ids = {int(row[1]) for row in locked_assignments}
    if actor_role_ids != candidate_role_ids:
        # Fail closed if an unexpected writer did not honor the employee lock.
        raise IdentityAdministrationError("Authorization assignments changed; retry the operation.")

    cur.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (permission_key,))
    permission = cur.fetchone()
    if not permission:
        return False, int(actor[0]) if actor[0] is not None else None, actor_role_ids, role_names

    permission_id = int(permission[0])
    authorized = False
    for current_role_id in sorted(actor_role_ids & active_role_ids):
        cur.execute(
            """SELECT permission_id FROM role_permissions
               WHERE role_id=%s AND permission_id=%s FOR UPDATE""",
            (current_role_id, permission_id),
        )
        if cur.fetchone():
            authorized = True

    return authorized, int(actor[0]) if actor[0] is not None else None, actor_role_ids, role_names


def grant_role_permission(*, actor_employee_id: int, role_id: int, permission_key: str) -> bool:
    """Grant a catalogue permission to an active role; return whether a new grant was created."""
    key = (permission_key or "").strip()
    if not key or len(key) > 160:
        raise IdentityAdministrationError("A valid permission key is required.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        authorized, actor_department_id, actor_role_ids, role_names = (
            _lock_actor_permission_for_role_change(
                cur, actor_employee_id=actor_employee_id,
                permission_key="identity.roles.permissions.manage", target_role_id=role_id,
            )
        )
        if not authorized:
            raise IdentityAdministrationError("Not authorized to manage role permissions.")
        if role_id not in role_names:
            raise IdentityAdministrationError("Role does not exist or is inactive.")
        if role_id in actor_role_ids:
            raise IdentityAdministrationError("You cannot modify permissions on a role assigned to your own account.")
        _assert_role_permission_scope(
            cur, actor_employee_id=actor_employee_id, role_id=role_id,
            actor_department_id=actor_department_id, actor_department_checked=True,
        )
        cur.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (key,))
        permission = cur.fetchone()
        if not permission:
            raise IdentityAdministrationError("Permission key is not registered.")
        cur.execute("INSERT IGNORE INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
                    (role_id, permission[0]))
        created = cur.rowcount > 0
        if created:
            cur.execute("""INSERT INTO audit_events
                (actor_employee_id,event_key,target_type,target_id,outcome,details)
                VALUES (%s,'IDENTITY_ROLE_PERMISSION_GRANTED','application_role',%s,'SUCCESS',
                    JSON_OBJECT('permission_key',%s))""",
                (actor_employee_id, str(role_id), key))
        conn.commit()
        return created
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def revoke_role_permission(*, actor_employee_id: int, role_id: int, permission_key: str) -> bool:
    """Revoke a catalogue permission from an active role; return whether a grant existed."""
    key = (permission_key or "").strip()
    if not key or len(key) > 160:
        raise IdentityAdministrationError("A valid permission key is required.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        authorized, actor_department_id, actor_role_ids, role_names = (
            _lock_actor_permission_for_role_change(
                cur, actor_employee_id=actor_employee_id,
                permission_key="identity.roles.permissions.manage", target_role_id=role_id,
            )
        )
        if not authorized:
            raise IdentityAdministrationError("Not authorized to manage role permissions.")
        if role_id not in role_names:
            raise IdentityAdministrationError("Role does not exist or is inactive.")
        if role_id in actor_role_ids:
            raise IdentityAdministrationError("You cannot modify permissions on a role assigned to your own account.")
        _assert_role_permission_scope(
            cur, actor_employee_id=actor_employee_id, role_id=role_id,
            actor_department_id=actor_department_id,
        )
        cur.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (key,))
        permission = cur.fetchone()
        if not permission:
            raise IdentityAdministrationError("Permission key is not registered.")
        cur.execute("DELETE FROM role_permissions WHERE role_id=%s AND permission_id=%s",
                    (role_id, permission[0]))
        removed = cur.rowcount > 0
        if removed:
            cur.execute("""INSERT INTO audit_events
                (actor_employee_id,event_key,target_type,target_id,outcome,details)
                VALUES (%s,'IDENTITY_ROLE_PERMISSION_REVOKED','application_role',%s,'SUCCESS',
                    JSON_OBJECT('permission_key',%s))""",
                (actor_employee_id, str(role_id), key))
        conn.commit()
        return removed
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def list_role_permission_options(*, actor_employee_id: int, role_id: int | None = None) -> dict:
    """Return active roles and permission catalogue for the selected role."""
    if not has_permission(actor_employee_id, "identity.roles.permissions.manage"):
        raise IdentityAdministrationError("Not authorized to manage role permissions.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT r.role_id,r.role_name
            FROM application_roles r
            WHERE r.is_active=TRUE
              AND EXISTS (
                SELECT 1 FROM employee_role_assignments a
                JOIN employees e ON e.employee_id=a.employee_id AND e.is_active=TRUE
                WHERE a.role_id=r.role_id AND a.is_active=TRUE
                  AND (a.expires_at IS NULL OR a.expires_at>UTC_TIMESTAMP())
                  AND e.department_id=(
                    SELECT actor.department_id FROM employees actor
                    WHERE actor.employee_id=%s AND actor.is_active=TRUE
                  )
              )
              AND NOT EXISTS (
                SELECT 1 FROM employee_role_assignments a
                JOIN employees e ON e.employee_id=a.employee_id AND e.is_active=TRUE
                WHERE a.role_id=r.role_id AND a.is_active=TRUE
                  AND (a.expires_at IS NULL OR a.expires_at>UTC_TIMESTAMP())
                  AND (e.department_id IS NULL OR e.department_id<>(
                    SELECT actor.department_id FROM employees actor
                    WHERE actor.employee_id=%s AND actor.is_active=TRUE
                  ))
              )
              AND NOT EXISTS (
                SELECT 1 FROM employee_role_assignments own
                WHERE own.role_id=r.role_id AND own.employee_id=%s
                  AND own.is_active=TRUE
                  AND (own.expires_at IS NULL OR own.expires_at>UTC_TIMESTAMP())
              )
            ORDER BY r.role_name""", (actor_employee_id, actor_employee_id, actor_employee_id))
        roles = cur.fetchall()
        if not roles:
            return {"roles": [], "permissions": [], "selected_role_id": None}
        available = {int(role["role_id"]) for role in roles}
        selected = int(role_id) if role_id is not None else int(roles[0]["role_id"])
        if selected not in available:
            raise IdentityAdministrationError("Select an active application role.")
        cur.execute("""SELECT p.permission_key,p.description,
            (rp.permission_id IS NOT NULL) AS is_granted
            FROM permissions p
            LEFT JOIN role_permissions rp
              ON rp.permission_id=p.permission_id AND rp.role_id=%s
            ORDER BY p.permission_key""", (selected,))
        return {"roles": roles, "permissions": cur.fetchall(), "selected_role_id": selected}
    finally:
        cur.close()
        conn.close()
