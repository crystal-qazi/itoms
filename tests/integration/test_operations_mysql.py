"""MySQL integration coverage for technical operations and Oracle inventory."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def operations_fixture():
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
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"Ops Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Ops Team {suffix}"),
        )
        team_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"OPS-{suffix}", f"Ops Test Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Ops Test Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        keys = ("operations.read", "operations.create", "operations.update",
                "oracle.inventory.read", "oracle.inventory.manage")
        for key in keys:
            cursor.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (key,))
            permission = cursor.fetchone()
            assert permission, f"{key} must be seeded by migrations"
            cursor.execute("INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)", (role_id, permission[0]))
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,scope_reference,is_active)
               VALUES (%s,%s,'TEAM',%s,TRUE)""",
            (employee_id, role_id, str(team_id)),
        )
        cursor.execute(
            "INSERT INTO employee_team_memberships (employee_id,team_id,is_primary) VALUES (%s,%s,TRUE)",
            (employee_id, team_id),
        )
        cursor.execute(
            """INSERT INTO service_records
               (service_key,service_name,service_type,owner_team_id,criticality,lifecycle_status)
               VALUES (%s,%s,'DATABASE',%s,'HIGH','ACTIVE')""",
            (f"OPS-SVC-{suffix}", f"Ops Test Service {suffix}", team_id),
        )
        service_id = int(cursor.lastrowid)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {"employee_id": employee_id, "team_id": team_id, "department_id": department_id,
            "role_id": role_id, "service_id": service_id, "suffix": suffix}
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute("DELETE FROM oracle_database_inventory WHERE service_id=%s", (service_id,))
        cursor.execute("DELETE FROM service_records WHERE service_id=%s", (service_id,))
        cursor.execute("DELETE FROM operational_work_items WHERE created_by=%s", (employee_id,))
        cursor.execute("DELETE FROM audit_events WHERE actor_employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM employee_role_assignments WHERE employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
        cursor.execute("DELETE FROM application_roles WHERE role_id=%s", (role_id,))
        cursor.execute("DELETE FROM employee_team_memberships WHERE employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM employees WHERE employee_id=%s", (employee_id,))
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


def test_operations_work_and_oracle_inventory_lifecycle(operations_fixture):
    from itoms.services.operations import (
        create_operational_work_item, create_oracle_database,
        list_operational_work_items, list_oracle_databases,
        update_oracle_lifecycle, update_work_status,
    )
    from itoms.db.connection import get_connection

    data = operations_fixture
    work_id = create_operational_work_item(
        actor_employee_id=data["employee_id"], domain="NETWORK",
        title="Replace access switch", description="Replace and verify the access switch.",
        owner_team_id=data["team_id"], priority="HIGH",
    )
    assert any(row["work_item_id"] == work_id for row in list_operational_work_items(
        actor_employee_id=data["employee_id"], domain="NETWORK"
    ))
    update_work_status(
        actor_employee_id=data["employee_id"], work_item_id=work_id,
        new_status="IN_PROGRESS",
    )
    update_work_status(
        actor_employee_id=data["employee_id"], work_item_id=work_id,
        new_status="COMPLETED",
    )
    oracle_id = create_oracle_database(
        actor_employee_id=data["employee_id"], service_id=data["service_id"],
        environment_name="TEST", database_name=f"DB_{data['suffix']}",
        host_reference="oracle-test.internal", version_label="19c",
        criticality="HIGH", notes="Integration test reference only.",
    )
    assert any(row["oracle_database_id"] == oracle_id for row in list_oracle_databases(
        actor_employee_id=data["employee_id"]
    ))
    update_oracle_lifecycle(
        actor_employee_id=data["employee_id"], oracle_database_id=oracle_id,
        new_status="MAINTENANCE",
    )
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT status FROM operational_work_items WHERE work_item_id=%s", (work_id,))
        assert cursor.fetchone()[0] == "COMPLETED"
        cursor.execute("SELECT lifecycle_status FROM oracle_database_inventory WHERE oracle_database_id=%s", (oracle_id,))
        assert cursor.fetchone()[0] == "MAINTENANCE"
        cursor.execute(
            "SELECT event_key FROM audit_events WHERE target_type='operational_work_item' AND target_id=%s",
            (str(work_id),),
        )
        assert [row[0] for row in cursor.fetchall()].count("OPERATIONS_WORK_STATUS_CHANGED") == 2
    finally:
        cursor.close()
        connection.close()
