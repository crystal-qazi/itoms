"""MySQL integration coverage for Change and Release Management gates.

Run against the dedicated migrated MySQL database with
ITOMS_RUN_MYSQL_INTEGRATION=1.
"""
from __future__ import annotations

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def workflow_fixture():
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
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO departments (department_name) VALUES (%s)",
            (f"Workflow Integration {suffix}",),
        )
        department_id = int(cur.lastrowid)
        employee_ids = []
        for label in ("requester", "approver_one", "approver_two", "outsider"):
            cur.execute(
                """INSERT INTO employees
                   (employee_code,full_name,department_id,is_active)
                   VALUES (%s,%s,%s,TRUE)""",
                (f"WF-{suffix}-{label}", f"Workflow {label}", department_id),
            )
            employee_ids.append(int(cur.lastrowid))
        requester, approver_one, approver_two, outsider = employee_ids

        cur.execute(
            "INSERT INTO departments (department_name) VALUES (%s)",
            (f"Other Workflow Integration {suffix}",),
        )
        other_department_id = int(cur.lastrowid)
        cur.execute(
            """UPDATE employees SET department_id=%s WHERE employee_id=%s""",
            (other_department_id, outsider),
        )

        cur.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Workflow Integration {suffix}", "Temporary MySQL workflow test role"),
        )
        role_id = int(cur.lastrowid)
        permissions = (
            "change.create", "change.read", "change.update",
            "release.create", "release.read", "release.update",
            "approvals.create", "sqa.signoff.create",
        )
        for permission_key in permissions:
            cur.execute(
                "SELECT permission_id FROM permissions WHERE permission_key=%s",
                (permission_key,),
            )
            permission = cur.fetchone()
            assert permission, f"permission migration missing: {permission_key}"
            cur.execute(
                "INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)",
                (role_id, permission[0]),
            )
        cur.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'DEPARTMENT',TRUE)""",
            (requester, role_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    data = {
        "app": app,
        "suffix": suffix,
        "department_id": department_id,
        "other_department_id": other_department_id,
        "requester": requester,
        "approver_one": approver_one,
        "approver_two": approver_two,
        "outsider": outsider,
        "role_id": role_id,
    }
    yield data

    cleanup = get_connection()
    cur = cleanup.cursor()
    try:
        cur.execute(
            "SELECT release_id,release_key FROM software_releases WHERE created_by=%s",
            (requester,),
        )
        releases = cur.fetchall()
        release_ids = [int(row[0]) for row in releases]
        release_keys = [row[1] for row in releases]
        if release_keys:
            marks = ",".join(["%s"] * len(release_keys))
            cur.execute(
                f"DELETE FROM sqa_release_signoffs WHERE release_key IN ({marks})",
                release_keys,
            )
            cur.execute(
                f"SELECT test_plan_id FROM sqa_test_plans WHERE release_key IN ({marks})",
                release_keys,
            )
            plan_ids = [int(row[0]) for row in cur.fetchall()]
            if plan_ids:
                pmarks = ",".join(["%s"] * len(plan_ids))
                cur.execute(
                    f"""DELETE d FROM sqa_defects d
                        JOIN sqa_test_executions x ON x.execution_id=d.execution_id
                        JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
                        WHERE c.test_plan_id IN ({pmarks})""",
                    plan_ids,
                )
                cur.execute(
                    f"""DELETE x FROM sqa_test_executions x
                        JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
                        WHERE c.test_plan_id IN ({pmarks})""",
                    plan_ids,
                )
                cur.execute(
                    f"DELETE FROM sqa_test_cases WHERE test_plan_id IN ({pmarks})",
                    plan_ids,
                )
                cur.execute(
                    f"DELETE FROM sqa_test_plans WHERE test_plan_id IN ({pmarks})",
                    plan_ids,
                )
        if release_ids:
            marks = ",".join(["%s"] * len(release_ids))
            cur.execute(
                f"SELECT approval_request_id FROM approval_requests WHERE resource_type='release' AND resource_id IN ({marks})",
                [str(value) for value in release_ids],
            )
            approval_ids = [int(row[0]) for row in cur.fetchall()]
            if approval_ids:
                amarks = ",".join(["%s"] * len(approval_ids))
                cur.execute(f"DELETE FROM approval_history WHERE approval_request_id IN ({amarks})", approval_ids)
                cur.execute(f"DELETE FROM approval_steps WHERE approval_request_id IN ({amarks})", approval_ids)
                cur.execute(f"DELETE FROM approval_requests WHERE approval_request_id IN ({amarks})", approval_ids)
            cur.execute(f"DELETE FROM release_change_links WHERE release_id IN ({marks})", release_ids)
            cur.execute(f"DELETE FROM software_releases WHERE release_id IN ({marks})", release_ids)

        cur.execute(
            "SELECT change_id FROM change_records WHERE requested_by=%s",
            (requester,),
        )
        change_ids = [int(row[0]) for row in cur.fetchall()]
        if change_ids:
            marks = ",".join(["%s"] * len(change_ids))
            cur.execute(
                f"SELECT approval_request_id FROM approval_requests WHERE resource_type='change' AND resource_id IN ({marks})",
                [str(value) for value in change_ids],
            )
            approval_ids = [int(row[0]) for row in cur.fetchall()]
            if approval_ids:
                amarks = ",".join(["%s"] * len(approval_ids))
                cur.execute(f"DELETE FROM approval_history WHERE approval_request_id IN ({amarks})", approval_ids)
                cur.execute(f"DELETE FROM approval_steps WHERE approval_request_id IN ({amarks})", approval_ids)
                cur.execute(f"DELETE FROM approval_requests WHERE approval_request_id IN ({amarks})", approval_ids)
            cur.execute(f"DELETE FROM change_activity WHERE change_id IN ({marks})", change_ids)
            cur.execute(f"DELETE FROM change_records WHERE change_id IN ({marks})", change_ids)

        ids = (requester, approver_one, approver_two, outsider)
        marks = ",".join(["%s"] * len(ids))
        cur.execute(
            f"DELETE FROM audit_events WHERE actor_employee_id IN ({marks})",
            ids,
        )
        cur.execute("DELETE FROM employee_role_assignments WHERE employee_id=%s", (requester,))
        cur.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
        cur.execute("DELETE FROM application_roles WHERE role_id=%s", (role_id,))
        cur.execute(f"DELETE FROM employees WHERE employee_id IN ({marks})", ids)
        cur.execute(
            "DELETE FROM departments WHERE department_id IN (%s,%s)",
            (department_id, other_department_id),
        )
        cleanup.commit()
    except Exception:
        cleanup.rollback()
        raise
    finally:
        cur.close()
        cleanup.close()
        app_context.pop()


def _db():
    from itoms.db.connection import get_connection
    return get_connection()


def _create_change(data):
    from itoms.services.change_management import create_change

    return create_change(
        actor_employee_id=data["requester"],
        title="Integration change",
        description="Real MySQL change workflow test",
        change_type="NORMAL",
        risk_level="MEDIUM",
        planned_start=None,
        planned_end=None,
        implementation_plan="Implement safely",
        rollback_plan="Restore previous version",
        verification_plan="Verify service health",
    )


def _create_release(data):
    from itoms.services.release_management import create_release

    return create_release(
        actor_employee_id=data["requester"],
        release_key=f"REL-IT-{data['suffix']}",
        version_label="1.0.0",
        release_notes="Integration release gate test",
        service_id=None,
        target_at=None,
        change_id=None,
    )


def test_change_scope_denies_another_department(workflow_fixture):
    from itoms.services.change_management import ChangeError, get_change

    data = workflow_fixture
    change_id = _create_change(data)
    with pytest.raises(ChangeError, match="not found"):
        get_change(actor_employee_id=data["outsider"], change_id=change_id)


def test_change_approval_blocks_schedule_until_approved(workflow_fixture):
    from itoms.services.approvals import decide_approval
    from itoms.services.change_management import ChangeError, transition_change

    data = workflow_fixture
    change_id = _create_change(data)
    transition_change(
        actor_employee_id=data["requester"],
        change_id=change_id,
        new_status="SUBMITTED",
        details="Submit for controlled approval",
        approver_employee_ids=[data["approver_one"], data["approver_two"]],
    )
    with pytest.raises(ChangeError, match="fully approved"):
        transition_change(
            actor_employee_id=data["requester"],
            change_id=change_id,
            new_status="SCHEDULED",
        )

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT approval_request_id FROM approval_requests
               WHERE resource_type='change' AND resource_id=%s
               ORDER BY approval_request_id DESC LIMIT 1""",
            (str(change_id),),
        )
        approval_id = int(cur.fetchone()[0])
    finally:
        cur.close()
        conn.close()

    decide_approval(
        actor_employee_id=data["approver_one"],
        request_id=approval_id,
        decision="APPROVED",
        comment="First approval",
    )
    decide_approval(
        actor_employee_id=data["approver_two"],
        request_id=approval_id,
        decision="APPROVED",
        comment="Final approval",
    )
    transition_change(
        actor_employee_id=data["requester"],
        change_id=change_id,
        new_status="SCHEDULED",
    )

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM change_records WHERE change_id=%s", (change_id,))
        assert cur.fetchone() == ("SCHEDULED",)
    finally:
        cur.close()
        conn.close()


def test_rejected_change_can_be_resubmitted_with_new_approval(workflow_fixture):
    from itoms.services.approvals import decide_approval
    from itoms.services.change_management import transition_change

    data = workflow_fixture
    change_id = _create_change(data)
    transition_change(
        actor_employee_id=data["requester"], change_id=change_id,
        new_status="SUBMITTED", details="Initial submission",
        approver_employee_ids=[data["approver_one"]],
    )
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT approval_request_id FROM approval_requests
               WHERE resource_type='change' AND resource_id=%s
               ORDER BY approval_request_id DESC LIMIT 1""",
            (str(change_id),),
        )
        first_approval = int(cur.fetchone()[0])
    finally:
        cur.close()
        conn.close()
    decide_approval(
        actor_employee_id=data["approver_one"], request_id=first_approval,
        decision="REJECTED", comment="Needs a safer rollback plan",
    )
    transition_change(
        actor_employee_id=data["requester"], change_id=change_id,
        new_status="SUBMITTED", details="Revised submission",
        approver_employee_ids=[data["approver_two"]],
    )
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM change_records WHERE change_id=%s", (change_id,))
        assert cur.fetchone() == ("SUBMITTED",)
        cur.execute(
            """SELECT status FROM approval_requests
               WHERE resource_type='change' AND resource_id=%s
               ORDER BY approval_request_id""",
            (str(change_id),),
        )
        assert cur.fetchall() == [("REJECTED",), ("PENDING",)]
    finally:
        cur.close()
        conn.close()


def test_release_requires_approval_and_sqa_and_rechecks_before_deployment(workflow_fixture):
    from itoms.services.approvals import decide_approval
    from itoms.services.release_management import ReleaseError, transition_release
    from itoms.services.sqa import record_release_signoff

    data = workflow_fixture
    release_id = _create_release(data)
    transition_release(actor_employee_id=data["requester"], release_id=release_id, new_status="IN_TEST")
    transition_release(actor_employee_id=data["requester"], release_id=release_id, new_status="READY")

    with pytest.raises(ReleaseError, match="approval workflow"):
        transition_release(actor_employee_id=data["requester"], release_id=release_id, new_status="APPROVED")

    transition_release(
        actor_employee_id=data["requester"], release_id=release_id,
        new_status="REQUEST_APPROVAL",
        approver_employee_ids=[data["approver_one"]],
        approval_reason="Approve validated release",
    )
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT approval_request_id FROM approval_requests
               WHERE resource_type='release' AND resource_id=%s
               ORDER BY approval_request_id DESC LIMIT 1""",
            (str(release_id),),
        )
        approval_id = int(cur.fetchone()[0])
        cur.execute("SELECT release_key FROM software_releases WHERE release_id=%s", (release_id,))
        release_key = cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()

    decide_approval(
        actor_employee_id=data["approver_one"], request_id=approval_id,
        decision="APPROVED", comment="Approved",
    )
    with pytest.raises(ReleaseError, match="SQA gate"):
        transition_release(actor_employee_id=data["requester"], release_id=release_id, new_status="APPROVED")

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO sqa_test_plans
               (plan_key,release_key,title,created_by,status)
               VALUES (%s,%s,%s,%s,'COMPLETED')""",
            (f"SQA-{data['suffix']}", release_key, "Completed release test", data["requester"]),
        )
        plan_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO sqa_test_cases
               (test_plan_id,case_key,title,steps,expected_result)
               VALUES (%s,'CASE-1','Release smoke test','Run smoke test','Service is healthy')""",
            (plan_id,),
        )
        case_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO sqa_test_executions
               (test_case_id,executed_by,result,actual_result,executed_at)
               VALUES (%s,%s,'PASS','Service is healthy',UTC_TIMESTAMP())""",
            (case_id, data["requester"]),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    record_release_signoff(
        actor_employee_id=data["requester"], release_key=release_key,
        decision="APPROVED", comments="SQA checks passed",
    )
    transition_release(actor_employee_id=data["requester"], release_id=release_id, new_status="APPROVED")

    # A later failing execution invalidates the previously completed SQA evidence.
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO sqa_test_executions
               (test_case_id,executed_by,result,actual_result,executed_at)
               VALUES (%s,%s,'FAIL','Regression detected',DATE_ADD(UTC_TIMESTAMP(), INTERVAL 1 SECOND))""",
            (case_id, data["requester"]),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    with pytest.raises(ReleaseError, match="latest PASS"):
        transition_release(actor_employee_id=data["requester"], release_id=release_id, new_status="DEPLOYING")
