"""MySQL integration tests for notification outbox recovery and replay."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def notification_fixture():
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
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"Notify Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"NTF-{suffix}", f"Notify Test Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Notify Test Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        for key in ("notifications.send", "notifications.outbox.replay"):
            cursor.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (key,))
            permission = cursor.fetchone()
            assert permission, f"{key} must be seeded by migrations"
            cursor.execute("INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)", (role_id, permission[0]))
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active) VALUES (%s,%s,'OWN',TRUE)""",
            (employee_id, role_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    data = {"employee_id": employee_id, "department_id": department_id, "role_id": role_id}
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute(
            """DELETE o FROM notification_outbox o JOIN notifications n
               ON n.notification_id=o.notification_id WHERE n.recipient_employee_id=%s""",
            (employee_id,),
        )
        cursor.execute("DELETE FROM notifications WHERE recipient_employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM audit_events WHERE actor_employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM employee_role_assignments WHERE employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
        cursor.execute("DELETE FROM application_roles WHERE role_id=%s", (role_id,))
        cursor.execute("DELETE FROM employees WHERE employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM departments WHERE department_id=%s", (department_id,))
        cleanup.commit()
    except Exception:
        cleanup.rollback()
        raise
    finally:
        cursor.close()
        cleanup.close()
        context.pop()


def test_outbox_process_recover_and_audited_replay(notification_fixture):
    from itoms.services.notifications import (
        create_notification, process_in_app_outbox_batch, recover_stale_outbox,
        replay_dead_letter,
    )
    from itoms.db.connection import get_connection

    employee_id = notification_fixture["employee_id"]
    notification_id = create_notification(
        actor_employee_id=employee_id, recipient_employee_id=employee_id,
        notification_type="TEST", title="Outbox test", body="Notification body",
    )
    assert process_in_app_outbox_batch(batch_size=10) == 1

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT outbox_id,delivery_status FROM notification_outbox WHERE notification_id=%s", (notification_id,))
        outbox_id, status = cursor.fetchone()
        assert status == "SENT"
        cursor.execute(
            """UPDATE notification_outbox SET delivery_status='PROCESSING',
               locked_at=DATE_SUB(UTC_TIMESTAMP(),INTERVAL 600 SECOND)
               WHERE outbox_id=%s""",
            (outbox_id,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    recovered = recover_stale_outbox(stale_after_seconds=300)
    assert recovered == {"recovered": 1, "dead_lettered": 0}

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("UPDATE notification_outbox SET delivery_status='DEAD' WHERE outbox_id=%s", (outbox_id,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    replay_dead_letter(actor_employee_id=employee_id, outbox_id=outbox_id)

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT delivery_status,attempt_count FROM notification_outbox WHERE outbox_id=%s", (outbox_id,))
        assert cursor.fetchone() == ("PENDING", 0)
        cursor.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE actor_employee_id=%s AND event_key='NOTIFICATION_OUTBOX_REPLAYED'""",
            (employee_id,),
        )
        assert cursor.fetchone()[0] == 1
    finally:
        cursor.close()
        connection.close()
