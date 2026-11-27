"""MySQL integration coverage for idempotent incident SLA escalation."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def sla_fixture():
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
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"SLA Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"SLA Team {suffix}"),
        )
        team_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"SLA-{suffix}", f"SLA Test Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"SLA Test Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        for key in ("incident.sla.manage",):
            cursor.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (key,))
            permission = cursor.fetchone()
            assert permission, f"{key} must be seeded by migrations"
            cursor.execute("INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)", (role_id, permission[0]))
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active) VALUES (%s,%s,'OWN',TRUE)""",
            (employee_id, role_id),
        )
        cursor.execute(
            """INSERT INTO incident_tickets
               (ticket_number,title,description,requester_employee_id,assigned_employee_id,
                assigned_team_id,status,priority,first_response_due_at)
               VALUES (%s,'SLA test incident','SLA integration test',%s,%s,%s,'OPEN','LOW',
                       DATE_SUB(UTC_TIMESTAMP(),INTERVAL 30 MINUTE))""",
            (f"INC-SLA-{suffix}", employee_id, employee_id, team_id),
        )
        ticket_id = int(cursor.lastrowid)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {"employee_id": employee_id, "department_id": department_id, "team_id": team_id,
            "role_id": role_id, "ticket_id": ticket_id, "suffix": suffix}
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute("DELETE FROM incident_sla_escalation_events WHERE ticket_id=%s", (ticket_id,))
        cursor.execute(
            """DELETE o FROM notification_outbox o JOIN notifications n
               ON n.notification_id=o.notification_id
               WHERE n.recipient_employee_id=%s AND n.target_id=%s""",
            (employee_id, str(ticket_id)),
        )
        cursor.execute(
            "DELETE FROM notifications WHERE recipient_employee_id=%s AND target_id=%s",
            (employee_id, str(ticket_id)),
        )
        cursor.execute("DELETE FROM incident_activity WHERE ticket_id=%s", (ticket_id,))
        cursor.execute("DELETE FROM incident_comments WHERE ticket_id=%s", (ticket_id,))
        cursor.execute("DELETE FROM incident_tickets WHERE ticket_id=%s", (ticket_id,))
        cursor.execute(
            """DELETE FROM incident_sla_escalation_policies
               WHERE priority='LOW' AND sla_type='FIRST_RESPONSE' AND escalation_level=9"""
        )
        cursor.execute("DELETE FROM audit_events WHERE actor_employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM employee_role_assignments WHERE employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
        cursor.execute("DELETE FROM application_roles WHERE role_id=%s", (role_id,))
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


def test_sla_escalation_creates_one_audited_notification(sla_fixture):
    from itoms.services.sla_escalations import process_sla_escalations, upsert_escalation_policy
    from itoms.db.connection import get_connection

    data = sla_fixture
    upsert_escalation_policy(
        actor_employee_id=data["employee_id"], priority="LOW",
        sla_type="FIRST_RESPONSE", escalation_level=9,
        after_due_minutes=1, is_active=True,
    )
    first = process_sla_escalations(batch_size=50)
    second = process_sla_escalations(batch_size=50)
    assert first["events_created"] == 1
    assert first["notifications_created"] == 1
    assert second == {"events_created": 0, "notifications_created": 0}
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM incident_sla_escalation_events WHERE ticket_id=%s",
            (data["ticket_id"],),
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            """SELECT COUNT(*) FROM notifications
               WHERE recipient_employee_id=%s AND target_type='incident' AND target_id=%s
                 AND notification_type='INCIDENT_SLA_ESCALATION'""",
            (data["employee_id"], str(data["ticket_id"])),
        )
        assert cursor.fetchone()[0] == 1
    finally:
        cursor.close()
        connection.close()
