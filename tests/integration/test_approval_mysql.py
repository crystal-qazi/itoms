"""Real MySQL integration tests for approval transaction semantics.

Run after applying migrations with ITOMS_RUN_MYSQL_INTEGRATION=1.
These tests create and remove uniquely named fixture records in the configured test DB.
"""
from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import mysql.connector
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def mysql_app():
    from itoms import create_app
    from itoms.config import Config

    class MySQLTestConfig(Config):
        TESTING = True
        SECRET_KEY = "mysql-integration-only"
        DB_HOST = os.environ["ITOMS_DB_HOST"]
        DB_PORT = int(os.environ.get("ITOMS_DB_PORT", "3306"))
        DB_NAME = os.environ["ITOMS_DB_NAME"]
        DB_USER = os.environ["ITOMS_DB_USER"]
        DB_PASSWORD = os.environ["ITOMS_DB_PASSWORD"]

    app = create_app(MySQLTestConfig)
    with app.app_context():
        yield app


@pytest.fixture()
def approval_fixture(mysql_app):
    from itoms.db.connection import get_connection

    suffix = uuid.uuid4().hex[:12]
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO departments (department_name) VALUES (%s)",
            (f"Approval Integration {suffix}",),
        )
        department_id = cursor.lastrowid
        employee_ids = []
        for label in ("requester", "approver_one", "approver_two"):
            cursor.execute(
                """INSERT INTO employees
                   (employee_code,full_name,department_id,is_active)
                   VALUES (%s,%s,%s,TRUE)""",
                (f"IT-{suffix}-{label}", f"Integration {label}", department_id),
            )
            employee_ids.append(int(cursor.lastrowid))
        requester, approver_one, approver_two = employee_ids

        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Approval Integration {suffix}", "Temporary integration-test role"),
        )
        role_id = int(cursor.lastrowid)
        cursor.execute(
            "SELECT permission_id FROM permissions WHERE permission_key='approvals.create'"
        )
        permission = cursor.fetchone()
        assert permission, "approval permission migration must be applied"
        cursor.execute(
            "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
            (role_id, permission[0]),
        )
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'OWN',TRUE)""",
            (requester, role_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    fixture = {
        "suffix": suffix,
        "department_id": int(department_id),
        "requester": requester,
        "approver_one": approver_one,
        "approver_two": approver_two,
        "role_id": role_id,
    }
    yield fixture

    cleanup = get_connection()
    cur = cleanup.cursor()
    try:
        ids = (requester, approver_one, approver_two)
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(
            f"SELECT approval_request_id FROM approval_requests WHERE requested_by IN ({placeholders})",
            ids,
        )
        request_ids = [int(row[0]) for row in cur.fetchall()]
        if request_ids:
            marks = ",".join(["%s"] * len(request_ids))
            cur.execute(f"DELETE FROM approval_history WHERE approval_request_id IN ({marks})", request_ids)
            cur.execute(f"DELETE FROM approval_steps WHERE approval_request_id IN ({marks})", request_ids)
            cur.execute(f"DELETE FROM approval_requests WHERE approval_request_id IN ({marks})", request_ids)
        cur.execute(
            f"DELETE FROM audit_events WHERE actor_employee_id IN ({placeholders})",
            ids,
        )
        cur.execute(
            f"DELETE FROM change_activity WHERE actor_employee_id IN ({placeholders})",
            ids,
        )
        cur.execute(
            "DELETE FROM change_records WHERE requested_by=%s",
            (requester,),
        )
        cur.execute(
            "DELETE FROM employee_role_assignments WHERE employee_id=%s",
            (requester,),
        )
        cur.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
        cur.execute("DELETE FROM application_roles WHERE role_id=%s", (role_id,))
        cur.execute(f"DELETE FROM employees WHERE employee_id IN ({placeholders})", ids)
        cur.execute("DELETE FROM departments WHERE department_id=%s", (department_id,))
        cleanup.commit()
    except Exception:
        cleanup.rollback()
        raise
    finally:
        cur.close()
        cleanup.close()


def _db():
    from itoms.db.connection import get_connection
    return get_connection()


def _create_request(data, approvers=None, *, resource_type="test", resource_id=None):
    from itoms.services.approvals import create_approval

    return create_approval(
        actor_employee_id=data["requester"],
        request_type="TEST",
        resource_type=resource_type,
        resource_id=resource_id or data["suffix"],
        approver_employee_ids=approvers or [data["approver_one"], data["approver_two"]],
        reason="MySQL integration transaction test",
    )


def test_create_approval_persists_ordered_steps_history_and_audit(approval_fixture):
    data = approval_fixture
    request_id = _create_request(data)
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT status,current_step FROM approval_requests WHERE approval_request_id=%s",
            (request_id,),
        )
        assert cursor.fetchone() == ("PENDING", 1)
        cursor.execute(
            """SELECT step_number,approver_employee_id,decision
               FROM approval_steps WHERE approval_request_id=%s ORDER BY step_number""",
            (request_id,),
        )
        assert cursor.fetchall() == [
            (1, data["approver_one"], "PENDING"),
            (2, data["approver_two"], "PENDING"),
        ]
        cursor.execute(
            "SELECT action_key FROM approval_history WHERE approval_request_id=%s",
            (request_id,),
        )
        assert cursor.fetchall() == [("SUBMITTED",)]
        cursor.execute(
            """SELECT event_key,outcome FROM audit_events
               WHERE target_type='approval' AND target_id=%s""",
            (str(request_id),),
        )
        assert cursor.fetchall() == [("APPROVAL_SUBMITTED", "SUCCESS")]
    finally:
        cursor.close()
        connection.close()


def test_rejection_skips_remaining_steps_and_updates_linked_change_atomically(approval_fixture):
    from itoms.services.approvals import decide_approval

    data = approval_fixture
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO change_records
               (change_number,title,description,requested_by,status)
               VALUES (%s,'Integration change','Test change',%s,'SUBMITTED')""",
            (f"CHG-IT-{data['suffix']}", data["requester"]),
        )
        change_id = int(cursor.lastrowid)
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    request_id = _create_request(
        data,
        resource_type="change",
        resource_id=str(change_id),
    )
    decide_approval(
        actor_employee_id=data["approver_one"],
        request_id=request_id,
        decision="REJECTED",
        comment="Integration rejection",
    )

    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT status FROM approval_requests WHERE approval_request_id=%s", (request_id,))
        assert cursor.fetchone() == ("REJECTED",)
        cursor.execute(
            "SELECT decision FROM approval_steps WHERE approval_request_id=%s ORDER BY step_number",
            (request_id,),
        )
        assert cursor.fetchall() == [("REJECTED",), ("SKIPPED",)]
        cursor.execute("SELECT status FROM change_records WHERE change_id=%s", (change_id,))
        assert cursor.fetchone() == ("REJECTED",)
        cursor.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event_key='CHANGE_APPROVAL_REJECTED' AND target_id=%s""",
            (str(change_id),),
        )
        assert cursor.fetchone()[0] == 1
    finally:
        cursor.close()
        connection.close()


def test_requester_cancellation_resets_submitted_change_and_skips_steps(approval_fixture):
    from itoms.services.approvals import cancel_approval

    data = approval_fixture
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO change_records
               (change_number,title,description,requested_by,status)
               VALUES (%s,'Integration cancel','Test change',%s,'SUBMITTED')""",
            (f"CHG-CANCEL-{data['suffix']}", data["requester"]),
        )
        change_id = int(cursor.lastrowid)
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    request_id = _create_request(data, resource_type="change", resource_id=str(change_id))
    cancel_approval(actor_employee_id=data["requester"], request_id=request_id)

    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT status FROM approval_requests WHERE approval_request_id=%s", (request_id,))
        assert cursor.fetchone() == ("CANCELLED",)
        cursor.execute(
            "SELECT decision FROM approval_steps WHERE approval_request_id=%s",
            (request_id,),
        )
        assert cursor.fetchall() == [("SKIPPED",), ("SKIPPED",)]
        cursor.execute("SELECT status FROM change_records WHERE change_id=%s", (change_id,))
        assert cursor.fetchone() == ("DRAFT",)
    finally:
        cursor.close()
        connection.close()


def test_failed_history_insert_rolls_back_entire_approval_submission(approval_fixture):
    from itoms.services.approvals import create_approval

    data = approval_fixture
    trigger_name = f"itoms_it_{data['suffix']}"
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            f"""CREATE TRIGGER `{trigger_name}` BEFORE INSERT ON approval_history
                FOR EACH ROW SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT='integration rollback injection'"""
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    try:
        with pytest.raises(mysql.connector.Error, match="integration rollback injection"):
            create_approval(
                actor_employee_id=data["requester"],
                request_type="TEST",
                resource_type="test",
                resource_id=data["suffix"],
                approver_employee_ids=[data["approver_one"]],
            )
    finally:
        connection = _db()
        cursor = connection.cursor()
        try:
            cursor.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`")
            connection.commit()
        finally:
            cursor.close()
            connection.close()

    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM approval_requests WHERE requested_by=%s AND resource_id=%s",
            (data["requester"], data["suffix"]),
        )
        assert cursor.fetchone()[0] == 0
    finally:
        cursor.close()
        connection.close()


def test_concurrent_duplicate_decision_commits_only_once(approval_fixture):
    from itoms.services.approvals import ApprovalError, decide_approval

    data = approval_fixture
    request_id = _create_request(data, approvers=[data["approver_one"]])
    barrier = threading.Barrier(2)

    def decide():
        barrier.wait(timeout=10)
        try:
            decide_approval(
                actor_employee_id=data["approver_one"],
                request_id=request_id,
                decision="APPROVED",
                comment="Concurrent integration decision",
            )
            return "committed"
        except ApprovalError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: decide(), range(2)))

    assert sorted(outcomes) == ["committed", "rejected"]
    connection = _db()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT status FROM approval_requests WHERE approval_request_id=%s", (request_id,))
        assert cursor.fetchone() == ("APPROVED",)
        cursor.execute(
            """SELECT COUNT(*) FROM approval_history
               WHERE approval_request_id=%s AND action_key='APPROVED'""",
            (request_id,),
        )
        assert cursor.fetchone()[0] == 1
    finally:
        cursor.close()
        connection.close()
