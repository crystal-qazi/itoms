"""Authenticated in-app notification inbox."""
from __future__ import annotations
import hmac
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from itoms.security.decorators import login_required
from itoms.services.notifications import list_inbox, mark_read

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")

@notifications_bp.get("/")
@login_required
def index():
    unread_only = request.args.get("unread") == "1"
    items = list_inbox(employee_id=g.employee_id, limit=100, unread_only=unread_only)
    unread_count = sum(1 for item in items if item["read_at"] is None) if unread_only else len(list_inbox(employee_id=g.employee_id, limit=100, unread_only=True))
    return render_template("notifications/index.html", notifications=items, unread_only=unread_only, unread_count=unread_count, csrf_token_value=session.get("csrf_token", ""))

@notifications_bp.post("/<int:notification_id>/read")
@login_required
def read(notification_id: int):
    csrf = session.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))): return "Invalid request token", 400
    mark_read(employee_id=g.employee_id, notification_id=notification_id)
    flash("Notification marked as read.", "success")
    return redirect(url_for("notifications.index", unread=1 if request.form.get("unread_only") == "1" else None))