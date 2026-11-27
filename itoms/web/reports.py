"""Personal saved-report builder and CSV export routes."""
from __future__ import annotations

import hmac
import re
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for, make_response

from itoms.security.decorators import login_required
from itoms.services.reporting import DATASETS, ReportingError, build_csv, create_report, list_reports, run_report

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@reports_bp.get("/")
@login_required
def index():
    try:
        reports = list_reports(employee_id=g.employee_id)
    except ReportingError:
        reports = []
    return render_template(
        "reports/index.html", reports=reports, datasets=DATASETS,
        csrf_token_value=session.get("csrf_token", ""),
    )


@reports_bp.post("/")
@login_required
def create():
    if not _valid_csrf():
        return "Invalid request token", 400
    raw_filters = {
        "status": request.form.get("status", "").strip().upper(),
        "priority": request.form.get("priority", "").strip().upper(),
        "domain": request.form.get("domain", "").strip().upper(),
    }
    try:
        report_id = create_report(
            employee_id=g.employee_id,
            report_name=request.form.get("report_name", ""),
            dataset_key=request.form.get("dataset_key", ""),
            columns=request.form.getlist("columns"),
            filters=raw_filters,
        )
        flash("Saved report created.", "success")
    except ReportingError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("reports.index"))
    return redirect(url_for("reports.export_csv", report_id=report_id))


@reports_bp.get("/<int:report_id>/csv")
@login_required
def export_csv(report_id: int):
    try:
        name, columns, rows = run_report(employee_id=g.employee_id, report_id=report_id)
    except ReportingError:
        return "Report not found or not authorized.", 404
    content = build_csv(columns, rows)
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._-")[:80] or "report"
    response = make_response(content)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
