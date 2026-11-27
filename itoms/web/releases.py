"""Software release register and lifecycle routes."""
from __future__ import annotations
import hmac
from flask import Blueprint,flash,g,redirect,render_template,request,session,url_for
from itoms.security.decorators import login_required
from itoms.services.authorization import ResourceContext,has_permission
from itoms.services.change_management import list_changes
from itoms.services.release_management import ReleaseError,RELEASE_STATES,create_release,list_releases,transition_release
from itoms.db.connection import get_connection
release_bp=Blueprint("releases",__name__,url_prefix="/releases")
def _choices(actor_employee_id):
    """Return only service and change records the actor may legitimately link."""
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT s.service_id,s.service_name,s.owner_team_id,t.department_id
            FROM service_records s LEFT JOIN teams t ON t.team_id=s.owner_team_id
            ORDER BY s.service_name,s.service_id LIMIT 500""")
        candidates=cur.fetchall()
    finally:
        cur.close(); conn.close()
    services=[{"service_id":row["service_id"],"service_name":row["service_name"]}
        for row in candidates if row["department_id"] is not None and has_permission(
            actor_employee_id,"service.inventory.read",
            ResourceContext(team_id=row["owner_team_id"],department_id=row["department_id"],
                resource_type="service",resource_id=str(row["service_id"]))) ]
    changes=[row for row in list_changes(actor_employee_id=actor_employee_id,limit=200)
        if row["status"] not in {"CANCELLED","CLOSED"}]
    return services,changes

def _approvers(department_id):
    """Return active approver candidates only within the release department."""
    if department_id is None:
        return []
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT employee_id,full_name FROM employees
            WHERE is_active=TRUE AND department_id=%s ORDER BY full_name,employee_id""",
            (department_id,))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()
@release_bp.get("/")
@login_required
def index():
    can_create=has_permission(g.employee_id,"release.create")
    services,changes=_choices(g.employee_id) if can_create else ([],[])
    releases=list_releases(actor_employee_id=g.employee_id)
    for item in releases:
        item["approvers"]=_approvers(item.get("department_id")) if item["can_update"] else []
    return render_template("releases/index.html",releases=releases,can_create=can_create,services=services,changes=changes,states=sorted(RELEASE_STATES),csrf_token_value=session.get("csrf_token",""))
@release_bp.post("/")
@login_required
def create():
    csrf=session.get("csrf_token","")
    if not csrf or not hmac.compare_digest(str(csrf),str(request.form.get("csrf_token",""))): return "Invalid request token",400
    def optional_int(key):
        value=request.form.get(key,"").strip(); return int(value) if value else None
    try:
        rid=create_release(actor_employee_id=g.employee_id,release_key=request.form.get("release_key",""),version_label=request.form.get("version_label",""),release_notes=request.form.get("release_notes",""),service_id=optional_int("service_id"),target_at=request.form.get("target_at") or None,change_id=optional_int("change_id"))
        flash("Release record created.","success")
    except (ReleaseError,ValueError,TypeError) as exc: flash(str(exc) or "Invalid release details.","danger")
    return redirect(url_for("releases.index"))
@release_bp.post("/<int:release_id>/status")
@login_required
def status(release_id:int):
    csrf=session.get("csrf_token","")
    if not csrf or not hmac.compare_digest(str(csrf),str(request.form.get("csrf_token",""))): return "Invalid request token",400
    try:
        approvers=[int(value) for value in request.form.getlist("approver_employee_ids") if value.strip()]
        transition_release(actor_employee_id=g.employee_id,release_id=release_id,new_status=request.form.get("status","").strip().upper(),approver_employee_ids=approvers,approval_reason=request.form.get("approval_reason","").strip() or None)
        flash("Release approval workflow requested." if request.form.get("status","").strip().upper()=="REQUEST_APPROVAL" else "Release status updated.","success")
    except (ReleaseError,ValueError,TypeError) as exc: flash(str(exc) or "Invalid release update.","danger")
    return redirect(url_for("releases.index"))