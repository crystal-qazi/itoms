"""MySQL integration coverage for department-scoped directory administration."""
from __future__ import annotations

import hashlib
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def directory_admin_fixture():
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
    context = app.app_context()
    context.push()
    suffix = uuid.uuid4().hex[:12]
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"Directory Admin {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Directory Team {suffix}"),
        )
        team_id = int(cursor.lastrowid)
        employees = []
        for label in ("actor", "manager", "member"):
            cursor.execute(
                """INSERT INTO employees (employee_code,full_name,department_id,is_active)
                   VALUES (%s,%s,%s,TRUE)""",
                (f"DIR-{suffix}-{label}", f"Directory {label}", department_id),
            )
            employees.append(int(cursor.lastrowid))
        actor_id, manager_id, member_id = employees
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Directory Admin Role {suffix}", "Temporary directory test role"),
        )
        role_id = int(cursor.lastrowid)
        for permission_key in ("identity.directory.manage", "identity.roles.assign"):
            cursor.execute(
                "SELECT permission_id FROM permissions WHERE permission_key=%s",
                (permission_key,),
            )
            permission = cursor.fetchone()
            assert permission, f"{permission_key} must be seeded by the identity migrations"
            cursor.execute(
                "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
                (role_id, permission[0]),
            )
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Directory Member Role {suffix}", "Temporary role for revocation integration test"),
        )
        member_role_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,scope_reference,is_active)
               VALUES (%s,%s,'DEPARTMENT',%s,TRUE)""",
            (actor_id, role_id, str(department_id)),
        )
        cursor.execute(
            """INSERT INTO employee_team_memberships (employee_id,team_id,is_primary)
               VALUES (%s,%s,FALSE)""",
            (manager_id, team_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {
        "app": app, "department_id": department_id, "team_id": team_id,
        "actor_id": actor_id, "manager_id": manager_id, "member_id": member_id,
        "role_id": role_id, "member_role_id": member_role_id, "employee_ids": employees,
        "extra_team_ids": [],
    }
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute("DELETE FROM team_management_assignments WHERE team_id=%s", (team_id,))
        cursor.execute("DELETE FROM employee_team_memberships WHERE team_id=%s", (team_id,))
        cursor.execute("DELETE FROM audit_events WHERE actor_employee_id=%s", (actor_id,))
        marks = ",".join(["%s"] * len(employees))
        cursor.execute(f"DELETE FROM employee_role_assignments WHERE employee_id IN ({marks})", tuple(employees))
        cursor.execute("DELETE FROM role_permissions WHERE role_id IN (%s,%s)", (role_id, member_role_id))
        cursor.execute("DELETE FROM application_roles WHERE role_id IN (%s,%s)", (role_id, member_role_id))
        cursor.execute(f"DELETE FROM employees WHERE employee_id IN ({marks})", tuple(employees))
        for extra_team_id in data["extra_team_ids"]:
            cursor.execute("DELETE FROM teams WHERE team_id=%s", (extra_team_id,))
        cursor.execute("DELETE FROM teams WHERE team_id=%s", (team_id,))
        cursor.execute("DELETE FROM departments WHERE department_id=%s", (department_id,))
        cleanup.commit()
    except Exception:
        cleanup.rollback()
        raise
    finally:
        cursor.close()
        cleanup.close()
        context.pop()


def test_department_scoped_directory_membership_and_manager_workflow(directory_admin_fixture):
    from itoms.services.directory_admin import (
        assign_team_manager, assign_team_membership, create_team, deactivate_employee,
        list_directory, remove_team_manager, remove_team_membership, set_team_active,
    )
    from itoms.services.directory_admin import DirectoryAdministrationError

    data = directory_admin_fixture
    actor_id, manager_id, member_id = (
        data["actor_id"], data["manager_id"], data["member_id"]
    )
    team_id = data["team_id"]

    listing = list_directory(actor_employee_id=actor_id)
    assert {row["employee_id"] for row in listing["employees"]} == {
        actor_id, manager_id, member_id
    }

    assign_team_membership(
        actor_employee_id=actor_id, employee_id=member_id, team_id=team_id,
    )
    assert assign_team_manager(
        actor_employee_id=actor_id, manager_employee_id=manager_id, team_id=team_id,
    ) is True
    assert assign_team_manager(
        actor_employee_id=actor_id, manager_employee_id=manager_id, team_id=team_id,
    ) is False

    from itoms.services.identity_admin import assign_role, revoke_role_assignment
    managed_assignment_id = assign_role(
        actor_employee_id=actor_id, employee_id=manager_id,
        role_id=data["member_role_id"], scope_type="MANAGED_TEAMS",
    )
    assert revoke_role_assignment(
        actor_employee_id=actor_id, assignment_id=managed_assignment_id,
    ) is True

    listing = list_directory(actor_employee_id=actor_id)
    assert any(
        row["manager_employee_id"] == manager_id and row["team_id"] == team_id
        for row in listing["managers"]
    )

    with pytest.raises(DirectoryAdministrationError, match="Remove the manager assignment"):
        remove_team_membership(
            actor_employee_id=actor_id, employee_id=manager_id, team_id=team_id,
        )

    assert remove_team_manager(
        actor_employee_id=actor_id, manager_employee_id=manager_id, team_id=team_id,
    ) is True
    assert remove_team_membership(
        actor_employee_id=actor_id, employee_id=manager_id, team_id=team_id,
    ) is None
    assert remove_team_membership(
        actor_employee_id=actor_id, employee_id=member_id, team_id=team_id,
    ) is None

    extra_team_id = create_team(
        actor_employee_id=actor_id, team_name=f"Directory Extra {team_id}",
    )
    data["extra_team_ids"].append(extra_team_id)
    assert set_team_active(
        actor_employee_id=actor_id, team_id=extra_team_id, is_active=False,
    ) is True
    assert set_team_active(
        actor_employee_id=actor_id, team_id=extra_team_id, is_active=True,
    ) is True
    assert set_team_active(
        actor_employee_id=actor_id, team_id=team_id, is_active=False,
    ) is True
    assert set_team_active(
        actor_employee_id=actor_id, team_id=team_id, is_active=True,
    ) is True

    assignment_id = assign_role(
        actor_employee_id=actor_id, employee_id=member_id,
        role_id=data["member_role_id"], scope_type="OWN",
    )
    assert revoke_role_assignment(
        actor_employee_id=actor_id, assignment_id=assignment_id,
    ) is True
    assert revoke_role_assignment(
        actor_employee_id=actor_id, assignment_id=assignment_id,
    ) is False
    assert not any(
        row["assignment_id"] == assignment_id
        for row in list_directory(actor_employee_id=actor_id)["role_assignments"]
    )

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO user_accounts
               (employee_id,username,password_hash,account_status,session_version)
               VALUES (%s,%s,'test-hash','ACTIVE',1)""",
            (member_id, f"directory-member-{member_id}"),
        )
        account_id = int(cursor.lastrowid)
        token_hash = hashlib.sha256(f"directory-session-{member_id}".encode()).hexdigest()
        cursor.execute(
            """INSERT INTO user_sessions
               (account_id,token_hash,session_version,last_activity_at,expires_at)
               VALUES (%s,%s,1,UTC_TIMESTAMP(),DATE_ADD(UTC_TIMESTAMP(),INTERVAL 60 MINUTE))""",
            (account_id, token_hash),
        )
        cursor.execute(
            "INSERT INTO account_recovery_codes (account_id,code_hash) VALUES (%s,'test-recovery-hash')",
            (account_id,),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    assert deactivate_employee(actor_employee_id=actor_id, employee_id=member_id) is True
    assert deactivate_employee(actor_employee_id=actor_id, employee_id=member_id) is False

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT is_active FROM employees WHERE employee_id=%s", (member_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT account_status,session_version,mfa_enabled,totp_secret_encrypted FROM user_accounts WHERE account_id=%s",
            (account_id,),
        )
        account_status, session_version, mfa_enabled, totp_secret = cursor.fetchone()
        assert (account_status, session_version, mfa_enabled, totp_secret) == ("DISABLED", 2, 0, None)
        cursor.execute(
            "SELECT revoked_at,revoke_reason FROM user_sessions WHERE account_id=%s",
            (account_id,),
        )
        revoked_at, revoke_reason = cursor.fetchone()
        assert revoked_at is not None and revoke_reason == "ACCOUNT_DISABLED"
        cursor.execute("SELECT COUNT(*) FROM account_recovery_codes WHERE account_id=%s", (account_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE actor_employee_id=%s AND event_key='IDENTITY_EMPLOYEE_DEACTIVATED'
                 AND target_id=%s""",
            (actor_id, str(member_id)),
        )
        assert cursor.fetchone()[0] == 1
    finally:
        cursor.close()
        connection.close()
