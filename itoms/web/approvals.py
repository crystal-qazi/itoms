"""Assigned approval inbox and decision routes."""
from __future__ import annotations
import hmac
from flask import Blueprint,flash,g,redirect,render_template,request,session,url_for
from itoms.security.decorators import login_required
from itoms.services.approval_inbox import list_current_approvals
from itoms.services.approvals import ApprovalError,decide_approval
approval_bp=Blueprint("approvals",__name__,url_prefix="/approvals")
@approval_bp.get("/")
@login_required
def inbox():
    return render_template("approvals/index.html",items=list_current_approvals(g.employee_id),csrf_token_value=session.get("csrf_token",""))
@approval_bp.post("/<int:request_id>/decision")
@login_required
def decision(request_id:int):
    csrf=session.get("csrf_token","")
    if not csrf or not hmac.compare_digest(str(csrf),str(request.form.get("csrf_token",""))): return "Invalid request token",400
    try:
        decide_approval(actor_employee_id=g.employee_id,request_id=request_id,decision=request.form.get("decision",""),comment=request.form.get("comment","").strip() or None)
        flash("Approval decision recorded.","success")
    except ApprovalError as exc: flash(str(exc),"danger")
    return redirect(url_for("approvals.inbox"))
