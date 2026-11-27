"""One-time, operator-invoked first administrator bootstrap."""
from __future__ import annotations

from itoms.db.connection import get_connection
from itoms.security.password_policy import validate_password
from itoms.services.auth import hash_password

BOOTSTRAP_SETTING = "security.initial_admin_bootstrap_completed"
BOOTSTRAP_LOCK = "itoms_initial_admin_bootstrap"


class BootstrapError(ValueError):
    """The bootstrap cannot safely proceed."""


def bootstrap_first_administrator(*, employee_code: str, full_name: str,
                                   username: str, password: str,
                                   department_id: int, email: str | None = None) -> int:
    """Create the first department-scoped administrator in one transaction."""
    employee_code, full_name, username = (
        (employee_code or "").strip(), (full_name or "").strip(), (username or "").strip()
    )
    email = (email or "").strip() or None
    if not employee_code or not full_name or not username:
        raise BootstrapError("Employee code, full name and username are required.")
    if len(employee_code) > 80 or len(full_name) > 200 or len(username) > 120:
        raise BootstrapError("An identity field exceeds its database limit.")
    if email and len(email) > 254:
        raise BootstrapError("Email exceeds its database limit.")
    if not isinstance(department_id, int) or department_id <= 0:
        raise BootstrapError("A valid active department ID is required.")
    validate_password(password)
    password_hash = hash_password(password)

    conn = get_connection()
    cur = conn.cursor()
    locked = False
    try:
        cur.execute("SELECT GET_LOCK(%s,30)", (BOOTSTRAP_LOCK,))
        row = cur.fetchone()
        locked = bool(row and row[0] == 1)
        if not locked:
            raise BootstrapError("Could not acquire bootstrap lock; retry later.")
        cur.execute("SELECT setting_value FROM system_settings WHERE setting_key=%s FOR UPDATE",
                    (BOOTSTRAP_SETTING,))
        marker = cur.fetchone()
        if marker and marker[0] == "completed":
            raise BootstrapError("Initial administrator bootstrap has already been completed.")
        cur.execute("SELECT COUNT(*) FROM user_accounts")
        if cur.fetchone()[0]:
            raise BootstrapError("Accounts already exist; refusing first-admin bootstrap.")
        cur.execute("SELECT 1 FROM departments WHERE department_id=%s AND is_active=TRUE",
                    (department_id,))
        if not cur.fetchone():
            raise BootstrapError("The selected department does not exist or is inactive.")

        cur.execute("""INSERT INTO employees
            (employee_code,full_name,email,job_title,department_id)
            VALUES (%s,%s,%s,'ITOMS Initial Administrator',%s)""",
            (employee_code, full_name, email, department_id))
        employee_id = int(cur.lastrowid)
        cur.execute("""INSERT INTO user_accounts
            (employee_id,username,password_hash,account_status,must_change_password)
            VALUES (%s,%s,%s,'ACTIVE',TRUE)""",
            (employee_id, username, password_hash))
        cur.execute("""INSERT INTO application_roles
            (role_name,description,is_system_role,is_active)
            VALUES ('Initial System Administrator',
            'One-time bootstrap role; data access is bounded by department scope.',TRUE,TRUE)""")
        role_id = int(cur.lastrowid)
        cur.execute("SELECT permission_id FROM permissions ORDER BY permission_id")
        permission_ids = [int(item[0]) for item in cur.fetchall()]
        if not permission_ids:
            raise BootstrapError("Permission catalogue is empty; apply all migrations first.")
        cur.executemany("INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
                        [(role_id, permission_id) for permission_id in permission_ids])
        cur.execute("""INSERT INTO employee_role_assignments
            (employee_id,role_id,scope_type,scope_reference,assigned_by,is_active)
            VALUES (%s,%s,'DEPARTMENT',%s,NULL,TRUE)""",
            (employee_id, role_id, str(department_id)))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome,details)
            VALUES (NULL,'INITIAL_ADMIN_BOOTSTRAPPED','employee',%s,'SUCCESS',
            JSON_OBJECT('role_id',%s,'scope_type','DEPARTMENT',
            'department_id',%s,'permission_count',%s))""",
            (str(employee_id), role_id, department_id, len(permission_ids)))
        cur.execute("""INSERT INTO system_settings (setting_key,setting_value)
            VALUES (%s,'completed') ON DUPLICATE KEY UPDATE setting_value='completed'""",
            (BOOTSTRAP_SETTING,))
        conn.commit()
        return employee_id
    except Exception:
        conn.rollback()
        raise
    finally:
        if locked:
            try:
                cur.execute("SELECT RELEASE_LOCK(%s)", (BOOTSTRAP_LOCK,))
                cur.fetchone()
            except Exception:
                pass
        cur.close()
        conn.close()
