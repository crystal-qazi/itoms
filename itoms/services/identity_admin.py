"""Privileged identity administration operations."""
from __future__ import annotations
from itoms.db.connection import get_connection
from itoms.security.password_policy import validate_password
from itoms.services.auth import hash_password
from itoms.services.authorization import has_permission

class IdentityAdministrationError(ValueError):
    """Identity administration request was invalid or not authorized."""

def create_employee_account(*, actor_employee_id: int, employee_code: str,
                            full_name: str, username: str, initial_password: str,
                            department_id: int | None = None, email: str | None = None,
                            job_title: str | None = None, primary_team_id: int | None = None) -> int:
    """Create an employee and active first-login account after a permission check."""
    if not has_permission(actor_employee_id, "identity.accounts.create"):
        raise IdentityAdministrationError("Not authorized to create accounts.")
    if not all((employee_code.strip(), full_name.strip(), username.strip())):
        raise IdentityAdministrationError("Employee code, name and username are required.")
    validate_password(initial_password)
    password_hash = hash_password(initial_password)
    conn = get_connection()
    cur = conn.cursor()
    try:
        if department_id is not None:
            cur.execute("SELECT 1 FROM departments WHERE department_id=%s AND is_active=TRUE", (department_id,))
            if not cur.fetchone():
                raise IdentityAdministrationError("Department does not exist or is inactive.")
        if primary_team_id is not None:
            cur.execute("SELECT department_id FROM teams WHERE team_id=%s AND is_active=TRUE", (primary_team_id,))
            team = cur.fetchone()
            if not team:
                raise IdentityAdministrationError("Primary team does not exist or is inactive.")
            if department_id is not None and team[0] != department_id:
                raise IdentityAdministrationError("Primary team must belong to the employee department.")
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
    if not has_permission(actor_employee_id, "identity.roles.assign"):
        raise IdentityAdministrationError("Not authorized to assign roles.")
    if scope_type not in {"OWN","TEAM","MANAGED_TEAMS","DEPARTMENT","RESOURCE"}:
        raise IdentityAdministrationError("Invalid authorization scope.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE", (employee_id,))
        if not cur.fetchone():
            raise IdentityAdministrationError("Employee does not exist or is inactive.")
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
