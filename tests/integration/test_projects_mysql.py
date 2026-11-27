"""MySQL integration coverage for project portfolio and milestones."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def project_fixture():
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
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"Project Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Project Team {suffix}"),
        )
        team_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"PRJ-{suffix}", f"Project Test Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Project Test Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        for permission_key in ("project.read", "project.create", "project.update"):
            cursor.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (permission_key,))
            permission = cursor.fetchone()
            assert permission, f"{permission_key} must be seeded by migrations"
            cursor.execute(
                "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
                (role_id, permission[0]),
            )
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,scope_reference,is_active)
               VALUES (%s,%s,'TEAM',%s,TRUE)""",
            (employee_id, role_id, str(team_id)),
        )
        cursor.execute(
            """INSERT INTO employee_team_memberships (employee_id,team_id,is_primary)
               VALUES (%s,%s,TRUE)""",
            (employee_id, team_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {
        "employee_id": employee_id, "team_id": team_id,
        "department_id": department_id, "role_id": role_id,
        "suffix": suffix,
    }
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute("SELECT project_id FROM projects WHERE project_key=%s", (f"PRJ-{suffix}".upper(),))
        row = cursor.fetchone()
        if row:
            project_id = int(row[0])
            cursor.execute("DELETE FROM project_milestones WHERE project_id=%s", (project_id,))
            cursor.execute("DELETE FROM project_team_assignments WHERE project_id=%s", (project_id,))
            cursor.execute("DELETE FROM audit_events WHERE target_type='project' AND target_id=%s", (str(project_id),))
            cursor.execute("DELETE FROM projects WHERE project_id=%s", (project_id,))
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


def test_project_milestone_lifecycle_and_audit(project_fixture):
    from itoms.services.projects import (
        create_milestone, create_project, get_project_detail, list_projects,
        update_milestone_status, update_project_status,
    )
    from itoms.db.connection import get_connection

    data = project_fixture
    project_id = create_project(
        actor_employee_id=data["employee_id"],
        project_key=f"PRJ-{data['suffix']}",
        project_name="Integration test project",
        description="Validates scoped project creation and milestone lifecycle.",
        team_ids=[data["team_id"]],
        start_date="2027-01-01",
        target_end_date="2027-06-30",
    )
    assert any(item["project_id"] == project_id for item in list_projects(
        actor_employee_id=data["employee_id"]
    ))
    milestone_id = create_milestone(
        actor_employee_id=data["employee_id"], project_id=project_id,
        title="Architecture approved", due_date="2027-02-15",
    )
    update_milestone_status(
        actor_employee_id=data["employee_id"], milestone_id=milestone_id,
        new_status="IN_PROGRESS",
    )
    update_milestone_status(
        actor_employee_id=data["employee_id"], milestone_id=milestone_id,
        new_status="COMPLETED",
    )
    update_project_status(
        actor_employee_id=data["employee_id"], project_id=project_id,
        new_status="ACTIVE",
    )
    detail = get_project_detail(actor_employee_id=data["employee_id"], project_id=project_id)
    assert detail["status"] == "ACTIVE"
    assert detail["teams"] == [f"Project Team {data['suffix']}"]
    assert detail["milestones"][0]["status"] == "COMPLETED"

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT event_key FROM audit_events WHERE target_type='project' AND target_id=%s",
            (str(project_id),),
        )
        events = [row[0] for row in cursor.fetchall()]
        assert "PROJECT_CREATED" in events
        assert "PROJECT_STATUS_CHANGED" in events
        cursor.execute(
            """SELECT event_key FROM audit_events
               WHERE target_type='project_milestone' AND target_id=%s""",
            (str(milestone_id),),
        )
        milestone_events = [row[0] for row in cursor.fetchall()]
        assert milestone_events.count("PROJECT_MILESTONE_CREATED") == 1
        assert milestone_events.count("PROJECT_MILESTONE_STATUS_CHANGED") == 2
    finally:
        cursor.close()
        connection.close()
