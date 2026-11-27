"""MySQL integration coverage for Change and Release Management gates.

Run against the dedicated migrated MySQL database with
ITOMS_RUN_MYSQL_INTEGRATION=1.
"""
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
            "service.inventory.read", "service.inventory.create", "service.inventory.update",
            "engineering.tasks.read", "engineering.tasks.create", "engineering.tasks.update",
            "incident.create", "incident.read", "incident.update", "incident.assign",
            "incident.comment", "incident.comment.internal",
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
        cur.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Workflow Team A {suffix}"),
        )
        team_a = int(cur.lastrowid)
        cur.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (department_id, f"Workflow Team B {suffix}"),
        )
        team_b = int(cur.lastrowid)
        cur.execute(
            "INSERT INTO employee_team_memberships (employee_id,team_id,is_primary) VALUES (%s,%s,TRUE)",
            (approver_one, team_a),
        )
        cur.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'TEAM',TRUE)""",
            (approver_one, role_id),
        )
        cur.execute(
            "INSERT INTO team_management_assignments (manager_employee_id,team_id) VALUES (%s,%s)",
            (approver_two, team_a),
        )
        cur.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active)
               VALUES (%s,%s,'MANAGED_TEAMS',TRUE)""",
            (approver_two, role_id),
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
        "team_a": team_a,
        "team_b": team_b,
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

        cur.execute("SELECT task_id FROM engineering_tasks WHERE created_by=%s", (requester,))
        task_ids = [int(row[0]) for row in cur.fetchall()]
        if task_ids:
            task_marks = ",".join(["%s"] * len(task_ids))
            cur.execute(f"DELETE FROM engineering_task_activity WHERE task_id IN ({task_marks})", task_ids)
            cur.execute(f"DELETE FROM engineering_tasks WHERE task_id IN ({task_marks})", task_ids)

        ids = (requester, approver_one, approver_two, outsider)
        marks = ",".join(["%s"] * len(ids))
        cur.execute(
            f"DELETE FROM audit_events WHERE actor_employee_id IN ({marks})",
            ids,
        )
        cur.execute("SELECT ticket_id FROM incident_tickets WHERE requester_employee_id=%s", (requester,))
        incident_ids = [int(row[0]) for row in cur.fetchall()]
        if incident_ids:
            incident_marks = ",".join(["%s"] * len(incident_ids))
            cur.execute(f"DELETE FROM incident_comments WHERE ticket_id IN ({incident_marks})", incident_ids)
            cur.execute(f"DELETE FROM incident_activity WHERE ticket_id IN ({incident_marks})", incident_ids)
            cur.execute(f"DELETE FROM incident_tickets WHERE ticket_id IN ({incident_marks})", incident_ids)
        cur.execute("SELECT test_plan_id FROM sqa_test_plans WHERE created_by=%s", (requester,))
        sqa_plan_ids = [int(row[0]) for row in cur.fetchall()]
        if sqa_plan_ids:
            sqa_marks = ",".join(["%s"] * len(sqa_plan_ids))
            cur.execute(f"""DELETE d FROM sqa_defects d
                JOIN sqa_test_executions x ON x.execution_id=d.execution_id
                JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
                WHERE c.test_plan_id IN ({sqa_marks})""", sqa_plan_ids)
            cur.execute(f"""DELETE x FROM sqa_test_executions x
                JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
                WHERE c.test_plan_id IN ({sqa_marks})""", sqa_plan_ids)
            cur.execute(f"DELETE FROM sqa_test_cases WHERE test_plan_id IN ({sqa_marks})", sqa_plan_ids)
            cur.execute(f"DELETE FROM sqa_test_plans WHERE test_plan_id IN ({sqa_marks})", sqa_plan_ids)
        cur.execute("DELETE FROM service_records WHERE service_key LIKE %s", (f"SVC-IT-{suffix}-%",))
        cur.execute(f"DELETE FROM employee_role_assignments WHERE employee_id IN ({marks})", ids)
        cur.execute(f"DELETE FROM employee_team_memberships WHERE employee_id IN ({marks})", ids)
        cur.execute(f"DELETE FROM team_management_assignments WHERE manager_employee_id IN ({marks})", ids)
        cur.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
        cur.execute("DELETE FROM teams WHERE team_id IN (%s,%s)", (team_a, team_b))
        cur.execute(
            "DELETE FROM teams WHERE department_id=%s AND team_name LIKE %s",
            (other_department_id, f"Other % {suffix}"),
        )
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


def test_team_scope_requires_active_membership_in_target_team(workflow_fixture):
    from itoms.services.authorization import ResourceContext, has_permission

    data = workflow_fixture
    assert has_permission(
        data["approver_one"], "change.read",
        ResourceContext(team_id=data["team_a"], department_id=data["department_id"]),
    ) is True
    assert has_permission(
        data["approver_one"], "change.read",
        ResourceContext(team_id=data["team_b"], department_id=data["department_id"]),
    ) is False


def test_managed_team_scope_requires_active_managed_team(workflow_fixture):
    from itoms.services.authorization import ResourceContext, has_permission

    data = workflow_fixture
    context = ResourceContext(team_id=data["team_a"], department_id=data["department_id"])
    assert has_permission(data["approver_two"], "change.read", context) is True

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE teams SET is_active=FALSE WHERE team_id=%s", (data["team_a"],))
        conn.commit()
    finally:
        cur.close()
        conn.close()

    assert has_permission(data["approver_two"], "change.read", context) is False



def test_concurrent_change_transitions_commit_once(workflow_fixture):
    from itoms.services.change_management import ChangeError, transition_change

    data = workflow_fixture
    change_id = _create_change(data)
    barrier = threading.Barrier(2)

    def submit():
        with data["app"].app_context():
            barrier.wait(timeout=10)
            try:
                transition_change(
                    actor_employee_id=data["requester"],
                    change_id=change_id,
                    new_status="SUBMITTED",
                    details="Concurrent submission",
                    approver_employee_ids=[data["approver_one"]],
                )
                return "committed"
            except ChangeError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: submit(), range(2)))

    assert sorted(outcomes) == ["committed", "rejected"]
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM change_records WHERE change_id=%s", (change_id,))
        assert cur.fetchone() == ("SUBMITTED",)
        cur.execute(
            "SELECT COUNT(*) FROM approval_requests WHERE resource_type='change' AND resource_id=%s",
            (str(change_id),),
        )
        assert cur.fetchone()[0] == 1
        cur.execute(
            """SELECT COUNT(*) FROM change_activity
               WHERE change_id=%s AND action_key='STATUS_SUBMITTED'""",
            (change_id,),
        )
        assert cur.fetchone()[0] == 1
        cur.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event_key='CHANGE_STATUS_CHANGED' AND target_id=%s""",
            (str(change_id),),
        )
        assert cur.fetchone()[0] == 1
    finally:
        cur.close()
        conn.close()


def test_concurrent_release_transitions_commit_once(workflow_fixture):
    from itoms.services.release_management import ReleaseError, transition_release

    data = workflow_fixture
    release_id = _create_release(data)
    barrier = threading.Barrier(2)

    def transition(status):
        with data["app"].app_context():
            barrier.wait(timeout=10)
            try:
                transition_release(
                    actor_employee_id=data["requester"],
                    release_id=release_id,
                    new_status=status,
                )
                return status
            except ReleaseError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(transition, ("IN_TEST", "CANCELLED")))

    committed = [value for value in outcomes if value != "rejected"]
    assert len(committed) == 1
    final_status = committed[0]
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM software_releases WHERE release_id=%s", (release_id,))
        assert cur.fetchone() == (final_status,)
        cur.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event_key='RELEASE_STATUS_CHANGED' AND target_id=%s""",
            (str(release_id),),
        )
        assert cur.fetchone()[0] == 1
    finally:
        cur.close()
        conn.close()


def test_change_transition_rolls_back_when_audit_insert_fails(workflow_fixture):
    from itoms.services.change_management import transition_change

    data = workflow_fixture
    change_id = _create_change(data)
    trigger_name = f"itoms_chg_rb_{data['suffix']}"
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""CREATE TRIGGER `{trigger_name}` BEFORE INSERT ON audit_events
                FOR EACH ROW SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT='change transition rollback injection'"""
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    try:
        with pytest.raises(Exception, match="change transition rollback injection"):
            transition_change(
                actor_employee_id=data["requester"],
                change_id=change_id,
                new_status="CANCELLED",
                details="Rollback test",
            )
    finally:
        conn = _db()
        cur = conn.cursor()
        try:
            cur.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`")
            conn.commit()
        finally:
            cur.close()
            conn.close()

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM change_records WHERE change_id=%s", (change_id,))
        assert cur.fetchone() == ("DRAFT",)
        cur.execute(
            """SELECT COUNT(*) FROM change_activity
               WHERE change_id=%s AND action_key='STATUS_CANCELLED'""",
            (change_id,),
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event_key='CHANGE_STATUS_CHANGED' AND target_id=%s""",
            (str(change_id),),
        )
        assert cur.fetchone()[0] == 0
    finally:
        cur.close()
        conn.close()


def test_release_transition_rolls_back_when_audit_insert_fails(workflow_fixture):
    from itoms.services.release_management import transition_release

    data = workflow_fixture
    release_id = _create_release(data)
    trigger_name = f"itoms_rel_rb_{data['suffix']}"
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""CREATE TRIGGER `{trigger_name}` BEFORE INSERT ON audit_events
                FOR EACH ROW SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT='release transition rollback injection'"""
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    try:
        with pytest.raises(Exception, match="release transition rollback injection"):
            transition_release(
                actor_employee_id=data["requester"],
                release_id=release_id,
                new_status="CANCELLED",
            )
    finally:
        conn = _db()
        cur = conn.cursor()
        try:
            cur.execute(f"DROP TRIGGER IF EXISTS `{trigger_name}`")
            conn.commit()
        finally:
            cur.close()
            conn.close()

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM software_releases WHERE release_id=%s", (release_id,))
        assert cur.fetchone() == ("PLANNED",)
        cur.execute(
            """SELECT COUNT(*) FROM audit_events
               WHERE event_key='RELEASE_STATUS_CHANGED' AND target_id=%s""",
            (str(release_id),),
        )
        assert cur.fetchone()[0] == 0
    finally:
        cur.close()
        conn.close()



def test_change_and_release_employee_choices_are_department_scoped(workflow_fixture):
    from itoms.web.changes import _owners
    from itoms.web.releases import _approvers

    data = workflow_fixture
    owner_ids = {row["employee_id"] for row in _owners(data["department_id"])}
    approver_ids = {row["employee_id"] for row in _approvers(data["department_id"])}

    assert data["requester"] in owner_ids
    assert data["approver_one"] in owner_ids
    assert data["outsider"] not in owner_ids
    assert data["requester"] in approver_ids
    assert data["approver_two"] in approver_ids
    assert data["outsider"] not in approver_ids



def test_change_submission_rejects_cross_department_approver(workflow_fixture):
    from itoms.services.change_management import ChangeError, transition_change

    data = workflow_fixture
    change_id = _create_change(data)
    with pytest.raises(ChangeError, match="change department"):
        transition_change(
            actor_employee_id=data["requester"],
            change_id=change_id,
            new_status="SUBMITTED",
            details="Cross-department approver must be rejected",
            approver_employee_ids=[data["outsider"]],
        )
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM change_records WHERE change_id=%s", (change_id,))
        assert cur.fetchone() == ("DRAFT",)
        cur.execute(
            """SELECT COUNT(*) FROM approval_requests
               WHERE resource_type='change' AND resource_id=%s""",
            (str(change_id),),
        )
        assert cur.fetchone()[0] == 0
    finally:
        cur.close()
        conn.close()


def test_release_approval_rejects_cross_department_approver(workflow_fixture):
    from itoms.services.release_management import ReleaseError, transition_release

    data = workflow_fixture
    release_id = _create_release(data)
    transition_release(actor_employee_id=data["requester"], release_id=release_id, new_status="IN_TEST")
    transition_release(actor_employee_id=data["requester"], release_id=release_id, new_status="READY")
    with pytest.raises(ReleaseError, match="release department"):
        transition_release(
            actor_employee_id=data["requester"],
            release_id=release_id,
            new_status="REQUEST_APPROVAL",
            approver_employee_ids=[data["outsider"]],
            approval_reason="Cross-department approver must be rejected",
        )
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM software_releases WHERE release_id=%s", (release_id,))
        assert cur.fetchone() == ("READY",)
        cur.execute(
            """SELECT COUNT(*) FROM approval_requests
               WHERE resource_type='release' AND resource_id=%s""",
            (str(release_id),),
        )
        assert cur.fetchone()[0] == 0
    finally:
        cur.close()
        conn.close()



def test_service_inventory_department_scope_uses_trusted_team_department(workflow_fixture):
    from itoms.services.service_inventory import (
        ServiceInventoryError, create_service_record, list_service_records,
        list_service_teams,
    )

    data = workflow_fixture
    own_id = create_service_record(
        actor_employee_id=data["requester"],
        service_key=f"SVC-IT-{data['suffix']}-OWN",
        service_name="Department-owned service",
        service_type="APPLICATION",
        owner_team_id=data["team_a"],
    )

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO teams (department_id,team_name,is_active)
               VALUES (%s,%s,TRUE)""",
            (data["other_department_id"], f"Other Service Team {data['suffix']}"),
        )
        other_team = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO service_records
               (service_key,service_name,service_type,owner_team_id,criticality)
               VALUES (%s,%s,'APPLICATION',%s,'HIGH')""",
            (f"SVC-IT-{data['suffix']}-OTHER", "Other department confidential service", other_team),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    visible_ids = {row["service_id"] for row in list_service_records(actor_employee_id=data["requester"])}
    assert own_id in visible_ids
    assert all(row["service_name"] != "Other department confidential service"
               for row in list_service_records(actor_employee_id=data["requester"]))
    visible_team_ids = {row["team_id"] for row in list_service_teams(actor_employee_id=data["requester"])}
    assert data["team_a"] in visible_team_ids
    assert other_team not in visible_team_ids

    with pytest.raises(ServiceInventoryError, match="Not authorized"):
        create_service_record(
            actor_employee_id=data["requester"],
            service_key=f"SVC-IT-{data['suffix']}-DENIED",
            service_name="Must not be created",
            service_type="APPLICATION",
            owner_team_id=other_team,
        )


def test_service_inventory_lifecycle_update_rechecks_scope(workflow_fixture):
    from itoms.services.service_inventory import create_service_record, update_service_lifecycle

    data = workflow_fixture
    service_id = create_service_record(
        actor_employee_id=data["requester"],
        service_key=f"SVC-IT-{data['suffix']}-LIFE",
        service_name="Lifecycle test service",
        service_type="DATABASE",
        owner_team_id=data["team_a"],
    )
    update_service_lifecycle(
        actor_employee_id=data["requester"],
        service_id=service_id,
        lifecycle_status="ACTIVE",
    )
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT lifecycle_status FROM service_records WHERE service_id=%s", (service_id,))
        assert cur.fetchone() == ("ACTIVE",)
    finally:
        cur.close()
        conn.close()



def test_incident_department_scope_covers_queue_detail_comments_and_assignment(workflow_fixture):
    from itoms.services.incidents import (
        IncidentError, add_comment, assign_incident, create_incident,
        get_incident_detail, list_accessible_incident_teams,
        list_assignable_teams, list_incidents, transition_incident,
    )

    data = workflow_fixture
    ticket_id = create_incident(
        actor_employee_id=data["requester"],
        requester_employee_id=data["requester"],
        assigned_team_id=data["team_a"],
        title="Department-scoped incident",
        description="Validate department authorization through all incident operations.",
    )

    assert any(row["ticket_id"] == ticket_id
               for row in list_incidents(actor_employee_id=data["requester"]))
    assert get_incident_detail(actor_employee_id=data["requester"], ticket_id=ticket_id)["ticket_id"] == ticket_id
    visible_team_ids = {row["team_id"] for row in list_accessible_incident_teams(
        actor_employee_id=data["requester"])}
    assert data["team_a"] in visible_team_ids
    assert data["team_b"] in visible_team_ids
    with pytest.raises(IncidentError, match="Not authorized"):
        list_assignable_teams(actor_employee_id=data["outsider"], ticket_id=ticket_id)

    unassigned_ticket = create_incident(
        actor_employee_id=data["requester"],
        requester_employee_id=data["requester"],
        title="Unassigned incident scope test",
        description="Team-only permission must not assign another employee's unassigned incident.",
    )
    with pytest.raises(IncidentError, match="Not authorized"):
        assign_incident(
            actor_employee_id=data["approver_one"],
            ticket_id=unassigned_ticket,
            assigned_team_id=data["team_a"],
        )

    add_comment(actor_employee_id=data["requester"], ticket_id=ticket_id,
                body="Internal department note", internal=True)
    detail = get_incident_detail(actor_employee_id=data["requester"], ticket_id=ticket_id)
    assert any(item["is_internal"] for item in detail["comments"])

    transition_incident(actor_employee_id=data["requester"], ticket_id=ticket_id,
                        new_status="OPEN")
    assign_incident(actor_employee_id=data["requester"], ticket_id=ticket_id,
                    assigned_team_id=data["team_b"])
    assert get_incident_detail(actor_employee_id=data["requester"], ticket_id=ticket_id)["assigned_team_id"] == data["team_b"]

    with pytest.raises(IncidentError, match="not found"):
        get_incident_detail(actor_employee_id=data["outsider"], ticket_id=ticket_id)
    with pytest.raises(IncidentError, match="Not authorized"):
        add_comment(actor_employee_id=data["outsider"], ticket_id=ticket_id,
                    body="Unauthorized comment")


def test_sqa_high_defect_blocks_completion_until_closed(workflow_fixture):
    from itoms.services.sqa import (
        SQAError, add_test_case, complete_test_plan, create_defect,
        create_test_plan, record_execution, update_defect_status,
    )

    data = workflow_fixture
    plan_id = create_test_plan(
        actor_employee_id=data["requester"],
        title="High defect readiness gate",
        scope_description="Verify fixed defects remain unresolved until retest closure.",
        release_key=None,
    )
    case_id = add_test_case(
        actor_employee_id=data["requester"],
        plan_id=plan_id,
        case_key=f"CASE-{data['suffix']}",
        title="Critical path verification",
        preconditions="Test environment is available",
        steps="Run the critical path",
        expected_result="The operation succeeds",
    )
    failed_execution = record_execution(
        actor_employee_id=data["requester"], plan_id=plan_id, case_id=case_id,
        result="FAIL", actual_result="The operation failed before the fix.",
    )
    defect_id = create_defect(
        actor_employee_id=data["requester"], plan_id=plan_id,
        execution_id=failed_execution, title="High severity regression",
        description="The failed execution identified a high severity issue.",
        severity="HIGH",
    )
    record_execution(
        actor_employee_id=data["requester"], plan_id=plan_id, case_id=case_id,
        result="PASS", actual_result="The fix appears to pass; retest defect lifecycle.",
    )
    update_defect_status(actor_employee_id=data["requester"], plan_id=plan_id,
                         defect_id=defect_id, new_status="TRIAGED")
    update_defect_status(actor_employee_id=data["requester"], plan_id=plan_id,
                         defect_id=defect_id, new_status="FIXED")

    with pytest.raises(SQAError, match="Unresolved High/Critical defects"):
        complete_test_plan(actor_employee_id=data["requester"], plan_id=plan_id)

    update_defect_status(actor_employee_id=data["requester"], plan_id=plan_id,
                         defect_id=defect_id, new_status="RETEST")
    with pytest.raises(SQAError, match="Unresolved High/Critical defects"):
        complete_test_plan(actor_employee_id=data["requester"], plan_id=plan_id)

    update_defect_status(actor_employee_id=data["requester"], plan_id=plan_id,
                         defect_id=defect_id, new_status="CLOSED")
    complete_test_plan(actor_employee_id=data["requester"], plan_id=plan_id)

    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT status FROM sqa_test_plans WHERE test_plan_id=%s", (plan_id,))
        assert cur.fetchone() == ("COMPLETED",)
    finally:
        cur.close()
        conn.close()


def test_incident_first_response_sla_records_first_public_staff_reply(workflow_fixture):
    from itoms.services.incidents import add_comment, create_incident

    data = workflow_fixture
    ticket_id = create_incident(
        actor_employee_id=data["requester"],
        requester_employee_id=data["requester"],
        assigned_team_id=data["team_a"],
        title="First response SLA test",
        description="Only a public staff response should satisfy first response SLA.",
    )

    add_comment(actor_employee_id=data["approver_one"], ticket_id=ticket_id,
                body="Internal triage note", internal=True)
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT first_responded_at FROM incident_tickets WHERE ticket_id=%s", (ticket_id,))
        assert cur.fetchone()[0] is None
    finally:
        cur.close()
        conn.close()

    add_comment(actor_employee_id=data["requester"], ticket_id=ticket_id,
                body="Any update?", internal=False)
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT first_responded_at FROM incident_tickets WHERE ticket_id=%s", (ticket_id,))
        assert cur.fetchone()[0] is None
    finally:
        cur.close()
        conn.close()

    add_comment(actor_employee_id=data["approver_one"], ticket_id=ticket_id,
                body="We are investigating the issue.", internal=False)
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT first_responded_at FROM incident_tickets WHERE ticket_id=%s", (ticket_id,))
        first_response = cur.fetchone()[0]
        assert first_response is not None
        cur.execute(
            "UPDATE incident_tickets SET first_responded_at=DATE_SUB(UTC_TIMESTAMP(), INTERVAL 5 MINUTE) WHERE ticket_id=%s",
            (ticket_id,),
        )
        conn.commit()
        cur.execute("SELECT first_responded_at FROM incident_tickets WHERE ticket_id=%s", (ticket_id,))
        original = cur.fetchone()[0]
    finally:
        cur.close()
        conn.close()

    add_comment(actor_employee_id=data["approver_one"], ticket_id=ticket_id,
                body="A later update.", internal=False)
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT first_responded_at FROM incident_tickets WHERE ticket_id=%s", (ticket_id,))
        assert cur.fetchone()[0] == original
    finally:
        cur.close()
        conn.close()


def test_incident_detail_calculates_elapsed_sla_breaches(workflow_fixture):
    from itoms.services.incidents import create_incident, get_incident_detail

    data = workflow_fixture
    ticket_id = create_incident(
        actor_employee_id=data["requester"],
        requester_employee_id=data["requester"],
        assigned_team_id=data["team_a"],
        title="SLA breach indicator test",
        description="Due dates in the past must be reported as breached.",
    )
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE incident_tickets
               SET first_response_due_at=DATE_SUB(UTC_TIMESTAMP(),INTERVAL 5 MINUTE),
                   resolution_due_at=DATE_SUB(UTC_TIMESTAMP(),INTERVAL 1 MINUTE)
               WHERE ticket_id=%s""",
            (ticket_id,),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    detail = get_incident_detail(actor_employee_id=data["requester"], ticket_id=ticket_id)
    assert detail["first_response_breached"] in (1, True)
    assert detail["resolution_breached"] in (1, True)


def test_engineering_task_pagination_filters_scope_before_limit(workflow_fixture):
    from itoms.services.engineering_tasks import create_task, list_task_assignees, list_tasks

    data = workflow_fixture
    own_task = create_task(
        actor_employee_id=data["requester"],
        team_id=data["team_a"],
        title="Authorized task survives pagination",
    )
    conn = _db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO teams (department_id,team_name,is_active) VALUES (%s,%s,TRUE)",
            (data["other_department_id"], f"Other Task Team {data['suffix']}"),
        )
        hidden_team = int(cur.lastrowid)
        for index in range(4):
            cur.execute(
                """INSERT INTO engineering_tasks
                   (task_number,title,team_id,created_by,priority,status)
                   VALUES (%s,%s,%s,%s,'HIGH','BACKLOG')""",
                (f"TASK-IT-{data['suffix']}-{index}", f"Hidden department task {index}",
                 hidden_team, data["requester"]),
            )
        conn.commit()
    finally:
        cur.close()
        conn.close()

    rows = list_tasks(actor_employee_id=data["requester"], limit=1)
    assert len(rows) == 1
    assert rows[0]["task_id"] == own_task

    assignees = list_task_assignees(actor_employee_id=data["requester"])
    assert any(
        row["employee_id"] == data["approver_one"]
        and row["team_id"] == data["team_a"]
        and row["team_name"].startswith("Workflow Team A")
        for row in assignees
    )
    assert all(row["employee_id"] != data["outsider"] for row in assignees)


def test_engineering_tasks_enforce_department_and_team_scope(workflow_fixture):
    from itoms.services.engineering_tasks import (
        TaskError, change_task_status, create_task, get_task_detail,
        list_accessible_task_teams, list_task_assignees, list_tasks,
    )

    data = workflow_fixture
    task_id = create_task(
        actor_employee_id=data["requester"],
        team_id=data["team_a"],
        title="Scoped engineering integration task",
        description="Verify department and team access controls.",
        assigned_to=data["approver_one"],
    )

    requester_tasks = {row["task_id"] for row in list_tasks(actor_employee_id=data["requester"])}
    assert task_id in requester_tasks
    assert get_task_detail(actor_employee_id=data["requester"], task_id=task_id)["task_id"] == task_id

    team_reader_tasks = {row["task_id"] for row in list_tasks(actor_employee_id=data["approver_one"])}
    assert task_id in team_reader_tasks
    assert [row["team_id"] for row in list_accessible_task_teams(
        actor_employee_id=data["approver_one"])] == [data["team_a"]]
    assert any(row["employee_id"] == data["approver_one"]
               for row in list_task_assignees(actor_employee_id=data["approver_one"]))

    with pytest.raises(TaskError, match="not found"):
        get_task_detail(actor_employee_id=data["outsider"], task_id=task_id)
    with pytest.raises(TaskError, match="Not authorized"):
        create_task(
            actor_employee_id=data["outsider"],
            team_id=data["team_a"],
            title="Unauthorized cross-department task",
        )

    change_task_status(
        actor_employee_id=data["approver_one"],
        task_id=task_id,
        new_status="READY",
    )
    assert get_task_detail(actor_employee_id=data["approver_one"], task_id=task_id)["status"] == "READY"
