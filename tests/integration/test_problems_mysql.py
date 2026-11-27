"""MySQL integration coverage for Problem Management and known errors."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def problem_fixture():
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
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"Problem Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Problem Team {suffix}"),
        )
        team_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"PRB-{suffix}", f"Problem Test Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Problem Test Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        keys = ("problem.read", "problem.create", "problem.update", "incident.read")
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
            """INSERT INTO incident_tickets
               (ticket_number,title,description,requester_employee_id,assigned_team_id,status,priority)
               VALUES (%s,%s,%s,%s,%s,'OPEN','HIGH')""",
            (f"INC-PRB-{suffix}", "Repeated database timeout", "Database timeout symptoms.", employee_id, team_id),
        )
        ticket_id = int(cursor.lastrowid)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {"employee_id": employee_id, "team_id": team_id, "department_id": department_id,
            "role_id": role_id, "ticket_id": ticket_id, "suffix": suffix}
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute("SELECT problem_id FROM problem_records WHERE problem_key LIKE %s", ("PRB-%",))
        # Scope cleanup by the test employee, not a broad problem-key pattern.
        cursor.execute("SELECT problem_id FROM problem_records WHERE created_by=%s", (employee_id,))
        problem_ids = [int(row[0]) for row in cursor.fetchall()]
        for problem_id in problem_ids:
            cursor.execute("DELETE FROM known_error_records WHERE problem_id=%s", (problem_id,))
            cursor.execute("DELETE FROM problem_incident_links WHERE problem_id=%s", (problem_id,))
        if problem_ids:
            marks = ",".join(["%s"] * len(problem_ids))
            cursor.execute(f"DELETE FROM problem_records WHERE problem_id IN ({marks})", tuple(problem_ids))
        cursor.execute("DELETE FROM incident_activity WHERE ticket_id=%s", (ticket_id,))
        cursor.execute("DELETE FROM incident_comments WHERE ticket_id=%s", (ticket_id,))
        cursor.execute("DELETE FROM incident_tickets WHERE ticket_id=%s", (ticket_id,))
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


def test_problem_links_incident_and_publishes_known_error(problem_fixture):
    from itoms.services.problems import (
        create_known_error, create_problem, get_problem_detail, link_incident,
        transition_problem,
    )
    from itoms.db.connection import get_connection

    data = problem_fixture
    problem_id = create_problem(
        actor_employee_id=data["employee_id"], title="Repeated database timeouts",
        description="Investigate recurring database timeout incidents.",
        owner_team_id=data["team_id"], priority="HIGH",
    )
    link_incident(
        actor_employee_id=data["employee_id"], problem_id=problem_id,
        ticket_id=data["ticket_id"],
    )
    transition_problem(
        actor_employee_id=data["employee_id"], problem_id=problem_id,
        new_status="INVESTIGATING", root_cause="Connection pool exhaustion under load.",
    )
    transition_problem(
        actor_employee_id=data["employee_id"], problem_id=problem_id,
        new_status="KNOWN_ERROR",
    )
    known_error_id = create_known_error(
        actor_employee_id=data["employee_id"], problem_id=problem_id,
        title="Connection pool exhaustion",
        symptoms="Database requests time out during peak load.",
        workaround="Recycle the affected application connection pool after validating active transactions.",
    )
    detail = get_problem_detail(actor_employee_id=data["employee_id"], problem_id=problem_id)
    assert detail["status"] == "KNOWN_ERROR"
    assert len(detail["incidents"]) == 1
    assert detail["known_error"]["known_error_id"] == known_error_id
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT event_key FROM audit_events WHERE target_type='problem' AND target_id=%s",
            (str(problem_id),),
        )
        events = [row[0] for row in cursor.fetchall()]
        assert "PROBLEM_CREATED" in events
        assert "PROBLEM_INCIDENT_LINKED" in events
        assert events.count("PROBLEM_STATUS_CHANGED") == 2
    finally:
        cursor.close()
        connection.close()
