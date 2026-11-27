"""Manual SQA planning, execution, defect and release sign-off services."""
from __future__ import annotations

import secrets

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission


class SQAError(ValueError):
    """An SQA operation is invalid or outside the actor's authorization scope."""


PLAN_STATUSES = {"DRAFT", "ACTIVE", "COMPLETED", "CANCELLED"}
TEST_RESULTS = {"PASS", "FAIL", "BLOCKED", "RETEST"}
DEFECT_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
DEFECT_STATUSES = {"OPEN", "TRIAGED", "FIXED", "RETEST", "CLOSED", "REJECTED"}
SIGNOFF_DECISIONS = {"APPROVED", "REJECTED", "CONDITIONAL"}
DEFECT_TRANSITIONS = {
    "OPEN": {"TRIAGED", "REJECTED"},
    "TRIAGED": {"FIXED", "REJECTED"},
    "FIXED": {"RETEST"},
    "RETEST": {"CLOSED", "OPEN"},
    "CLOSED": set(),
    "REJECTED": set(),
}


def _plan_context(row):
    return ResourceContext(owner_employee_id=row["created_by"], team_id=row.get("team_id"),
                           department_id=row.get("department_id"), resource_type="sqa_plan",
                           resource_id=str(row["test_plan_id"]))


def _load_plan(cur, plan_id: int, *, lock: bool = False):
    query = """SELECT p.test_plan_id,p.plan_key,p.release_key,p.title,p.status,p.created_by,
        e.department_id,m.team_id
        FROM sqa_test_plans p JOIN employees e ON e.employee_id=p.created_by
        LEFT JOIN employee_team_memberships m ON m.employee_id=e.employee_id AND m.is_primary=TRUE
        WHERE p.test_plan_id=%s"""
    cur.execute(query + (" FOR UPDATE" if lock else ""), (plan_id,))
    return cur.fetchone()


def _require_plan_permission(actor_employee_id: int, permission: str, plan):
    if not plan or not has_permission(actor_employee_id, permission, _plan_context(plan)):
        raise SQAError("SQA plan not found or not authorized.")


def list_test_plans(*, actor_employee_id: int):
    """Return every plan visible to the actor, filtering in bounded batches."""
    visible = []
    batch_size = 200
    offset = 0
    while True:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("""SELECT p.test_plan_id,p.plan_key,p.release_key,p.title,p.status,p.created_by,
                p.created_at,e.department_id,m.team_id
                FROM sqa_test_plans p JOIN employees e ON e.employee_id=p.created_by
                LEFT JOIN employee_team_memberships m ON m.employee_id=e.employee_id AND m.is_primary=TRUE
                ORDER BY p.created_at DESC,p.test_plan_id DESC LIMIT %s OFFSET %s""",
                (batch_size, offset))
            rows = cur.fetchall()
        finally:
            cur.close()
            conn.close()
        if not rows:
            break
        visible.extend(row for row in rows
            if has_permission(actor_employee_id,"sqa.plan.read",_plan_context(row)))
        offset += len(rows)
        if len(rows) < batch_size:
            break
    return visible

def get_test_plan(*, actor_employee_id: int, plan_id: int):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT p.*,e.full_name AS creator_name,e.department_id,m.team_id
            FROM sqa_test_plans p JOIN employees e ON e.employee_id=p.created_by
            LEFT JOIN employee_team_memberships m ON m.employee_id=e.employee_id AND m.is_primary=TRUE
            WHERE p.test_plan_id=%s""",(plan_id,))
        plan=cur.fetchone()
        if plan:
            cur.execute("""SELECT c.test_case_id,c.case_key,c.title,c.preconditions,c.steps,c.expected_result,
                (SELECT x.result FROM sqa_test_executions x WHERE x.test_case_id=c.test_case_id
                 ORDER BY x.executed_at DESC,x.execution_id DESC LIMIT 1) AS latest_result,
                (SELECT x.execution_id FROM sqa_test_executions x WHERE x.test_case_id=c.test_case_id
                 ORDER BY x.executed_at DESC,x.execution_id DESC LIMIT 1) AS latest_execution_id
                FROM sqa_test_cases c WHERE c.test_plan_id=%s ORDER BY c.case_key""",(plan_id,))
            plan["cases"]=cur.fetchall()
            cur.execute("""SELECT d.defect_id,d.defect_key,d.title,d.severity,d.status,d.created_at
                FROM sqa_defects d JOIN sqa_test_executions x ON x.execution_id=d.execution_id
                JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
                WHERE c.test_plan_id=%s ORDER BY d.created_at DESC""",(plan_id,))
            plan["defects"]=cur.fetchall()
    finally:
        cur.close(); conn.close()
    _require_plan_permission(actor_employee_id,"sqa.plan.read",plan)
    plan["can_update"]=has_permission(actor_employee_id,"sqa.plan.update",_plan_context(plan))
    plan["can_add_case"]=has_permission(actor_employee_id,"sqa.case.create",_plan_context(plan))
    plan["can_execute"]=has_permission(actor_employee_id,"sqa.execution.create",_plan_context(plan))
    plan["can_create_defect"]=has_permission(actor_employee_id,"sqa.defect.create",_plan_context(plan))
    plan["can_update_defects"]=has_permission(actor_employee_id,"sqa.defect.update",_plan_context(plan))
    return plan


def create_test_plan(*, actor_employee_id: int, title: str, scope_description: str, release_key: str | None):
    title=title.strip()
    if not title or len(title)>200:
        raise SQAError("Plan title is required (maximum 200 characters).")
    release_key=(release_key or "").strip().upper() or None
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("""SELECT e.department_id,m.team_id FROM employees e
            LEFT JOIN employee_team_memberships m ON m.employee_id=e.employee_id AND m.is_primary=TRUE
            WHERE e.employee_id=%s AND e.is_active=TRUE""",(actor_employee_id,))
        actor_scope=cur.fetchone()
        if not actor_scope or not has_permission(actor_employee_id,"sqa.plan.create",
            ResourceContext(owner_employee_id=actor_employee_id,department_id=actor_scope[0],team_id=actor_scope[1])):
            raise SQAError("Not authorized to create SQA plans.")
        if release_key:
            cur.execute("""SELECT r.release_id,r.created_by,e.department_id,s.owner_team_id
                FROM software_releases r JOIN employees e ON e.employee_id=r.created_by
                LEFT JOIN service_records s ON s.service_id=r.service_id WHERE r.release_key=%s""",(release_key,))
            release=cur.fetchone()
            if not release:
                raise SQAError("Selected release was not found.")
            if not has_permission(actor_employee_id,"release.read",
                ResourceContext(owner_employee_id=release[1],department_id=release[2],team_id=release[3],
                    resource_type="release",resource_id=str(release[0]))):
                raise SQAError("Not authorized to associate this release.")
        plan_key="SQA-"+secrets.token_hex(5).upper()
        cur.execute("""INSERT INTO sqa_test_plans
            (plan_key,release_key,title,scope_description,created_by,status)
            VALUES (%s,%s,%s,%s,%s,'ACTIVE')""",
            (plan_key,release_key,title,scope_description.strip() or None,actor_employee_id))
        plan_id=int(cur.lastrowid)
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'SQA_PLAN_CREATED','sqa_plan',%s,'SUCCESS')""",(actor_employee_id,str(plan_id)))
        conn.commit(); return plan_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()


def add_test_case(*, actor_employee_id: int, plan_id: int, case_key: str, title: str,
                  preconditions: str, steps: str, expected_result: str):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        plan=_load_plan(cur,plan_id,lock=True)
        _require_plan_permission(actor_employee_id,"sqa.case.create",plan)
        if plan["status"]!="ACTIVE":
            raise SQAError("Test cases can only be added to active plans.")
        case_key=case_key.strip().upper(); title=title.strip(); steps=steps.strip(); expected_result=expected_result.strip()
        if not case_key or len(case_key)>80 or not title or len(title)>200 or not steps or not expected_result:
            raise SQAError("A valid case key, title, test steps and expected result are required.")
        cur.execute("""INSERT INTO sqa_test_cases
            (test_plan_id,case_key,title,preconditions,steps,expected_result)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (plan_id,case_key,title,preconditions.strip() or None,steps,expected_result))
        case_id=int(cur.lastrowid)
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'SQA_CASE_CREATED','sqa_test_case',%s,'SUCCESS')""",(actor_employee_id,str(case_id)))
        conn.commit(); return case_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()


def record_execution(*, actor_employee_id: int, plan_id: int, case_id: int, result: str, actual_result: str):
    result=result.strip().upper()
    if result not in TEST_RESULTS:
        raise SQAError("Choose a valid test execution result.")
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        plan=_load_plan(cur,plan_id,lock=True)
        _require_plan_permission(actor_employee_id,"sqa.execution.create",plan)
        if plan["status"]!="ACTIVE":
            raise SQAError("Executions can only be recorded against active plans.")
        cur.execute("SELECT test_case_id FROM sqa_test_cases WHERE test_case_id=%s AND test_plan_id=%s",(case_id,plan_id))
        if not cur.fetchone():
            raise SQAError("Test case not found in this plan.")
        cur.execute("""INSERT INTO sqa_test_executions
            (test_case_id,executed_by,result,actual_result,executed_at)
            VALUES (%s,%s,%s,%s,UTC_TIMESTAMP())""",(case_id,actor_employee_id,result,actual_result.strip() or None))
        execution_id=int(cur.lastrowid)
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'SQA_EXECUTION_RECORDED','sqa_execution',%s,'SUCCESS')""",(actor_employee_id,str(execution_id)))
        conn.commit(); return execution_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()


def create_defect(*, actor_employee_id: int, plan_id: int, execution_id: int,
                  title: str, description: str, severity: str):
    title=title.strip(); description=description.strip(); severity=severity.strip().upper()
    if not title or len(title)>200 or not description or severity not in DEFECT_SEVERITIES:
        raise SQAError("Provide a valid defect title, description and severity.")
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        plan=_load_plan(cur,plan_id,lock=True)
        _require_plan_permission(actor_employee_id,"sqa.defect.create",plan)
        cur.execute("""SELECT x.execution_id,x.result FROM sqa_test_executions x
            JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
            WHERE x.execution_id=%s AND c.test_plan_id=%s""",(execution_id,plan_id))
        execution=cur.fetchone()
        if not execution or execution["result"]!="FAIL":
            raise SQAError("Defects must reference a failed execution in this plan.")
        defect_key="BUG-"+secrets.token_hex(5).upper()
        cur.execute("""INSERT INTO sqa_defects (defect_key,execution_id,title,description,severity)
            VALUES (%s,%s,%s,%s,%s)""",(defect_key,execution_id,title,description,severity))
        defect_id=int(cur.lastrowid)
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'SQA_DEFECT_CREATED','sqa_defect',%s,'SUCCESS')""",(actor_employee_id,str(defect_id)))
        conn.commit(); return defect_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()


def _assert_plan_ready(cur, plan_id: int):
    cur.execute("SELECT COUNT(*) AS total_cases FROM sqa_test_cases WHERE test_plan_id=%s",(plan_id,))
    if cur.fetchone()["total_cases"]<1:
        raise SQAError("A plan needs at least one test case before completion.")
    cur.execute("""SELECT COUNT(*) AS failing_cases FROM sqa_test_cases c WHERE c.test_plan_id=%s
        AND NOT EXISTS (SELECT 1 FROM sqa_test_executions x
            WHERE x.test_case_id=c.test_case_id AND x.execution_id=(
                SELECT x2.execution_id FROM sqa_test_executions x2
                WHERE x2.test_case_id=c.test_case_id
                ORDER BY x2.executed_at DESC,x2.execution_id DESC LIMIT 1)
            AND x.result='PASS')""",(plan_id,))
    if cur.fetchone()["failing_cases"]:
        raise SQAError("Every test case must have a latest PASS result.")
    cur.execute("""SELECT COUNT(*) AS unresolved_defects FROM sqa_defects d
        JOIN sqa_test_executions x ON x.execution_id=d.execution_id
        JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
        WHERE c.test_plan_id=%s AND d.severity IN ('HIGH','CRITICAL')
        AND d.status NOT IN ('CLOSED','REJECTED')""",(plan_id,))
    if cur.fetchone()["unresolved_defects"]:
        raise SQAError("Unresolved High/Critical defects prevent SQA approval.")


def complete_test_plan(*, actor_employee_id: int, plan_id: int):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        plan=_load_plan(cur,plan_id,lock=True)
        _require_plan_permission(actor_employee_id,"sqa.plan.update",plan)
        if plan["status"]!="ACTIVE":
            raise SQAError("Only active plans can be completed.")
        _assert_plan_ready(cur,plan_id)
        cur.execute("UPDATE sqa_test_plans SET status='COMPLETED' WHERE test_plan_id=%s",(plan_id,))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'SQA_PLAN_COMPLETED','sqa_plan',%s,'SUCCESS')""",(actor_employee_id,str(plan_id)))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()


def record_release_signoff(*, actor_employee_id: int, release_key: str, decision: str, comments: str):
    release_key=release_key.strip().upper(); decision=decision.strip().upper()
    if decision not in SIGNOFF_DECISIONS or not release_key:
        raise SQAError("A release and valid sign-off decision are required.")
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        # Lock release first, matching the release lifecycle's locking order.
        cur.execute("""SELECT r.release_id,r.created_by,r.status,e.department_id,s.owner_team_id
            FROM software_releases r JOIN employees e ON e.employee_id=r.created_by
            LEFT JOIN service_records s ON s.service_id=r.service_id
            WHERE r.release_key=%s FOR UPDATE""",(release_key,))
        release=cur.fetchone()
        if not release:
            raise SQAError("Release record not found.")
        cur.execute("SELECT is_active FROM employees WHERE employee_id=%s",(actor_employee_id,))
        actor=cur.fetchone()
        if not actor or not actor["is_active"]:
            raise SQAError("An active employee account is required for SQA sign-off.")
        if release["status"] not in {"IN_TEST", "READY", "APPROVED"}:
            raise SQAError("SQA sign-off is closed for this release lifecycle stage.")
        release_context=ResourceContext(owner_employee_id=release["created_by"],
            team_id=release["owner_team_id"],department_id=release["department_id"],
            resource_type="release",resource_id=str(release["release_id"]))
        if not has_permission(actor_employee_id,"release.read",release_context):
            raise SQAError("Not authorized to sign off this release.")
        if not has_permission(actor_employee_id,"sqa.signoff.create",release_context):
            raise SQAError("Not authorized to record SQA sign-off for this release.")
        if decision=="APPROVED":
            cur.execute("SELECT test_plan_id FROM sqa_test_plans WHERE release_key=%s AND status='COMPLETED'",(release_key,))
            plans=cur.fetchall()
            if not plans:
                raise SQAError("Complete at least one linked SQA test plan before approval.")
            for plan in plans:
                _assert_plan_ready(cur,plan["test_plan_id"])
        cur.execute("""INSERT INTO sqa_release_signoffs (release_key,signed_by,decision,comments)
            VALUES (%s,%s,%s,%s) ON DUPLICATE KEY UPDATE decision=VALUES(decision),
            comments=VALUES(comments),signed_at=UTC_TIMESTAMP()""",
            (release_key,actor_employee_id,decision,comments.strip() or None))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'SQA_RELEASE_SIGNOFF','release',%s,'SUCCESS')""",(actor_employee_id,release_key))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()

def list_sqa_release_signoffs(*, actor_employee_id: int, release_key: str):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT r.release_id,r.created_by,e.department_id,srv.owner_team_id
            FROM software_releases r JOIN employees e ON e.employee_id=r.created_by
            LEFT JOIN service_records srv ON srv.service_id=r.service_id WHERE r.release_key=%s""",
            (release_key,))
        release=cur.fetchone()
        if not release:
            return []
        context=ResourceContext(owner_employee_id=release["created_by"],team_id=release["owner_team_id"],
            department_id=release["department_id"],resource_type="release",resource_id=str(release["release_id"]))
        if not has_permission(actor_employee_id,"sqa.signoff.read",context):
            return []
        cur.execute("""SELECT s.release_key,s.decision,s.comments,s.signed_at,
            COALESCE(e.full_name,'Former or inactive user') AS signer
            FROM sqa_release_signoffs s
            LEFT JOIN employees e ON e.employee_id=s.signed_by AND e.is_active=TRUE
            WHERE s.release_key=%s ORDER BY s.signed_at DESC""",(release_key,))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()



def update_defect_status(*, actor_employee_id: int, plan_id: int, defect_id: int,
                         new_status: str):
    new_status=new_status.strip().upper()
    if new_status not in DEFECT_STATUSES:
        raise SQAError("Invalid defect status.")
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT d.defect_id,d.status,p.test_plan_id,p.created_by,
            e.department_id,m.team_id FROM sqa_defects d
            JOIN sqa_test_executions x ON x.execution_id=d.execution_id
            JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
            JOIN sqa_test_plans p ON p.test_plan_id=c.test_plan_id
            JOIN employees e ON e.employee_id=p.created_by
            LEFT JOIN employee_team_memberships m ON m.employee_id=e.employee_id AND m.is_primary=TRUE
            WHERE d.defect_id=%s AND p.test_plan_id=%s""",(defect_id,plan_id))
        snapshot=cur.fetchone()
        if not snapshot:
            raise SQAError("Defect not found in this plan.")
        context=ResourceContext(owner_employee_id=snapshot["created_by"],
            team_id=snapshot["team_id"],department_id=snapshot["department_id"],
            resource_type="sqa_plan",resource_id=str(snapshot["test_plan_id"]))
        if not has_permission(actor_employee_id,"sqa.defect.update",context):
            raise SQAError("Not authorized to update this defect.")
        if new_status not in DEFECT_TRANSITIONS.get(snapshot["status"],set()):
            raise SQAError("This defect status transition is not allowed.")
        cur.execute("SELECT status FROM sqa_defects WHERE defect_id=%s FOR UPDATE",(defect_id,))
        current=cur.fetchone()
        if not current or current["status"]!=snapshot["status"]:
            raise SQAError("Defect changed; reload and try again.")
        cur.execute("UPDATE sqa_defects SET status=%s WHERE defect_id=%s",(new_status,defect_id))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'SQA_DEFECT_STATUS_CHANGED','sqa_defect',%s,'SUCCESS')""",
            (actor_employee_id,str(defect_id)))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()
