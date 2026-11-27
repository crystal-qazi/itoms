"""MySQL concurrency tests for transactional role-permission authorization."""
from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def role_permission_fixture():
    from itoms import create_app
    from itoms.config import Config
    from itoms.db.connection import get_connection

    class MySQLTestConfig(Config):
        TESTING = True
        SECRET_KEY = "mysql-integration-only"
        DB_HOST = os.environ["ITOMS_DB_HOST"]
        DB_PORT = int(os.environ.get("ITOMS_DB_PORT", "3306"))
        DB_NAME = os.environ["ITOMS_DB_NAME"]
        DB_USER = os.environ["ITOMS_DB_USER"]
        DB_PASSWORD = os.environ["ITOMS_DB_PASSWORD"]

    app = create_app(MySQLTestConfig)
    app_context = app.app_context()
    app_context.push()
    suffix = uuid.uuid4().hex[:12]
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO departments (department_name) VALUES (%s)",
            (f"Role Permission Concurrency {suffix}",),
        )
        department_id = int(cursor.lastrowid)
        employee_ids = []
        for label in ("operator", "revoker", "target"):
            cursor.execute(
                """INSERT INTO employees
                   (employee_code,full_name,department_id,is_active)
                   VALUES (%s,%s,%s,TRUE)""",
                (f"RPC-{suffix}-{label}", f"Role permission {label}", department_id),
            )
            employee_ids.append(int(cursor.lastrowid))
        operator_id, revoker_id, target_employee_id = employee_ids

        role_ids = []
        for label in ("operator", "revoker", "target"):
            cursor.execute(
                "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
                (f"RP {label} {suffix}", "Temporary MySQL concurrency test role"),
            )
            role_ids.append(int(cursor.lastrowid))
        operator_role_id, revoker_role_id, target_role_id = role_ids

        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("identity.roles.permissions.manage",),
        )
        manage_permission = cursor.fetchone()
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("approvals.create",),
        )
        target_permission = cursor.fetchone()
        assert manage_permission and target_permission, "permission catalogue migrations must be applied"

        for role_id in (operator_role_id, revoker_role_id):
            cursor.execute(
                "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
                (role_id, manage_permission[0]),
            )
        for employee_id, role_id in (
            (operator_id, operator_role_id),
            (revoker_id, revoker_role_id),
            (target_employee_id, target_role_id),
        ):
            cursor.execute(
                """INSERT INTO employee_role_assignments
                   (employee_id,role_id,scope_type,is_active)
                   VALUES (%s,%s,'OWN',TRUE)""",
                (employee_id, role_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {
        "app": app,
        "suffix": suffix,
        "department_id": department_id,
        "operator_id": operator_id,
        "revoker_id": revoker_id,
        "target_employee_id": target_employee_id,
        "operator_role_id": operator_role_id,
        "revoker_role_id": revoker_role_id,
        "target_role_id": target_role_id,
        "manage_permission_id": int(manage_permission[0]),
        "target_permission_id": int(target_permission[0]),
    }
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        actor_ids = (operator_id, revoker_id, target_employee_id)
        marks = ",".join(["%s"] * len(actor_ids))
        cursor.execute(
            f"DELETE FROM audit_events WHERE actor_employee_id IN ({marks})",
            actor_ids,
        )
        cursor.execute(
            f"DELETE FROM employee_role_assignments WHERE employee_id IN ({marks})",
            actor_ids,
        )
        cursor.execute(
            "DELETE FROM role_permissions WHERE role_id IN (%s,%s,%s)",
            (operator_role_id, revoker_role_id, target_role_id),
        )
        cursor.execute(
            "DELETE FROM application_roles WHERE role_id IN (%s,%s,%s)",
            (operator_role_id, revoker_role_id, target_role_id),
        )
        cursor.execute(
            f"DELETE FROM employees WHERE employee_id IN ({marks})",
            actor_ids,
        )
        cursor.execute("DELETE FROM departments WHERE department_id=%s", (department_id,))
        cleanup.commit()
    except Exception:
        cleanup.rollback()
        raise
    finally:
        cursor.close()
        cleanup.close()
        app_context.pop()


def _db():
    from itoms.db.connection import get_connection
    return get_connection()


def test_permission_revocation_wins_before_authorization_lock(role_permission_fixture):
    from itoms.services.identity_admin import (
        IdentityAdministrationError, grant_role_permission, revoke_role_permission,
    )

    data = role_permission_fixture
    revoke_role_permission(
        actor_employee_id=data["revoker_id"],
        role_id=data["operator_role_id"],
        permission_key="identity.roles.permissions.manage",
    )

    with pytest.raises(IdentityAdministrationError, match="Not authorized"):
        grant_role_permission(
            actor_employee_id=data["operator_id"],
            role_id=data["target_role_id"],
            permission_key="approvals.create",
        )

    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM role_permissions WHERE role_id=%s AND permission_id=%s",
            (data["target_role_id"], data["target_permission_id"]),
        )
        assert cursor.fetchone()[0] == 0
    finally:
        cursor.close()
        connection.close()


def test_authorized_mutation_serializes_before_permission_revocation(
    role_permission_fixture, monkeypatch
):
    from itoms.services import identity_admin
    from itoms.services.identity_admin import grant_role_permission, revoke_role_permission

    data = role_permission_fixture
    original_assert = identity_admin._assert_role_permission_scope
    grant_has_locks = threading.Event()
    allow_grant_to_finish = threading.Event()
    revoke_started = threading.Event()
    revoke_has_target_role_lock = threading.Event()

    def coordinated_assert(cur, *, actor_employee_id, role_id, **kwargs):
        result = original_assert(
            cur, actor_employee_id=actor_employee_id, role_id=role_id, **kwargs
        )
        if actor_employee_id == data["operator_id"] and role_id == data["target_role_id"]:
            # The grant helper has already locked the operator, both applicable
            # role rows, its assignment, and the management permission row.
            grant_has_locks.set()
            if not allow_grant_to_finish.wait(timeout=15):
                raise TimeoutError("test did not release the authorized grant")
        elif actor_employee_id == data["revoker_id"] and role_id == data["operator_role_id"]:
            # Reaching this point proves the revoker acquired the role lock.
            revoke_has_target_role_lock.set()
        return result

    monkeypatch.setattr(identity_admin, "_assert_role_permission_scope", coordinated_assert)

    def grant():
        with data["app"].app_context():
            return grant_role_permission(
                actor_employee_id=data["operator_id"],
                role_id=data["target_role_id"],
                permission_key="approvals.create",
            )

    def revoke():
        with data["app"].app_context():
            revoke_started.set()
            return revoke_role_permission(
                actor_employee_id=data["revoker_id"],
                role_id=data["operator_role_id"],
                permission_key="identity.roles.permissions.manage",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        grant_future = pool.submit(grant)
        assert grant_has_locks.wait(timeout=10), "grant did not reach its locked authorization point"
        revoke_future = pool.submit(revoke)
        assert revoke_started.wait(timeout=10), "revocation thread did not start"
        assert not revoke_has_target_role_lock.wait(timeout=0.5), (
            "revocation passed the role lock while the authorized grant held it"
        )
        allow_grant_to_finish.set()
        assert grant_future.result(timeout=15) is True
        assert revoke_future.result(timeout=15) is True

    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM role_permissions WHERE role_id=%s AND permission_id=%s",
            (data["target_role_id"], data["target_permission_id"]),
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT COUNT(*) FROM role_permissions WHERE role_id=%s AND permission_id=%s",
            (data["operator_role_id"], data["manage_permission_id"]),
        )
        assert cursor.fetchone()[0] == 0
    finally:
        cursor.close()
        connection.close()
