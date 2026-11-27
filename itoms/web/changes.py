"""Change request queue, detail and controlled transition routes."""
from __future__ import annotations
import hmac
from flask import Blueprint,flash,g,redirect,render_template,request,session,url_for
from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.change_management import ChangeError,CHANGE_TYPES,RISKS,create_change,get_change,list_changes,transition_change
from itoms.db.connection import get_connection
change_bp=Blueprint("changes",__name__,url_prefix="/changes")
def _owners():
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try: cur.execute("SELECT employee_id,full_name FROM employees WHERE is_active=TRUE ORDER BY full_name"); return cur.fetchall()
    finally: cur.close(); conn.close()
@change_bp.get("/")
@login_required
def index():
    can_create=has_permission(g.employee_id,"change.create")
    return render_template("changes/index.html",changes=list_changes(actor_employee_id=g.employee_id),can_create=can_create,owners=_owners() if can_create else [],change_types=sorted(CHANGE_TYPES),risks=sorted(RISKS),csrf_token_value=session.get("csrf_token",""))
@change_bp.post("/")
@login_required
def create():
    csrf=session.get("csrf_token","")
    if not csrf or not hmac.compare_digest(str(csrf),str(request.form.get("csrf_token",""))): return "Invalid request token",400
    raw_owner=request.form.get("owner_employee_id","").strip()
    try:
        change_id=create_change(actor_employee_id=g.employee_id,title=request.form.get("title",""),description=request.form.get("description",""),change_type=request.form.get("change_type",""),risk_level=request.form.get("risk_level",""),planned_start=request.form.get("planned_start") or None,planned_end=request.form.get("planned_end") or None,implementation_plan=request.form.get("implementation_plan",""),rollback_plan=request.form.get("rollback_plan",""),verification_plan=request.form.get("verification_plan",""),owner_employee_id=int(raw_owner) if raw_owner else None)
        flash("Change request created as a draft.","success"); return redirect(url_for("changes.detail",change_id=change_id))
    except (ChangeError,ValueError,TypeError) as exc: flash(str(exc) or "Invalid change request.","danger"); return redirect(url_for("changes.index"))
@change_bp.get("/<int:change_id>")
@login_required
def detail(change_id:int):
    try: item=get_change(actor_employee_id=g.employee_id,change_id=change_id)
    except ChangeError: return "Change record not found",404
    return render_template("changes/detail.html",item=item,transitions=["SUBMITTED","SCHEDULED","IMPLEMENTING","IMPLEMENTED","FAILED","CANCELLED","CLOSED"],approvers=_owners() if item["can_update"] and item["status"] in {"DRAFT","REJECTED"} else [],csrf_token_value=session.get("csrf_token",""))
@change_bp.post("/<int:change_id>/status")
@login_required
def status(change_id:int):
    csrf=session.get("csrf_token","")
    if not csrf or not hmac.compare_digest(str(csrf),str(request.form.get("csrf_token",""))): return "Invalid request token",400
    try:
        approvers=[int(value) for value in request.form.getlist("approver_employee_ids") if value.strip()]
        transition_change(actor_employee_id=g.employee_id,change_id=change_id,new_status=request.form.get("status","").strip().upper(),details=request.form.get("details","").strip() or None,approver_employee_ids=approvers)
        flash("Change status updated.","success")
    except (ChangeError,ValueError,TypeError) as exc: flash(str(exc) or "Invalid change update.","danger")
    return redirect(url_for("changes.detail",change_id=change_id))