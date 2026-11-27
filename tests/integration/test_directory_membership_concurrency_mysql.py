"""MySQL concurrency tests for employee team-membership lock ordering."""
from __future__ import annotations

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def membership_fixture():
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
    app_context = app.app_context()
    app_context.push()
    suffix = uuid.uuid4().hex[:12]
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO departments (department_name) VALUES (%s)",
            (f"Membership Concurrency {suffix}",),
        )
        department_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"MEM-{suffix}", "Membership concurrency test", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Membership Team A {suffix}"),
        )
        team_a = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Membership Team B {suffix}"),
        )
        team_b = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employee_team_memberships (employee_id,team_id,is_primary)
               VALUES (%s,%s,FALSE)""",
            (employee_id, team_a),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    yield {
        "app": app,
        "department_id": department_id,
        "employee_id": employee_id,
        "team_a": team_a,
        "team_b": team_b,
    }

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute(
            "DELETE FROM employee_team_memberships WHERE employee_id=%s",
            (employee_id,),
        )
        cursor.execute("DELETE FROM employees WHERE employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM teams WHERE team_id IN (%s,%s)", (team_a, team_b))
        cursor.execute("DELETE FROM departments WHERE department_id=%s", (department_id,))
        cleanup.commit()
    except Exception:
        cleanup.rollback()
        raise
    finally:
        cursor.close()
        cleanup.close()
        app_context.pop()


def test_concurrent_primary_assignment_and_membership_removal_serialize(membership_fixture):
    from itoms.services.directory import assign_employee_to_team, remove_employee_from_team

    data = membership_fixture
    barrier = threading.Barrier(2)

    def assign_primary():
        with data["app"].app_context():
            barrier.wait(timeout=10)
            assign_employee_to_team(data["employee_id"], data["team_b"], primary=True)

    def remove_old_membership():
        with data["app"].app_context():
            barrier.wait(timeout=10)
            remove_employee_from_team(data["employee_id"], data["team_a"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        assign_future = pool.submit(assign_primary)
        remove_future = pool.submit(remove_old_membership)
        assign_future.result(timeout=20)
        remove_future.result(timeout=20)

    from itoms.db.connection import get_connection

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """SELECT team_id,is_primary FROM employee_team_memberships
               WHERE employee_id=%s ORDER BY team_id""",
            (data["employee_id"],),
        )
        assert cursor.fetchall() == [(data["team_b"], 1)]
    finally:
        cursor.close()
        connection.close()
