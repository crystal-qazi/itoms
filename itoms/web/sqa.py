"""Authenticated SQA planning, execution and sign-off routes."""
from __future__ import annotations

import hmac

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from itoms.db.connection import get_connection
from itoms.security.decorators import login_required
from itoms.services.authorization import ResourceContext, has_permission
from itoms.services.sqa import (
    SQAError, add_test_case, complete_test_plan, create_defect, create_test_plan,
    get_test_plan, list_sqa_release_signoffs, list_test_plans, record_execution,
    record_release_signoff, update_defect_status,
)

sqa_bp = Blueprint("sqa", __name__, url_prefix="/sqa")


def _csrf_valid():
    token=session.get("csrf_token","")
    return bool(token and hmac.compare_digest(str(token),str(request.form.get("csrf_token",""))))


def _actor_context():
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("""SELECT e.department_id,m.team_id FROM employees e
            LEFT JOIN employee_team_memberships m ON m.employee_id=e.employee_id AND m.is_primary=TRUE
            WHERE e.employee_id=%s AND e.is_active=TRUE""",(g.employee_id,))
        row=cur.fetchone()
        return ResourceContext(owner_employee_id=g.employee_id,department_id=row[0],team_id=row[1]) if row else None
    finally:
        cur.close(); conn.close()


def _release_choices():
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT r.release_id,r.release_key,r.version_label,r.created_by,
            e.department_id,s.owner_team_id FROM software_releases r
            JOIN employees e ON e.employee_id=r.created_by
            LEFT JOIN service_records s ON s.service_id=r.service_id
            WHERE r.status IN ('IN_TEST','READY','APPROVED')
            ORDER BY r.created_at DESC LIMIT 100""")
        rows=cur.fetchall()
        visible=[]
        for row in rows:
            context=ResourceContext(owner_employee_id=row["created_by"],department_id=row["department_id"],
                team_id=row["owner_team_id"],resource_type="release",resource_id=str(row["release_id"]))
            if has_permission(g.employee_id,"release.read",context):
                row["can_signoff"]=has_permission(g.employee_id,"sqa.signoff.create",context)
                visible.append(row)
        return visible
    finally:
        cur.close(); conn.close()


@sqa_bp.get("/")
@login_required
def index():
    actor_context=_actor_context()
    can_create=bool(actor_context and has_permission(g.employee_id,"sqa.plan.create",actor_context))
    releases=_release_choices()
    signoff_releases=[row for row in releases if row["can_signoff"]]
    can_signoff=bool(signoff_releases)
    return render_template("sqa/index.html",plans=list_test_plans(actor_employee_id=g.employee_id),
        releases=releases,signoff_releases=signoff_releases,can_create=can_create,can_signoff=can_signoff,
        csrf_token_value=session.get("csrf_token",""))


@sqa_bp.post("/plans")
@login_required
def create_plan():
    if not _csrf_valid(): return "Invalid request token",400
    try:
        plan_id=create_test_plan(actor_employee_id=g.employee_id,title=request.form.get("title",""),
            scope_description=request.form.get("scope_description",""),release_key=request.form.get("release_key"))
        flash("SQA test plan created.","success")
        return redirect(url_for("sqa.detail",plan_id=plan_id))
    except SQAError as exc:
        flash(str(exc),"danger")
        return redirect(url_for("sqa.index"))


@sqa_bp.get("/plans/<int:plan_id>")
@login_required
def detail(plan_id: int):
    try:
        plan=get_test_plan(actor_employee_id=g.employee_id,plan_id=plan_id)
        signoffs=list_sqa_release_signoffs(actor_employee_id=g.employee_id,release_key=plan["release_key"]) if plan["release_key"] else []
        return render_template("sqa/detail.html",plan=plan,signoffs=signoffs,
            results=["PASS","FAIL","BLOCKED","RETEST"],severities=["LOW","MEDIUM","HIGH","CRITICAL"],
            csrf_token_value=session.get("csrf_token",""))
    except SQAError as exc:
        flash(str(exc),"danger")
        return redirect(url_for("sqa.index"))


@sqa_bp.post("/plans/<int:plan_id>/cases")
@login_required
def add_case(plan_id: int):
    if not _csrf_valid(): return "Invalid request token",400
    try:
        add_test_case(actor_employee_id=g.employee_id,plan_id=plan_id,case_key=request.form.get("case_key",""),
            title=request.form.get("title",""),preconditions=request.form.get("preconditions",""),
            steps=request.form.get("steps",""),expected_result=request.form.get("expected_result",""))
        flash("Test case added.","success")
    except SQAError as exc: flash(str(exc),"danger")
    return redirect(url_for("sqa.detail",plan_id=plan_id))


@sqa_bp.post("/plans/<int:plan_id>/cases/<int:case_id>/executions")
@login_required
def execute_case(plan_id: int, case_id: int):
    if not _csrf_valid(): return "Invalid request token",400
    try:
        record_execution(actor_employee_id=g.employee_id,plan_id=plan_id,case_id=case_id,
            result=request.form.get("result",""),actual_result=request.form.get("actual_result",""))
        flash("Execution result recorded.","success")
    except SQAError as exc: flash(str(exc),"danger")
    return redirect(url_for("sqa.detail",plan_id=plan_id))


@sqa_bp.post("/plans/<int:plan_id>/defects")
@login_required
def defect(plan_id: int):
    if not _csrf_valid(): return "Invalid request token",400
    try:
        create_defect(actor_employee_id=g.employee_id,plan_id=plan_id,
            execution_id=int(request.form.get("execution_id","")),title=request.form.get("title",""),
            description=request.form.get("description",""),severity=request.form.get("severity","MEDIUM"))
        flash("Defect recorded.","success")
    except (SQAError,ValueError,TypeError) as exc: flash(str(exc),"danger")
    return redirect(url_for("sqa.detail",plan_id=plan_id))


@sqa_bp.post("/plans/<int:plan_id>/complete")
@login_required
def complete(plan_id: int):
    if not _csrf_valid(): return "Invalid request token",400
    try:
        complete_test_plan(actor_employee_id=g.employee_id,plan_id=plan_id)
        flash("SQA plan completed; all latest results passed.","success")
    except SQAError as exc: flash(str(exc),"danger")
    return redirect(url_for("sqa.detail",plan_id=plan_id))


@sqa_bp.post("/signoffs")
@login_required
def signoff():
    if not _csrf_valid(): return "Invalid request token",400
    try:
        record_release_signoff(actor_employee_id=g.employee_id,release_key=request.form.get("release_key",""),
            decision=request.form.get("decision",""),comments=request.form.get("comments",""))
        flash("SQA sign-off recorded.","success")
    except SQAError as exc: flash(str(exc),"danger")
    return redirect(url_for("sqa.index"))



@sqa_bp.post("/plans/<int:plan_id>/defects/<int:defect_id>/status")
@login_required
def update_defect(plan_id: int, defect_id: int):
    if not _csrf_valid(): return "Invalid request token",400
    try:
        update_defect_status(actor_employee_id=g.employee_id,plan_id=plan_id,
            defect_id=defect_id,new_status=request.form.get("status",""))
        flash("Defect status updated.","success")
    except SQAError as exc:
        flash(str(exc),"danger")
    return redirect(url_for("sqa.detail",plan_id=plan_id))
