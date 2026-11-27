"""Software release planning with enforced SQA approval and deployment gates."""
from __future__ import annotations

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission


class ReleaseError(ValueError):
    """Invalid or unauthorized release operation."""


RELEASE_STATES={"PLANNED","IN_TEST","READY","APPROVED","DEPLOYING","RELEASED","ROLLED_BACK","CANCELLED"}
RELEASE_TRANSITIONS={
    "PLANNED":{"IN_TEST","CANCELLED"},
    "IN_TEST":{"READY","CANCELLED"},
    "READY":{"APPROVED","CANCELLED"},
    "APPROVED":{"DEPLOYING","CANCELLED"},
    "DEPLOYING":{"RELEASED","ROLLED_BACK"},
    "RELEASED":set(),"ROLLED_BACK":set(),"CANCELLED":set()
}


def _ctx(row):
    return ResourceContext(
        owner_employee_id=row["created_by"],
        team_id=row.get("team_id"),
        department_id=row.get("department_id"),
        resource_type="release",
        resource_id=str(row["release_id"]),
    )


def _assert_sqa_release_gate(cur, release_key: str):
    """Fail closed unless completed linked testing and an unambiguous SQA approval exist."""
    cur.execute("""SELECT COUNT(*) FROM sqa_test_plans
        WHERE release_key=%s AND status='COMPLETED'""",(release_key,))
    if cur.fetchone()[0] < 1:
        raise ReleaseError("SQA gate: at least one linked completed test plan is required.")

    cur.execute("""SELECT COUNT(*) FROM sqa_test_cases c
        JOIN sqa_test_plans p ON p.test_plan_id=c.test_plan_id
        WHERE p.release_key=%s AND p.status='COMPLETED'""",(release_key,))
    total_cases=cur.fetchone()[0]
    if total_cases < 1:
        raise ReleaseError("SQA gate: completed plans must contain test cases.")

    cur.execute("""SELECT COUNT(*) FROM sqa_test_cases c
        JOIN sqa_test_plans p ON p.test_plan_id=c.test_plan_id
        WHERE p.release_key=%s AND p.status='COMPLETED'
          AND NOT EXISTS (
            SELECT 1 FROM sqa_test_executions x
            WHERE x.test_case_id=c.test_case_id
              AND x.execution_id=(SELECT x2.execution_id FROM sqa_test_executions x2
                  WHERE x2.test_case_id=c.test_case_id
                  ORDER BY x2.executed_at DESC,x2.execution_id DESC LIMIT 1)
              AND x.result='PASS')""",(release_key,))
    if cur.fetchone()[0]:
        raise ReleaseError("SQA gate: every test case must have a latest PASS result.")

    cur.execute("""SELECT COUNT(*) FROM sqa_defects d
        JOIN sqa_test_executions x ON x.execution_id=d.execution_id
        JOIN sqa_test_cases c ON c.test_case_id=x.test_case_id
        JOIN sqa_test_plans p ON p.test_plan_id=c.test_plan_id
        WHERE p.release_key=%s AND d.severity IN ('HIGH','CRITICAL')
          AND d.status NOT IN ('CLOSED','REJECTED')""",(release_key,))
    if cur.fetchone()[0]:
        raise ReleaseError("SQA gate: unresolved High/Critical defects block release approval.")

    cur.execute("""SELECT
        SUM(CASE WHEN decision='APPROVED' THEN 1 ELSE 0 END),
        SUM(CASE WHEN decision<>'APPROVED' THEN 1 ELSE 0 END)
        FROM sqa_release_signoffs WHERE release_key=%s""",(release_key,))
    approved,rejected=cur.fetchone()
    if not approved or rejected:
        raise ReleaseError("SQA gate: an APPROVED sign-off is required and every recorded sign-off must be APPROVED.")


def list_releases(*,actor_employee_id:int):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT r.release_id,r.release_key,r.version_label,r.status,r.target_at,r.service_id,
            r.released_at,r.created_by,s.service_name,e.department_id,
            s.owner_team_id AS service_team_id,st.department_id AS service_department_id,
            CASE WHEN st.department_id=e.department_id THEN s.owner_team_id ELSE NULL END AS team_id,
            (SELECT ar.status FROM approval_requests ar
             WHERE ar.resource_type='release' AND ar.resource_id=CAST(r.release_id AS CHAR)
             ORDER BY ar.created_at DESC,ar.approval_request_id DESC LIMIT 1) AS approval_status
            FROM software_releases r
            JOIN employees e ON e.employee_id=r.created_by
            LEFT JOIN service_records s ON s.service_id=r.service_id
            LEFT JOIN teams st ON st.team_id=s.owner_team_id
            ORDER BY r.created_at DESC LIMIT 200""")
        rows=cur.fetchall()
    finally:
        cur.close(); conn.close()
    visible=[]
    for row in rows:
        if not has_permission(actor_employee_id,"release.read",_ctx(row)):
            continue
        # A release reader must not learn a linked service's name unless they
        # independently have permission to read that service resource.
        if row["service_name"] is not None and (
            row["service_department_id"] is None or not has_permission(
                actor_employee_id,"service.inventory.read",
                ResourceContext(team_id=row["service_team_id"],
                    department_id=row["service_department_id"],
                    resource_type="service",resource_id=str(row["service_id"])
                    if "service_id" in row else None))):
            row["service_name"]=None
        row["can_update"]=has_permission(actor_employee_id,"release.update",_ctx(row))
        visible.append(row)
    return visible


def create_release(*,actor_employee_id:int,release_key:str,version_label:str,release_notes:str,
                   service_id:int|None,target_at:str|None,change_id:int|None):
    actor_conn=get_connection(); actor_cur=actor_conn.cursor()
    try:
        actor_cur.execute("""SELECT e.department_id,
            (SELECT m.team_id FROM employee_team_memberships m
             WHERE m.employee_id=e.employee_id AND m.is_primary=TRUE LIMIT 1)
            FROM employees e WHERE e.employee_id=%s AND e.is_active=TRUE""",(actor_employee_id,))
        actor_row=actor_cur.fetchone()
    finally: actor_cur.close(); actor_conn.close()
    if not actor_row or actor_row[0] is None or not has_permission(
        actor_employee_id,"release.create",ResourceContext(department_id=actor_row[0],team_id=actor_row[1])
    ):
        raise ReleaseError("Not authorized to create releases in this department.")
    release_key=release_key.strip().upper(); version_label=version_label.strip()
    if not release_key or len(release_key)>100 or not version_label or len(version_label)>80:
        raise ReleaseError("Release key and version are required and must fit their limits.")
    conn=get_connection(); cur=conn.cursor()
    try:
        if service_id is not None:
            cur.execute("""SELECT s.service_id,s.owner_team_id,t.department_id
                FROM service_records s LEFT JOIN teams t ON t.team_id=s.owner_team_id
                WHERE s.service_id=%s""",(service_id,))
            service=cur.fetchone()
            if not service: raise ReleaseError("Service record not found.")
            if not has_permission(actor_employee_id,"service.inventory.read",
                ResourceContext(team_id=service[1],department_id=service[2],
                    resource_type="service",resource_id=str(service[0]))):
                raise ReleaseError("Not authorized to link this service.")
        if change_id is not None:
            cur.execute("""SELECT c.change_id,c.requested_by,e.department_id,
                    (SELECT m.team_id FROM employee_team_memberships m
                     JOIN teams t ON t.team_id=m.team_id AND t.department_id=e.department_id
                     WHERE m.employee_id=COALESCE(c.owner_employee_id,c.requested_by)
                       AND m.is_primary=TRUE LIMIT 1) AS team_id
                FROM change_records c JOIN employees e ON e.employee_id=c.requested_by
                WHERE c.change_id=%s""",(change_id,))
            change=cur.fetchone()
            if not change: raise ReleaseError("Change record not found.")
            if not has_permission(actor_employee_id,"change.read",
                ResourceContext(owner_employee_id=change[1],department_id=change[2],team_id=change[3],
                    resource_type="change",resource_id=str(change[0]))):
                raise ReleaseError("Not authorized to link this change.")
        cur.execute("""INSERT INTO software_releases
            (release_key,service_id,version_label,release_notes,target_at,created_by)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (release_key,service_id,version_label,release_notes.strip(),target_at or None,actor_employee_id))
        release_id=int(cur.lastrowid)
        if change_id is not None:
            cur.execute("INSERT INTO release_change_links (release_id,change_id) VALUES (%s,%s)",(release_id,change_id))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'RELEASE_CREATED','release',%s,'SUCCESS')""",(actor_employee_id,str(release_id)))
        conn.commit(); return release_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()


def transition_release(*,actor_employee_id:int,release_id:int,new_status:str,
                       approver_employee_ids:list[int]|None=None,approval_reason:str|None=None):
    request_approval = new_status=="REQUEST_APPROVAL"
    if new_status not in RELEASE_STATES and not request_approval:
        raise ReleaseError("Invalid release status.")
    approvers=list(dict.fromkeys(int(x) for x in (approver_employee_ids or [])))
    if request_approval:
        if not approvers or len(approvers)>10 or actor_employee_id in approvers:
            raise ReleaseError("Select 1–10 distinct approvers other than yourself.")
        if approval_reason is not None and len(approval_reason)>4000:
            raise ReleaseError("Approval reason is too long (maximum 4000 characters).")
        if not has_permission(actor_employee_id,"approvals.create"):
            raise ReleaseError("You are not authorized to submit a release approval workflow.")
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT r.release_id,r.release_key,r.created_by,r.status,e.department_id,
            CASE WHEN st.department_id=e.department_id THEN s.owner_team_id ELSE NULL END AS team_id
            FROM software_releases r JOIN employees e ON e.employee_id=r.created_by
            LEFT JOIN service_records s ON s.service_id=r.service_id
            LEFT JOIN teams st ON st.team_id=s.owner_team_id
            WHERE r.release_id=%s""",(release_id,))
        row=cur.fetchone()
    finally:
        cur.close(); conn.close()
    if not row or not has_permission(actor_employee_id,"release.update",_ctx(row)):
        raise ReleaseError("Release record not found or not authorized.")
    if request_approval:
        if row["status"]!="READY":
            raise ReleaseError("Release approval can only be requested when the release is READY.")
    elif new_status not in RELEASE_TRANSITIONS.get(row["status"],set()):
        raise ReleaseError("This release transition is not allowed.")

    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("""SELECT status,created_by,release_key FROM software_releases
            WHERE release_id=%s FOR UPDATE""",(release_id,))
        current=cur.fetchone()
        if not current or current[0]!=row["status"] or current[1]!=row["created_by"] or current[2]!=row["release_key"]:
            raise ReleaseError("Release changed; reload and try again.")
        if request_approval:
            cur.execute("""SELECT approval_request_id,status FROM approval_requests
                WHERE resource_type='release' AND resource_id=%s
                ORDER BY created_at DESC,approval_request_id DESC LIMIT 1 FOR UPDATE""",(str(release_id),))
            previous=cur.fetchone()
            if previous and previous[1]=="PENDING":
                raise ReleaseError("A release approval request is already pending.")
            if previous and previous[1]=="APPROVED":
                raise ReleaseError("This release already has an approved approval request.")
            for approver in approvers:
                cur.execute("""SELECT 1 FROM employees
                    WHERE employee_id=%s AND is_active=TRUE AND department_id=%s""",
                    (approver,row["department_id"]))
                if not cur.fetchone():
                    raise ReleaseError("Every release approver must be active and belong to the release department.")
            cur.execute("""INSERT INTO approval_requests
                (request_type,resource_type,resource_id,requested_by,request_reason)
                VALUES ('RELEASE','release',%s,%s,%s)""",(str(release_id),actor_employee_id,approval_reason))
            approval_id=int(cur.lastrowid)
            for step,approver in enumerate(approvers,1):
                cur.execute("""INSERT INTO approval_steps
                    (approval_request_id,step_number,approver_employee_id)
                    VALUES (%s,%s,%s)""",(approval_id,step,approver))
            cur.execute("""INSERT INTO approval_history
                (approval_request_id,actor_employee_id,action_key,comment)
                VALUES (%s,%s,'SUBMITTED',%s)""",(approval_id,actor_employee_id,approval_reason))
            cur.execute("""INSERT INTO audit_events
                (actor_employee_id,event_key,target_type,target_id,outcome,details)
                VALUES (%s,'APPROVAL_SUBMITTED','approval',%s,'SUCCESS',
                    JSON_OBJECT('request_type','RELEASE','resource_type','release','approver_count',%s))""",
                (actor_employee_id,str(approval_id),len(approvers)))
            cur.execute("""INSERT INTO audit_events
                (actor_employee_id,event_key,target_type,target_id,outcome)
                VALUES (%s,'RELEASE_APPROVAL_REQUESTED','release',%s,'SUCCESS')""",
                (actor_employee_id,str(release_id)))
            conn.commit()
            return
        # Approval and deployment boundaries require both independent gates.
        if new_status in {"APPROVED","DEPLOYING"}:
            cur.execute("""SELECT status FROM approval_requests
                WHERE resource_type='release' AND resource_id=%s
                ORDER BY created_at DESC,approval_request_id DESC LIMIT 1 FOR UPDATE""",(str(release_id),))
            approval=cur.fetchone()
            if not approval or approval[0]!="APPROVED":
                raise ReleaseError("Release approval is blocked until the linked approval workflow is fully approved.")
            _assert_sqa_release_gate(cur,current[2])
        if new_status=="CANCELLED":
            cur.execute("""SELECT approval_request_id,status FROM approval_requests
                WHERE resource_type='release' AND resource_id=%s
                ORDER BY created_at DESC,approval_request_id DESC LIMIT 1 FOR UPDATE""",(str(release_id),))
            pending=cur.fetchone()
            if pending and pending[1]=="PENDING":
                approval_id=pending[0]
                cur.execute("UPDATE approval_requests SET status='CANCELLED',completed_at=UTC_TIMESTAMP() WHERE approval_request_id=%s",(approval_id,))
                cur.execute("""UPDATE approval_steps SET decision='SKIPPED'
                    WHERE approval_request_id=%s AND decision='PENDING'""",(approval_id,))
                cur.execute("""INSERT INTO approval_history
                    (approval_request_id,actor_employee_id,action_key)
                    VALUES (%s,%s,'CANCELLED')""",(approval_id,actor_employee_id))
                cur.execute("""INSERT INTO audit_events
                    (actor_employee_id,event_key,target_type,target_id,outcome)
                    VALUES (%s,'APPROVAL_CANCELLED','approval',%s,'SUCCESS')""",
                    (actor_employee_id,str(approval_id)))
        cur.execute("""UPDATE software_releases SET status=%s,
            released_at=CASE WHEN %s='RELEASED' THEN UTC_TIMESTAMP() ELSE released_at END
            WHERE release_id=%s""",(new_status,new_status,release_id))
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome)
            VALUES (%s,'RELEASE_STATUS_CHANGED','release',%s,'SUCCESS')""",
            (actor_employee_id,str(release_id)))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()
