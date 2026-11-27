"""MySQL integration coverage for training and vendor support directory."""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def people_ops_fixture():
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
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"People Ops Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO employees (employee_code,full_name,department_id,is_active) VALUES (%s,%s,%s,TRUE)",
            (f"PEO-{suffix}", f"People Ops Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"People Ops Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        keys = ("vendor.directory.read", "vendor.directory.manage", "training.course.read",
                "training.course.manage", "training.enroll", "training.read", "training.manage")
        for key in keys:
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

    data = {"employee_id": employee_id, "department_id": department_id, "role_id": role_id, "suffix": suffix}
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute("SELECT course_id FROM training_courses WHERE course_title=%s", (f"Safety Course {suffix}",))
        course = cursor.fetchone()
        if course:
            cursor.execute("DELETE FROM training_enrollments WHERE course_id=%s", (course[0],))
            cursor.execute("DELETE FROM training_courses WHERE course_id=%s", (course[0],))
        cursor.execute("DELETE FROM vendor_directory WHERE vendor_name=%s", (f"Vendor {suffix}",))
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


def test_vendor_and_training_course_enrollment_lifecycle(people_ops_fixture):
    from itoms.services.training import (
        create_course, enroll_employee, list_courses, list_enrollments,
        update_enrollment_status,
    )
    from itoms.services.vendors import create_vendor, list_vendors, set_vendor_active
    from itoms.db.connection import get_connection

    data = people_ops_fixture
    vendor_id = create_vendor(
        actor_employee_id=data["employee_id"], vendor_name=f"Vendor {data['suffix']}",
        service_description="Hardware support contact",
        support_email="support@example.com", support_phone="+1-555-0100",
        support_portal_url="https://support.example.com",
    )
    assert any(item["vendor_id"] == vendor_id for item in list_vendors(actor_employee_id=data["employee_id"]))
    set_vendor_active(actor_employee_id=data["employee_id"], vendor_id=vendor_id, is_active=False)

    course_id = create_course(
        actor_employee_id=data["employee_id"], course_title=f"Safety Course {data['suffix']}",
        description="Annual safety awareness course.",
    )
    assert any(item["course_id"] == course_id for item in list_courses(actor_employee_id=data["employee_id"]))
    enrollment_id = enroll_employee(
        actor_employee_id=data["employee_id"], course_id=course_id,
    )
    assert any(item["enrollment_id"] == enrollment_id for item in list_enrollments(
        actor_employee_id=data["employee_id"], course_id=course_id
    ))
    update_enrollment_status(
        actor_employee_id=data["employee_id"], enrollment_id=enrollment_id,
        new_status="IN_PROGRESS",
    )
    update_enrollment_status(
        actor_employee_id=data["employee_id"], enrollment_id=enrollment_id,
        new_status="COMPLETED",
    )
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT is_active FROM vendor_directory WHERE vendor_id=%s", (vendor_id,))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT status FROM training_enrollments WHERE enrollment_id=%s", (enrollment_id,))
        assert cursor.fetchone()[0] == "COMPLETED"
        cursor.execute(
            "SELECT event_key FROM audit_events WHERE target_type='training_enrollment' AND target_id=%s",
            (str(enrollment_id),),
        )
        events = [row[0] for row in cursor.fetchall()]
        assert events.count("TRAINING_EMPLOYEE_ENROLLED") == 1
        assert events.count("TRAINING_ENROLLMENT_STATUS_CHANGED") == 2
    finally:
        cursor.close()
        connection.close()
