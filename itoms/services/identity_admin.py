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
        if not has_permission(actor_employee_id, "identity.accounts.create", context):
            raise IdentityAdministrationError("Not authorized to create accounts in this department or team.")
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
        cur.execute("SELECT department_id FROM employees WHERE employee_id=%s AND is_active=TRUE", (employee_id,))
        employee = cur.fetchone()
        if not employee:
            raise IdentityAdministrationError("Employee does not exist or is inactive.")
        employee_department_id = employee[0]
        team_id = None
        if scope_type == "TEAM":
            if not scope_reference or not scope_reference.isdigit() or int(scope_reference) <= 0:
                raise IdentityAdministrationError("TEAM scope requires a valid team ID reference.")
            team_id = int(scope_reference)
            cur.execute("""SELECT t.department_id FROM teams t
                JOIN employee_team_memberships m ON m.team_id=t.team_id AND m.employee_id=%s
                WHERE t.team_id=%s AND t.is_active=TRUE""", (employee_id, team_id))
            team = cur.fetchone()
            if not team:
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
        cur.execute("SELECT 1 FROM application_roles WHERE role_id=%s AND is_active=TRUE", (role_id,))
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


def grant_role_permission(*, actor_employee_id: int, role_id: int, permission_key: str) -> bool:
    """Grant a catalogue permission to an active role; return whether a new grant was created."""
    if not has_permission(actor_employee_id, "identity.roles.permissions.manage"):
        raise IdentityAdministrationError("Not authorized to manage role permissions.")
    key = (permission_key or "").strip()
    if not key or len(key) > 160:
        raise IdentityAdministrationError("A valid permission key is required.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role_name FROM application_roles WHERE role_id=%s AND is_active=TRUE FOR UPDATE", (role_id,))
        role = cur.fetchone()
        if not role:
            raise IdentityAdministrationError("Role does not exist or is inactive.")
        cur.execute("""SELECT 1 FROM employee_role_assignments
            WHERE employee_id=%s AND role_id=%s AND is_active=TRUE
              AND (expires_at IS NULL OR expires_at>UTC_TIMESTAMP()) LIMIT 1""",
            (actor_employee_id, role_id))
        if cur.fetchone():
            raise IdentityAdministrationError("You cannot modify permissions on a role assigned to your own account.")
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
    if not has_permission(actor_employee_id, "identity.roles.permissions.manage"):
        raise IdentityAdministrationError("Not authorized to manage role permissions.")
    key = (permission_key or "").strip()
    if not key or len(key) > 160:
        raise IdentityAdministrationError("A valid permission key is required.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role_name FROM application_roles WHERE role_id=%s AND is_active=TRUE FOR UPDATE", (role_id,))
        role = cur.fetchone()
        if not role:
            raise IdentityAdministrationError("Role does not exist or is inactive.")
        cur.execute("""SELECT 1 FROM employee_role_assignments
            WHERE employee_id=%s AND role_id=%s AND is_active=TRUE
              AND (expires_at IS NULL OR expires_at>UTC_TIMESTAMP()) LIMIT 1""",
            (actor_employee_id, role_id))
        if cur.fetchone():
            raise IdentityAdministrationError("You cannot modify permissions on a role assigned to your own account.")
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
        cur.execute("SELECT role_id,role_name FROM application_roles WHERE is_active=TRUE ORDER BY role_name")
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
