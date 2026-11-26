"""Sequential approval workflow with actor-bound decisions and history."""
from __future__ import annotations
from itoms.db.connection import get_connection
from itoms.services.authorization import has_permission

class ApprovalError(ValueError):
    """Approval operation is invalid or unauthorized."""

def create_approval(*, actor_employee_id: int, request_type: str, resource_type: str,
                    resource_id: str, approver_employee_ids: list[int], reason: str | None=None) -> int:
    if not has_permission(actor_employee_id,"approvals.create"):
        raise ApprovalError("Not authorized to create approvals.")
    approvers=list(dict.fromkeys(int(x) for x in approver_employee_ids))
    if not approvers or len(approvers)>10 or actor_employee_id in approvers:
        raise ApprovalError("Provide 1–10 distinct approvers other than the requester.")
    if not request_type or not resource_type or not resource_id:
        raise ApprovalError("Request and resource identifiers are required.")
    conn=get_connection(); cur=conn.cursor()
    try:
        for approver in approvers:
            cur.execute("SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE",(approver,))
            if not cur.fetchone(): raise ApprovalError("An approver is inactive or unavailable.")
        cur.execute("""INSERT INTO approval_requests
            (request_type,resource_type,resource_id,requested_by,request_reason)
            VALUES (%s,%s,%s,%s,%s)""",(request_type,resource_type,resource_id,actor_employee_id,reason))
        request_id=int(cur.lastrowid)
        for step,approver in enumerate(approvers,1):
            cur.execute("""INSERT INTO approval_steps
                (approval_request_id,step_number,approver_employee_id)
                VALUES (%s,%s,%s)""",(request_id,step,approver))
        cur.execute("""INSERT INTO approval_history
            (approval_request_id,actor_employee_id,action_key,comment)
            VALUES (%s,%s,'SUBMITTED',%s)""",(request_id,actor_employee_id,reason))
        conn.commit(); return request_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()

def decide_approval(*, actor_employee_id: int, request_id: int, decision: str,
                    comment: str | None=None) -> None:
    if decision not in {"APPROVED","REJECTED"}:
        raise ApprovalError("Decision must be APPROVED or REJECTED.")
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT status,current_step FROM approval_requests WHERE approval_request_id=%s FOR UPDATE",(request_id,))
        request=cur.fetchone()
        if not request or request[0]!="PENDING": raise ApprovalError("Approval is not pending.")
        cur.execute("""SELECT approval_step_id,decision FROM approval_steps
            WHERE approval_request_id=%s AND step_number=%s AND approver_employee_id=%s FOR UPDATE""",
            (request_id,request[1],actor_employee_id))
        step=cur.fetchone()
        if not step or step[1]!="PENDING": raise ApprovalError("You are not the current approver.")
        cur.execute("""UPDATE approval_steps SET decision=%s,decision_comment=%s,decided_at=UTC_TIMESTAMP()
            WHERE approval_step_id=%s""",(decision,comment,step[0]))
        if decision=="REJECTED":
            status="REJECTED"
            cur.execute("UPDATE approval_requests SET status='REJECTED',completed_at=UTC_TIMESTAMP() WHERE approval_request_id=%s",(request_id,))
            cur.execute("""UPDATE approval_steps SET decision='SKIPPED'
                WHERE approval_request_id=%s AND decision='PENDING'""",(request_id,))
        else:
            cur.execute("SELECT MAX(step_number) FROM approval_steps WHERE approval_request_id=%s",(request_id,))
            last_step=cur.fetchone()[0]
            if request[1]>=last_step:
                status="APPROVED"
                cur.execute("UPDATE approval_requests SET status='APPROVED',completed_at=UTC_TIMESTAMP() WHERE approval_request_id=%s",(request_id,))
            else:
                status="PENDING"
                cur.execute("UPDATE approval_requests SET current_step=current_step+1 WHERE approval_request_id=%s",(request_id,))
        cur.execute("""INSERT INTO approval_history
            (approval_request_id,actor_employee_id,action_key,comment)
            VALUES (%s,%s,%s,%s)""",(request_id,actor_employee_id,decision,comment))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()

def cancel_approval(*, actor_employee_id: int, request_id: int) -> None:
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT requested_by,status FROM approval_requests WHERE approval_request_id=%s FOR UPDATE",(request_id,))
        row=cur.fetchone()
        if not row or row[1]!="PENDING": raise ApprovalError("Approval is not pending.")
        if row[0]!=actor_employee_id and not has_permission(actor_employee_id,"approvals.cancel"):
            raise ApprovalError("Not authorized to cancel this approval.")
        cur.execute("UPDATE approval_requests SET status='CANCELLED',completed_at=UTC_TIMESTAMP() WHERE approval_request_id=%s",(request_id,))
        cur.execute("""UPDATE approval_steps SET decision='SKIPPED'
            WHERE approval_request_id=%s AND decision='PENDING'""",(request_id,))
        cur.execute("""INSERT INTO approval_history
            (approval_request_id,actor_employee_id,action_key)
            VALUES (%s,%s,'CANCELLED')""",(request_id,actor_employee_id))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()
