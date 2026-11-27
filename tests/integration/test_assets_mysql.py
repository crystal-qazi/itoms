"""MySQL integration coverage for scoped assets and basic maintenance."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def asset_fixture():
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
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"Asset Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Asset Team {suffix}"),
        )
        team_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"AST-{suffix}", f"Asset Test Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Asset Test Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        keys = ("asset.read", "asset.create", "asset.update",
                "asset.maintenance.create", "asset.maintenance.update")
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
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {"employee_id": employee_id, "team_id": team_id, "department_id": department_id, "role_id": role_id, "suffix": suffix}
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        tag = f"AST-{suffix}".upper()
        cursor.execute("SELECT asset_id FROM asset_records WHERE asset_tag=%s", (tag,))
        row = cursor.fetchone()
        if row:
            asset_id = int(row[0])
            cursor.execute("DELETE FROM asset_maintenance WHERE asset_id=%s", (asset_id,))
            cursor.execute("DELETE FROM audit_events WHERE target_type='asset' AND target_id=%s", (str(asset_id),))
            cursor.execute("DELETE FROM asset_records WHERE asset_id=%s", (asset_id,))
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


def test_asset_registration_and_repair_ticket_lifecycle(asset_fixture):
    from itoms.services.assets import (
        create_asset, create_maintenance, list_assets, list_maintenance,
        update_asset_status, update_maintenance_status,
    )
    from itoms.db.connection import get_connection

    data = asset_fixture
    asset_id = create_asset(
        actor_employee_id=data["employee_id"], asset_tag=f"AST-{data['suffix']}",
        asset_name="Integration test laptop", asset_type="COMPUTER",
        owner_team_id=data["team_id"], manufacturer="Example", model="Model 1",
        location_label="IT Lab",
    )
    assert any(item["asset_id"] == asset_id for item in list_assets(actor_employee_id=data["employee_id"]))
    maintenance_id = create_maintenance(
        actor_employee_id=data["employee_id"], asset_id=asset_id,
        issue_description="Battery does not charge.",
    )
    assert any(item["maintenance_id"] == maintenance_id for item in list_maintenance(actor_employee_id=data["employee_id"]))
    update_maintenance_status(
        actor_employee_id=data["employee_id"], maintenance_id=maintenance_id,
        new_status="IN_PROGRESS",
    )
    update_maintenance_status(
        actor_employee_id=data["employee_id"], maintenance_id=maintenance_id,
        new_status="COMPLETED",
    )
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT asset_status FROM asset_records WHERE asset_id=%s", (asset_id,))
        assert cursor.fetchone()[0] == "IN_STOCK"
    finally:
        cursor.close()
        connection.close()
    update_asset_status(
        actor_employee_id=data["employee_id"], asset_id=asset_id, new_status="IN_USE",
    )
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT asset_status FROM asset_records WHERE asset_id=%s", (asset_id,))
        assert cursor.fetchone()[0] == "IN_USE"
        cursor.execute(
            "SELECT event_key FROM audit_events WHERE target_type='asset_maintenance' AND target_id=%s",
            (str(maintenance_id),),
        )
        events = [row[0] for row in cursor.fetchall()]
        assert events.count("ASSET_MAINTENANCE_OPENED") == 1
        assert events.count("ASSET_MAINTENANCE_STATUS_CHANGED") == 2
    finally:
        cursor.close()
        connection.close()
