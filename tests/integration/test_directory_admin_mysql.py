"""MySQL integration coverage for department-scoped directory administration."""
from __future__ import annotations

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
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key='identity.directory.manage'"
        )
        permission = cursor.fetchone()
        assert permission, "identity.directory.manage must be seeded by migration 040"
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (role_id, permission[0]),
        )
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
        "role_id": role_id, "employee_ids": employees,
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
        cursor.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
        cursor.execute("DELETE FROM application_roles WHERE role_id=%s", (role_id,))
        cursor.execute(f"DELETE FROM employees WHERE employee_id IN ({marks})", tuple(employees))
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
        assign_team_manager, assign_team_membership, list_directory,
        remove_team_manager, remove_team_membership,
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
