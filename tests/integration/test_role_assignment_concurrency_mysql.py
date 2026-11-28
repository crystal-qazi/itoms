"""MySQL race coverage for transaction-bound role assignment authorization."""
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
def role_assignment_fixture():
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
            (f"Role Assignment Concurrency {suffix}",),
        )
        department_id = int(cursor.lastrowid)
        employee_ids = []
        for label in ("assigner", "revoker", "target"):
            cursor.execute(
                """INSERT INTO employees
                   (employee_code,full_name,department_id,is_active)
                   VALUES (%s,%s,%s,TRUE)""",
                (f"RAC-{suffix}-{label}", f"Role assignment {label}", department_id),
            )
            employee_ids.append(int(cursor.lastrowid))
        assigner_id, revoker_id, target_employee_id = employee_ids

        team_ids = []
        for label in ("managed-a", "managed-b"):
            cursor.execute(
                "INSERT INTO teams (team_name,department_id,is_active) VALUES (%s,%s,TRUE)",
                (f"RA {label} {suffix}", department_id),
            )
            team_ids.append(int(cursor.lastrowid))
        for team_id in team_ids:
            cursor.execute(
                "INSERT INTO employee_team_memberships (employee_id,team_id,is_primary) VALUES (%s,%s,%s)",
                (target_employee_id, team_id, False),
            )
            cursor.execute(
                "INSERT INTO team_management_assignments (manager_employee_id,team_id,assigned_by) VALUES (%s,%s,%s)",
                (target_employee_id, team_id, assigner_id),
            )

        role_ids = []
        for label in ("assigner", "revoker", "target"):
            cursor.execute(
                "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
                (f"RA {label} {suffix}", "Temporary role assignment concurrency test role"),
            )
            role_ids.append(int(cursor.lastrowid))
        assigner_role_id, revoker_role_id, target_role_id = role_ids

        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("identity.roles.assign",),
        )
        assign_permission = cursor.fetchone()
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("identity.roles.permissions.manage",),
        )
        manage_permission = cursor.fetchone()
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key=%s",
            ("identity.directory.manage",),
        )
        directory_manage_permission = cursor.fetchone()
        assert assign_permission and manage_permission and directory_manage_permission, "permission catalogue migrations must be applied"

        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (assigner_role_id, assign_permission[0]),
        )
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (revoker_role_id, manage_permission[0]),
        )
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (revoker_role_id, directory_manage_permission[0]),
        )
        for employee_id, role_id in (
            (assigner_id, assigner_role_id),
            (revoker_id, revoker_role_id),
        ):
            cursor.execute(
                """INSERT INTO employee_role_assignments
                   (employee_id,role_id,scope_type,scope_reference,is_active)
                   VALUES (%s,%s,'DEPARTMENT',%s,TRUE)""",
                (employee_id, role_id, str(department_id)),
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
        "department_id": department_id,
        "assigner_id": assigner_id,
        "revoker_id": revoker_id,
        "target_employee_id": target_employee_id,
        "assigner_role_id": assigner_role_id,
        "revoker_role_id": revoker_role_id,
        "target_role_id": target_role_id,
        "team_ids": team_ids,
    }
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        actor_ids = (assigner_id, revoker_id, target_employee_id)
        marks = ",".join(["%s"] * len(actor_ids))
        cursor.execute(
            f"DELETE FROM audit_events WHERE actor_employee_id IN ({marks})",
            actor_ids,
        )
        cursor.execute(
            "DELETE FROM team_management_assignments WHERE manager_employee_id=%s",
            (target_employee_id,),
        )
        cursor.execute(
            f"DELETE FROM employee_team_memberships WHERE employee_id IN ({marks})",
            actor_ids,
        )
        cursor.execute(
            f"DELETE FROM employee_role_assignments WHERE employee_id IN ({marks})",
            actor_ids,
        )
        cursor.execute(
            "DELETE FROM role_permissions WHERE role_id IN (%s,%s,%s)",
            (assigner_role_id, revoker_role_id, target_role_id),
        )
        cursor.execute(
            "DELETE FROM application_roles WHERE role_id IN (%s,%s,%s)",
            (assigner_role_id, revoker_role_id, target_role_id),
        )
        cursor.execute(
            f"DELETE FROM employees WHERE employee_id IN ({marks})",
            actor_ids,
        )
        cursor.execute(
            "DELETE FROM teams WHERE team_id IN (%s,%s)",
            tuple(team_ids),
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


def test_role_assignment_holds_authorization_until_commit_before_revocation(
    role_assignment_fixture, monkeypatch
):
    from itoms.services import identity_admin

    data = role_assignment_fixture
    original_check = identity_admin.has_permissions_in_transaction
    authorization_locked = threading.Event()
    allow_assignment_to_finish = threading.Event()
    revocation_started = threading.Event()

    def coordinated_check(cur, actor_employee_id, permission_key, resources, **kwargs):
        result = original_check(
            cur, actor_employee_id, permission_key, resources, **kwargs
        )
        if actor_employee_id == data["assigner_id"] and permission_key == "identity.roles.assign":
            authorization_locked.set()
            if not allow_assignment_to_finish.wait(timeout=15):
                raise TimeoutError("test did not release the authorized role assignment")
        return result

    monkeypatch.setattr(
        identity_admin, "has_permissions_in_transaction", coordinated_check
    )

    def assign():
        with data["app"].app_context():
            return identity_admin.assign_role(
                actor_employee_id=data["assigner_id"],
                employee_id=data["target_employee_id"],
                role_id=data["target_role_id"],
                scope_type="DEPARTMENT",
            )

    def revoke():
        with data["app"].app_context():
            revocation_started.set()
            return identity_admin.revoke_role_permission(
                actor_employee_id=data["revoker_id"],
                role_id=data["assigner_role_id"],
                permission_key="identity.roles.assign",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        assignment_future = pool.submit(assign)
        assert authorization_locked.wait(timeout=10), (
            "role assignment did not reach its transaction-bound authorization point"
        )
        revocation_future = pool.submit(revoke)
        assert revocation_started.wait(timeout=10), "permission revocation did not start"
        assert not revocation_future.done(), (
            "permission revocation passed while the authorized assignment held its locks"
        )
        allow_assignment_to_finish.set()
        assignment_id = assignment_future.result(timeout=15)
        assert assignment_id > 0
        assert revocation_future.result(timeout=15) is True

    with pytest.raises(identity_admin.IdentityAdministrationError, match="Not authorized"):
        identity_admin.assign_role(
            actor_employee_id=data["assigner_id"],
            employee_id=data["target_employee_id"],
            role_id=data["target_role_id"],
            scope_type="DEPARTMENT",
        )



def test_permission_revocation_wins_before_role_assignment_authorization(
    role_assignment_fixture, monkeypatch
):
    from itoms.services import identity_admin

    data = role_assignment_fixture
    original_lock = identity_admin._lock_actor_permission_for_role_change
    revocation_locks_acquired = threading.Event()
    allow_revocation_to_finish = threading.Event()

    def coordinated_lock(cur, **kwargs):
        result = original_lock(cur, **kwargs)
        if kwargs.get("actor_employee_id") == data["revoker_id"]:
            revocation_locks_acquired.set()
            if not allow_revocation_to_finish.wait(timeout=15):
                raise TimeoutError("test did not release permission revocation")
        return result

    monkeypatch.setattr(
        identity_admin, "_lock_actor_permission_for_role_change", coordinated_lock
    )

    def revoke():
        with data["app"].app_context():
            return identity_admin.revoke_role_permission(
                actor_employee_id=data["revoker_id"],
                role_id=data["assigner_role_id"],
                permission_key="identity.roles.assign",
            )

    def assign():
        with data["app"].app_context():
            return identity_admin.assign_role(
                actor_employee_id=data["assigner_id"],
                employee_id=data["target_employee_id"],
                role_id=data["target_role_id"],
                scope_type="DEPARTMENT",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        revocation_future = pool.submit(revoke)
        assert revocation_locks_acquired.wait(timeout=10), (
            "permission revocation did not acquire the target role lock"
        )
        assignment_future = pool.submit(assign)
        assert not assignment_future.done(), (
            "role assignment passed while permission revocation held the role lock"
        )
        allow_revocation_to_finish.set()
        assert revocation_future.result(timeout=15) is True
        with pytest.raises(identity_admin.IdentityAdministrationError, match="Not authorized"):
            assignment_future.result(timeout=15)



def test_managed_teams_role_assignment_revalidates_all_team_memberships(
    role_assignment_fixture,
):
    from itoms.services import identity_admin

    data = role_assignment_fixture
    assignment_id = identity_admin.assign_role(
        actor_employee_id=data["assigner_id"],
        employee_id=data["target_employee_id"],
        role_id=data["target_role_id"],
        scope_type="MANAGED_TEAMS",
    )
    assert assignment_id > 0

    from itoms.db.connection import get_connection
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """SELECT scope_type,scope_reference FROM employee_role_assignments
               WHERE assignment_id=%s""",
            (assignment_id,),
        )
        row = cursor.fetchone()
        assert row == ("MANAGED_TEAMS", None)
    finally:
        cursor.close()
        connection.close()

    from itoms.services import directory_admin
    for team_id in data["team_ids"]:
        directory_admin.remove_team_manager(
            actor_employee_id=data["revoker_id"],
            manager_employee_id=data["target_employee_id"],
            team_id=team_id,
        )
    with pytest.raises(identity_admin.IdentityAdministrationError, match="no active managed teams"):
        identity_admin.assign_role(
            actor_employee_id=data["assigner_id"],
            employee_id=data["target_employee_id"],
            role_id=data["target_role_id"],
            scope_type="MANAGED_TEAMS",
        )


def test_team_membership_revocation_wins_before_team_scoped_role_assignment(
    role_assignment_fixture, monkeypatch
):
    from itoms.services import directory, directory_admin, identity_admin

    data = role_assignment_fixture
    original_check = directory.has_permissions_in_transaction
    revocation_locked = threading.Event()
    allow_revocation = threading.Event()

    def coordinated_check(cur, actor_employee_id, permission_key, resources, **kwargs):
        result = original_check(cur, actor_employee_id, permission_key, resources, **kwargs)
        if actor_employee_id == data["revoker_id"] and permission_key == "identity.directory.manage":
            revocation_locked.set()
            if not allow_revocation.wait(timeout=15):
                raise TimeoutError("test did not release membership revocation")
        return result

    monkeypatch.setattr(directory, "has_permissions_in_transaction", coordinated_check)

    def remove_membership():
        with data["app"].app_context():
            return directory_admin.remove_team_membership(
                actor_employee_id=data["revoker_id"],
                employee_id=data["target_employee_id"],
                team_id=data["team_ids"][0],
            )

    def assign_team_role():
        with data["app"].app_context():
            return identity_admin.assign_role(
                actor_employee_id=data["assigner_id"],
                employee_id=data["target_employee_id"],
                role_id=data["target_role_id"],
                scope_type="TEAM",
                scope_reference=str(data["team_ids"][0]),
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        removal_future = pool.submit(remove_membership)
        assert revocation_locked.wait(timeout=10), "membership removal did not acquire its locks"
        assignment_future = pool.submit(assign_team_role)
        assert not assignment_future.done(), "team-scoped assignment passed while membership removal held locks"
        allow_revocation.set()
        removal_future.result(timeout=15)
        with pytest.raises(identity_admin.IdentityAdministrationError, match="belong to the active team"):
            assignment_future.result(timeout=15)


def test_employee_deactivation_wins_before_role_assignment(
    role_assignment_fixture, monkeypatch
):
    from itoms.services import directory_admin, identity_admin

    data = role_assignment_fixture
    # Deactivation requires team and manager scopes to be explicitly removed first.
    for team_id in data["team_ids"]:
        directory_admin.remove_team_membership(
            actor_employee_id=data["revoker_id"],
            employee_id=data["target_employee_id"],
            team_id=team_id,
        )
        directory_admin.remove_team_manager(
            actor_employee_id=data["revoker_id"],
            manager_employee_id=data["target_employee_id"],
            team_id=team_id,
        )

    original_check = directory_admin.has_permissions_in_transaction
    deactivation_locked = threading.Event()
    allow_deactivation = threading.Event()

    def coordinated_check(cur, actor_employee_id, permission_key, resources, **kwargs):
        result = original_check(cur, actor_employee_id, permission_key, resources, **kwargs)
        if actor_employee_id == data["revoker_id"] and permission_key == "identity.directory.manage":
            deactivation_locked.set()
            if not allow_deactivation.wait(timeout=15):
                raise TimeoutError("test did not release employee deactivation")
        return result

    monkeypatch.setattr(directory_admin, "has_permissions_in_transaction", coordinated_check)

    def deactivate():
        with data["app"].app_context():
            return directory_admin.deactivate_employee(
                actor_employee_id=data["revoker_id"],
                employee_id=data["target_employee_id"],
            )

    def assign():
        with data["app"].app_context():
            return identity_admin.assign_role(
                actor_employee_id=data["assigner_id"],
                employee_id=data["target_employee_id"],
                role_id=data["target_role_id"],
                scope_type="DEPARTMENT",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        deactivation_future = pool.submit(deactivate)
        assert deactivation_locked.wait(timeout=10), "deactivation did not acquire its locks"
        assignment_future = pool.submit(assign)
        assert not assignment_future.done(), "role assignment passed while deactivation held employee locks"
        allow_deactivation.set()
        assert deactivation_future.result(timeout=15) is True
        with pytest.raises(identity_admin.IdentityAdministrationError, match="inactive"):
            assignment_future.result(timeout=15)



def test_authorization_locking_queries_use_indexes_under_repeatable_read(
    role_assignment_fixture,
):
    from itoms.db.connection import get_connection

    data = role_assignment_fixture
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT @@transaction_isolation AS isolation_level")
        isolation = cursor.fetchone()["isolation_level"]
        assert isolation == "REPEATABLE-READ"

        checks = [
            (
                "employee primary-key lookup",
                "SELECT employee_id FROM employees WHERE employee_id=%s",
                (data["assigner_id"],),
            ),
            (
                "team primary-key lookup",
                "SELECT team_id FROM teams WHERE team_id=%s",
                (data["team_ids"][0],),
            ),
            (
                "employee-team membership lookup",
                "SELECT 1 FROM employee_team_memberships WHERE employee_id=%s AND team_id=%s",
                (data["target_employee_id"], data["team_ids"][0]),
            ),
            (
                "employee role-assignment lookup",
                """SELECT role_id FROM employee_role_assignments
                   WHERE employee_id=%s AND is_active=TRUE
                     AND (expires_at IS NULL OR expires_at>UTC_TIMESTAMP())
                   ORDER BY role_id""",
                (data["assigner_id"],),
            ),
            (
                "role-permission lookup",
                "SELECT permission_id FROM role_permissions WHERE role_id=%s AND permission_id=%s",
                (data["assigner_role_id"], 1),
            ),
        ]
        for label, query, params in checks:
            cursor.execute("EXPLAIN " + query, params)
            plan = cursor.fetchone()
            assert plan and plan.get("type") != "ALL" and plan.get("key"), (
                f"{label} must use an index; observed plan: {plan}"
            )
    finally:
        cursor.close()
        connection.close()
