"""Sequential approval workflow with actor-bound decisions and history."""
from __future__ import annotations
from itoms.db.connection import get_connection
from itoms.services.authorization import has_permission, has_permission_in_transaction

class ApprovalError(ValueError):
    """Approval operation is invalid or unauthorized."""

def create_approval(*, actor_employee_id: int, request_type: str, resource_type: str,
                    resource_id: str, approver_employee_ids: list[int],
                    reason: str | None = None) -> int:
    approvers = list(dict.fromkeys(int(value) for value in approver_employee_ids))
    if not approvers or len(approvers) > 10 or actor_employee_id in approvers:
        raise ApprovalError("Provide 1–10 distinct approvers other than the requester.")
    if (not request_type or len(request_type) > 80 or not resource_type
            or len(resource_type) > 80 or not resource_id or len(resource_id) > 100):
        raise ApprovalError("Request and resource identifiers are required and must fit their limits.")
    if reason is not None and len(reason) > 4000:
        raise ApprovalError("Approval reason is too long (maximum 4000 characters).")
    if any(value <= 0 for value in approvers):
        raise ApprovalError("Approver IDs must be positive employee IDs.")

    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(
            cur, actor_employee_id, "approvals.create", None,
            lock_employee_ids=approvers,
        ):
            raise ApprovalError("Not authorized to create approvals.")
        for approver in approvers:
            cur.execute(
                "SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE",
                (approver,),
            )
            if not cur.fetchone():
                raise ApprovalError("An approver is inactive or unavailable.")
        cur.execute(
            """INSERT INTO approval_requests
               (request_type,resource_type,resource_id,requested_by,request_reason)
               VALUES (%s,%s,%s,%s,%s)""",
            (request_type, resource_type, resource_id, actor_employee_id, reason),
        )
        request_id = int(cur.lastrowid)
        for step, approver in enumerate(approvers, 1):
            cur.execute(
                """INSERT INTO approval_steps
                   (approval_request_id,step_number,approver_employee_id)
                   VALUES (%s,%s,%s)""",
                (request_id, step, approver),
            )
        cur.execute(
            """INSERT INTO approval_history
               (approval_request_id,actor_employee_id,action_key,comment)
               VALUES (%s,%s,'SUBMITTED',%s)""",
            (request_id, actor_employee_id, reason),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'APPROVAL_SUBMITTED','approval',%s,'SUCCESS',
                       JSON_OBJECT('request_type',%s,'resource_type',%s,'approver_count',%s))""",
            (actor_employee_id, str(request_id), request_type, resource_type, len(approvers)),
        )
        conn.commit()
        return request_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def decide_approval(*, actor_employee_id: int, request_id: int, decision: str,
                    comment: str | None=None) -> None:
    if decision not in {"APPROVED","REJECTED"}:
        raise ApprovalError("Decision must be APPROVED or REJECTED.")
    if comment is not None and len(comment)>4000:
        raise ApprovalError("Approval comment is too long (maximum 4000 characters).")
    conn=get_connection(); cur=conn.cursor()
    try:
        # Change workflows lock the resource before the approval row, matching
        # Change Management transitions and avoiding an inverted lock order.
        cur.execute("""SELECT request_type,resource_type,resource_id
            FROM approval_requests WHERE approval_request_id=%s""",(request_id,))
        identity=cur.fetchone()
        if not identity:
            raise ApprovalError("Approval is not pending.")
        if identity[0]=="CHANGE" and identity[1]=="change":
            cur.execute("SELECT status FROM change_records WHERE change_id=%s FOR UPDATE",(int(identity[2]),))
            if not cur.fetchone():
                raise ApprovalError("Linked change record does not exist.")
        cur.execute("""SELECT status,current_step,request_type,resource_type,resource_id
            FROM approval_requests WHERE approval_request_id=%s FOR UPDATE""",(request_id,))
        request=cur.fetchone()
        if not request or request[0]!="PENDING" or tuple(request[2:])!=tuple(identity):
            raise ApprovalError("Approval changed; reload and try again.")
        cur.execute("""SELECT s.approval_step_id,s.decision
            FROM approval_steps s
            JOIN employees e ON e.employee_id=s.approver_employee_id AND e.is_active=TRUE
            WHERE s.approval_request_id=%s AND s.step_number=%s
              AND s.approver_employee_id=%s FOR UPDATE""",
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
            if request[2]=="CHANGE" and request[3]=="change":
                cur.execute("""UPDATE change_records SET status='REJECTED'
                    WHERE change_id=%s AND status='SUBMITTED'""",(int(request[4]),))
                cur.execute("""INSERT INTO change_activity
                    (change_id,actor_employee_id,action_key,details)
                    VALUES (%s,%s,'APPROVAL_REJECTED',%s)""",(int(request[4]),actor_employee_id,comment))
                cur.execute("""INSERT INTO audit_events
                    (actor_employee_id,event_key,target_type,target_id,outcome,details)
                    VALUES (%s,'CHANGE_APPROVAL_REJECTED','change',%s,'SUCCESS',
                        JSON_OBJECT('approval_request_id',%s))""",
                    (actor_employee_id,str(request[4]),request_id))
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
        cur.execute("""INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome,details)
            VALUES (%s,%s,'approval',%s,'SUCCESS',JSON_OBJECT('decision',%s))""",
            (actor_employee_id,"APPROVAL_"+decision,str(request_id),decision))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()

def cancel_approval(*, actor_employee_id: int, request_id: int) -> None:
    """Cancel an approval after transaction-bound requester/permission authorization."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT requested_by,status,request_type,resource_type,resource_id
               FROM approval_requests WHERE approval_request_id=%s""",
            (request_id,),
        )
        snapshot = cur.fetchone()
        if not snapshot or snapshot[1] != "PENDING":
            raise ApprovalError("Approval is not pending.")

        if snapshot[0] == actor_employee_id:
            cur.execute(
                "SELECT is_active FROM employees WHERE employee_id=%s FOR UPDATE",
                (actor_employee_id,),
            )
            actor = cur.fetchone()
            if not actor or not actor[0]:
                raise ApprovalError("Not authorized to cancel this approval.")
        elif not has_permission_in_transaction(
            cur, actor_employee_id, "approvals.cancel", None,
            lock_employee_ids=[snapshot[0]],
        ):
            raise ApprovalError("Not authorized to cancel this approval.")

        # Change workflows preserve resource -> approval row ordering, matching
        # approval decisions and Change Management transitions.
        if snapshot[2] == "CHANGE" and snapshot[3] == "change":
            cur.execute(
                "SELECT status FROM change_records WHERE change_id=%s FOR UPDATE",
                (int(snapshot[4]),),
            )
            if not cur.fetchone():
                raise ApprovalError("Linked change record does not exist.")
        cur.execute(
            """SELECT requested_by,status,request_type,resource_type,resource_id
               FROM approval_requests WHERE approval_request_id=%s FOR UPDATE""",
            (request_id,),
        )
        row = cur.fetchone()
        if (not row or row[1] != "PENDING" or tuple(row[2:]) != tuple(snapshot[2:])
                or row[0] != snapshot[0]):
            raise ApprovalError("Approval changed; reload and try again.")
        cur.execute(
            "UPDATE approval_requests SET status='CANCELLED',completed_at=UTC_TIMESTAMP() WHERE approval_request_id=%s",
            (request_id,),
        )
        cur.execute(
            """UPDATE approval_steps SET decision='SKIPPED'
               WHERE approval_request_id=%s AND decision='PENDING'""",
            (request_id,),
        )
        cur.execute(
            """INSERT INTO approval_history
               (approval_request_id,actor_employee_id,action_key)
               VALUES (%s,%s,'CANCELLED')""",
            (request_id, actor_employee_id),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'APPROVAL_CANCELLED','approval',%s,'SUCCESS')""",
            (actor_employee_id, str(request_id)),
        )
        if snapshot[2] == "CHANGE" and snapshot[3] == "change":
            change_id = int(snapshot[4])
            cur.execute(
                "UPDATE change_records SET status='DRAFT' WHERE change_id=%s AND status='SUBMITTED'",
                (change_id,),
            )
            cur.execute(
                """INSERT INTO change_activity
                   (change_id,actor_employee_id,action_key,details)
                   VALUES (%s,%s,'APPROVAL_CANCELLED','Approval request cancelled')""",
                (change_id, actor_employee_id),
            )
            cur.execute(
                """INSERT INTO audit_events
                   (actor_employee_id,event_key,target_type,target_id,outcome,details)
                   VALUES (%s,'CHANGE_APPROVAL_CANCELLED','change',%s,'SUCCESS',
                       JSON_OBJECT('approval_request_id',%s))""",
                (actor_employee_id, str(change_id), request_id),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
