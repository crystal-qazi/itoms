"""Change management operations with server-side authorization."""
from __future__ import annotations
import re, secrets
from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission

class ChangeError(ValueError):
    """Invalid or unauthorized change operation."""
CHANGE_TYPES={"NORMAL","STANDARD","EMERGENCY"}
RISKS={"LOW","MEDIUM","HIGH","CRITICAL"}
STATUSES={"DRAFT","SUBMITTED","REJECTED","SCHEDULED","IMPLEMENTING","IMPLEMENTED","FAILED","CANCELLED","CLOSED"}
TRANSITIONS={"DRAFT":{"SUBMITTED","CANCELLED"},"SUBMITTED":{"SCHEDULED","CANCELLED"},"REJECTED":{"SUBMITTED","CANCELLED"},"SCHEDULED":{"IMPLEMENTING","CANCELLED"},"IMPLEMENTING":{"IMPLEMENTED","FAILED"},"IMPLEMENTED":{"CLOSED"},"FAILED":{"CLOSED"},"CANCELLED":set(),"CLOSED":set()}

def _context(row):
    return ResourceContext(owner_employee_id=row["requested_by"], resource_type="change", resource_id=str(row["change_id"]))

def list_changes(*, actor_employee_id:int, limit:int=100):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT change_id,change_number,title,change_type,risk_level,status,requested_by,owner_employee_id,planned_start,planned_end,created_at FROM change_records ORDER BY created_at DESC,change_id DESC LIMIT %s",(min(max(limit,1),200),))
        rows=cur.fetchall()
    finally: cur.close(); conn.close()
    visible=[]
    for row in rows:
        if has_permission(actor_employee_id,"change.read",_context(row)):
            row["can_update"]=has_permission(actor_employee_id,"change.update",_context(row))
            visible.append(row)
    return visible

def get_change(*,actor_employee_id:int,change_id:int):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT c.*,e.full_name AS requester_name,o.full_name AS owner_name FROM change_records c JOIN employees e ON e.employee_id=c.requested_by LEFT JOIN employees o ON o.employee_id=c.owner_employee_id WHERE c.change_id=%s",(change_id,))
        row=cur.fetchone()
        if row:
            cur.execute("SELECT actor_employee_id,action_key,details,occurred_at FROM change_activity WHERE change_id=%s ORDER BY occurred_at,change_activity_id",(change_id,)); row["activity"]=cur.fetchall()
        if row:
            cur.execute("""SELECT approval_request_id,status,current_step,request_reason,created_at,completed_at
                FROM approval_requests WHERE resource_type='change' AND resource_id=%s
                ORDER BY created_at DESC,approval_request_id DESC LIMIT 1""",(str(change_id),))
            approval=cur.fetchone()
        else:
            approval=None
        if approval:
            cur.execute("""SELECT s.step_number,s.decision,s.decided_at,s.decision_comment,e.full_name AS approver_name
                FROM approval_steps s JOIN employees e ON e.employee_id=s.approver_employee_id
                WHERE s.approval_request_id=%s ORDER BY s.step_number""",(approval["approval_request_id"],))
            approval["steps"]=cur.fetchall()
        row["approval"]=approval
    finally: cur.close(); conn.close()
    if not row or not has_permission(actor_employee_id,"change.read",_context(row)): raise ChangeError("Change record not found.")
    row["can_update"]=has_permission(actor_employee_id,"change.update",_context(row))
    return row

def create_change(*,actor_employee_id:int,title:str,description:str,change_type:str,risk_level:str,planned_start:str|None,planned_end:str|None,implementation_plan:str,rollback_plan:str,verification_plan:str,owner_employee_id:int|None=None):
    if not has_permission(actor_employee_id,"change.create"): raise ChangeError("Not authorized to create changes.")
    title=title.strip(); description=description.strip()
    if not title or len(title)>240: raise ChangeError("Title is required (maximum 240 characters).")
    if not description: raise ChangeError("Description is required.")
    if change_type not in CHANGE_TYPES or risk_level not in RISKS: raise ChangeError("Select a valid change type and risk level.")
    plans=[implementation_plan.strip(),rollback_plan.strip(),verification_plan.strip()]
    if any(not x for x in plans): raise ChangeError("Implementation, rollback and verification plans are all required.")
    if planned_start and planned_end and planned_end<=planned_start: raise ChangeError("Planned end must be later than planned start.")
    if owner_employee_id is not None:
        conn=get_connection(); cur=conn.cursor()
        try: cur.execute("SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE",(owner_employee_id,)); valid=cur.fetchone()
        finally: cur.close(); conn.close()
        if not valid: raise ChangeError("Selected change owner is inactive or unavailable.")
    change_number="CHG-"+secrets.token_hex(5).upper()
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("INSERT INTO change_records (change_number,title,description,change_type,risk_level,requested_by,owner_employee_id,planned_start,planned_end,implementation_plan,rollback_plan,verification_plan) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",(change_number,title,description,change_type,risk_level,actor_employee_id,owner_employee_id,planned_start or None,planned_end or None,*plans))
        change_id=int(cur.lastrowid)
        cur.execute("INSERT INTO change_activity (change_id,actor_employee_id,action_key,details) VALUES (%s,%s,'CREATED',%s)",(change_id,actor_employee_id,change_number))
        cur.execute("INSERT INTO audit_events (actor_employee_id,event_key,target_type,target_id,outcome) VALUES (%s,'CHANGE_CREATED','change',%s,'SUCCESS')",(actor_employee_id,str(change_id)))
        conn.commit(); return change_id
    except Exception: conn.rollback(); raise
    finally: cur.close(); conn.close()

def transition_change(*,actor_employee_id:int,change_id:int,new_status:str,details:str|None=None,approver_employee_ids:list[int]|None=None):
    if new_status not in STATUSES: raise ChangeError("Invalid change status.")
    approvers=list(dict.fromkeys(int(x) for x in (approver_employee_ids or [])))
    if new_status=="SUBMITTED":
        if not approvers or len(approvers)>10 or actor_employee_id in approvers:
            raise ChangeError("Select 1–10 distinct approvers other than yourself before submitting.")
        if not has_permission(actor_employee_id,"approvals.create"):
            raise ChangeError("You are not authorized to submit an approval workflow.")
        if details is not None and len(details)>4000:
            raise ChangeError("Approval reason is too long (maximum 4000 characters).")
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try: cur.execute("SELECT change_id,requested_by,status FROM change_records WHERE change_id=%s",(change_id,)); snapshot=cur.fetchone()
    finally: cur.close(); conn.close()
    if not snapshot: raise ChangeError("Change record not found.")
    context=_context(snapshot)
    if not has_permission(actor_employee_id,"change.update",context): raise ChangeError("Not authorized to update this change.")
    if new_status not in TRANSITIONS.get(snapshot["status"],set()): raise ChangeError("This status transition is not allowed.")
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT status,requested_by FROM change_records WHERE change_id=%s FOR UPDATE",(change_id,)); current=cur.fetchone()
        if not current or current[0]!=snapshot["status"] or current[1]!=snapshot["requested_by"]: raise ChangeError("Change record changed; reload and try again.")
        if new_status=="SUBMITTED":
            for approver in approvers:
                cur.execute("SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE",(approver,))
                if not cur.fetchone(): raise ChangeError("An approver is inactive or unavailable.")
            cur.execute("""INSERT INTO approval_requests
                (request_type,resource_type,resource_id,requested_by,request_reason)
                VALUES ('CHANGE','change',%s,%s,%s)""",(str(change_id),actor_employee_id,details))
            approval_id=int(cur.lastrowid)
            for step,approver in enumerate(approvers,1):
                cur.execute("""INSERT INTO approval_steps
                    (approval_request_id,step_number,approver_employee_id)
                    VALUES (%s,%s,%s)""",(approval_id,step,approver))
            cur.execute("""INSERT INTO approval_history
                (approval_request_id,actor_employee_id,action_key,comment)
                VALUES (%s,%s,'SUBMITTED',%s)""",(approval_id,actor_employee_id,details))
            cur.execute("""INSERT INTO audit_events
                (actor_employee_id,event_key,target_type,target_id,outcome,details)
                VALUES (%s,'APPROVAL_SUBMITTED','approval',%s,'SUCCESS',
                    JSON_OBJECT('request_type','CHANGE','resource_type','change','approver_count',%s))""",
                (actor_employee_id,str(approval_id),len(approvers)))
        if new_status=="SCHEDULED":
            cur.execute("""SELECT status FROM approval_requests
                WHERE resource_type='change' AND resource_id=%s
                ORDER BY created_at DESC,approval_request_id DESC LIMIT 1 FOR UPDATE""",(str(change_id),))
            approval=cur.fetchone()
            if not approval or approval[0]!="APPROVED":
                raise ChangeError("Scheduling is blocked until the linked change approval is fully approved.")
        if new_status=="CANCELLED":
            cur.execute("""SELECT approval_request_id,status FROM approval_requests
                WHERE resource_type='change' AND resource_id=%s
                ORDER BY created_at DESC,approval_request_id DESC LIMIT 1 FOR UPDATE""",(str(change_id),))
            linked_approval=cur.fetchone()
            if linked_approval and linked_approval[1]=="PENDING":
                approval_id=linked_approval[0]
                cur.execute("UPDATE approval_requests SET status='CANCELLED',completed_at=UTC_TIMESTAMP() WHERE approval_request_id=%s",(approval_id,))
                cur.execute("""UPDATE approval_steps SET decision='SKIPPED'
                    WHERE approval_request_id=%s AND decision='PENDING'""",(approval_id,))
                cur.execute("""INSERT INTO approval_history
                    (approval_request_id,actor_employee_id,action_key,comment)
                    VALUES (%s,%s,'CANCELLED',%s)""",(approval_id,actor_employee_id,details))
                cur.execute("""INSERT INTO audit_events
                    (actor_employee_id,event_key,target_type,target_id,outcome)
                    VALUES (%s,'APPROVAL_CANCELLED','approval',%s,'SUCCESS')""",
                    (actor_employee_id,str(approval_id)))
        cur.execute("UPDATE change_records SET status=%s,implementation_result=CASE WHEN %s IN ('IMPLEMENTED','FAILED') THEN %s ELSE implementation_result END WHERE change_id=%s",(new_status,new_status,details,change_id))
        cur.execute("INSERT INTO change_activity (change_id,actor_employee_id,action_key,details) VALUES (%s,%s,%s,%s)",(change_id,actor_employee_id,"STATUS_"+new_status,details))
        cur.execute("INSERT INTO audit_events (actor_employee_id,event_key,target_type,target_id,outcome) VALUES (%s,'CHANGE_STATUS_CHANGED','change',%s,'SUCCESS')",(actor_employee_id,str(change_id)))
        conn.commit()
    except Exception: conn.rollback(); raise
    finally: cur.close(); conn.close()
