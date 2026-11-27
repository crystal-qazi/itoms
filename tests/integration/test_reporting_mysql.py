"""MySQL integration coverage for saved reports and source authorization."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def report_fixture():
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
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"Report Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Report Team {suffix}"),
        )
        team_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"RPT-{suffix}", f"Report Test Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Report Test Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        keys = ("reports.read", "reports.create", "reports.run", "operations.read", "operations.create")
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

    data = {"employee_id": employee_id, "team_id": team_id, "department_id": department_id,
            "role_id": role_id, "suffix": suffix}
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute("DELETE FROM saved_reports WHERE created_by=%s", (employee_id,))
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


def test_saved_report_runs_only_authorized_service_rows(report_fixture):
    from itoms.services.operations import create_operational_work_item
    from itoms.services.reporting import create_report, run_report, build_csv

    data = report_fixture
    create_operational_work_item(
        actor_employee_id=data["employee_id"], domain="NETWORK",
        title="Reportable switch replacement", description="Visible in the report.",
        owner_team_id=data["team_id"], priority="HIGH",
    )
    report_id = create_report(
        employee_id=data["employee_id"], report_name=f"Operations {data['suffix']}",
        dataset_key="operations", columns=["work_number", "title", "priority", "status"],
        filters={"domain": "NETWORK"},
    )
    name, columns, rows = run_report(employee_id=data["employee_id"], report_id=report_id)
    assert name.startswith("Operations ")
    assert len(rows) == 1
    assert rows[0]["title"] == "Reportable switch replacement"
    assert "work_number" in build_csv(columns, rows)
