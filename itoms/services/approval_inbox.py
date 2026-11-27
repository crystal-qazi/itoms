"""Approval inbox queries and decisions."""
from __future__ import annotations
from itoms.db.connection import get_connection

def list_current_approvals(employee_id: int, limit: int = 100):
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT r.approval_request_id,r.request_type,r.resource_type,r.resource_id,
            r.requested_by,r.request_reason,r.created_at,r.current_step,
            e.full_name AS requester_name
            FROM approval_requests r JOIN approval_steps s
              ON s.approval_request_id=r.approval_request_id AND s.step_number=r.current_step
            JOIN employees e ON e.employee_id=r.requested_by
            WHERE r.status='PENDING' AND s.approver_employee_id=%s AND s.decision='PENDING'
            ORDER BY r.created_at ASC LIMIT %s""",(employee_id,limit))
        return cur.fetchall()
    finally: cur.close(); conn.close()
