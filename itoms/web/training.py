"""IT Training catalogue and enrollment routes."""
from __future__ import annotations

import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.training import (
    ENROLLMENT_STATUSES, TrainingError, create_course, enroll_employee,
    list_courses, list_enrollments, set_course_active, update_enrollment_status,
)

training_bp = Blueprint("training", __name__, url_prefix="/training")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@training_bp.get("/")
@login_required
def index():
    can_manage = has_permission(g.employee_id, "training.course.manage")
    try:
        courses = list_courses(actor_employee_id=g.employee_id, include_inactive=can_manage)
        enrollments = list_enrollments(actor_employee_id=g.employee_id) if (
            has_permission(g.employee_id, "training.read") or has_permission(g.employee_id, "training.manage")
        ) else []
    except TrainingError:
        return "Not authorized to view training.", 403
    return render_template(
        "training/index.html", courses=courses, enrollments=enrollments,
        can_manage=can_manage,
        can_enroll=has_permission(g.employee_id, "training.enroll") or has_permission(g.employee_id, "training.manage"),
        enrollment_statuses=sorted(ENROLLMENT_STATUSES),
        csrf_token_value=session.get("csrf_token", ""),
    )


@training_bp.post("/courses")
@login_required
def course_create():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_course(
            actor_employee_id=g.employee_id,
            course_title=request.form.get("course_title", ""),
            description=request.form.get("description", ""),
        )
        flash("Training course created.", "success")
    except TrainingError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("training.index"))


@training_bp.post("/courses/<int:course_id>/active")
@login_required
def course_active(course_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        set_course_active(
            actor_employee_id=g.employee_id, course_id=course_id,
            is_active=request.form.get("is_active") == "1",
        )
        flash("Training course updated.", "success")
    except TrainingError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("training.index"))


@training_bp.post("/courses/<int:course_id>/enroll")
@login_required
def enroll(course_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        enroll_employee(actor_employee_id=g.employee_id, course_id=course_id)
        flash("You have been enrolled.", "success")
    except TrainingError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("training.index"))


@training_bp.post("/enrollments/<int:enrollment_id>/status")
@login_required
def enrollment_status(enrollment_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        update_enrollment_status(
            actor_employee_id=g.employee_id, enrollment_id=enrollment_id,
            new_status=request.form.get("status", "").strip().upper(),
        )
        flash("Training enrollment updated.", "success")
    except TrainingError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("training.index"))
