"""Permission-scoped saved reports over allowlisted application services."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime

from itoms.db.connection import get_connection
from itoms.services.authorization import has_permission, has_permission_in_transaction
from itoms.services import (
    operations, projects, service_inventory, service_requests, assets, training,
)


class ReportingError(ValueError):
    """Invalid or unauthorized reporting operation."""


DATASETS = {
    "service_requests": {
        "label": "Service Requests",
        "fields": ("request_number", "title", "priority", "status", "created_at"),
        "filters": {"status": {"OPEN", "IN_PROGRESS", "ON_HOLD", "COMPLETED", "CANCELLED"}},
    },
    "projects": {
        "label": "Projects",
        "fields": ("project_key", "project_name", "status", "manager_name", "target_end_date", "teams"),
        "filters": {"status": projects.PROJECT_STATUSES},
    },
    "assets": {
        "label": "Assets",
        "fields": ("asset_tag", "asset_name", "asset_type", "team_name", "assignee_name",
                   "asset_status", "location_label"),
        "filters": {"status": assets.ASSET_STATUSES},
    },
    "operations": {
        "label": "Technical Operations",
        "fields": ("work_number", "domain", "title", "team_name", "priority", "status", "created_at"),
        "filters": {"status": operations.WORK_STATUSES, "priority": operations.PRIORITIES,
                    "domain": operations.DOMAINS},
    },
    "services": {
        "label": "Service Inventory",
        "fields": ("service_key", "service_name", "service_type", "team_name",
                   "criticality", "lifecycle_status"),
        "filters": {"status": service_inventory.SERVICE_STATUSES},
    },
    "training": {
        "label": "Training Enrollments",
        "fields": ("enrollment_id", "employee_name", "employee_code", "course_title",
                   "status", "enrolled_at", "completed_at"),
        "filters": {"status": training.ENROLLMENT_STATUSES},
    },
}


def list_reports(*, employee_id: int) -> list[dict]:
    if not has_permission(employee_id, "reports.read"):
        raise ReportingError("Not authorized to read saved reports.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT report_id,report_name,dataset_key,definition,created_at,updated_at
               FROM saved_reports WHERE created_by=%s
               ORDER BY updated_at DESC,report_id DESC""",
            (employee_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def create_report(
    *, employee_id: int, report_name: str, dataset_key: str,
    columns: list[str], filters: dict | None = None,
) -> int:
    name = (report_name or "").strip()
    if not name or len(name) > 150:
        raise ReportingError("Report name is required (maximum 150 characters).")
    dataset = DATASETS.get(dataset_key)
    if not dataset:
        raise ReportingError("Select a supported report dataset.")
    if not columns or len(columns) > len(dataset["fields"]):
        raise ReportingError("Select at least one and no more than the available report fields.")
    if len(set(columns)) != len(columns) or any(column not in dataset["fields"] for column in columns):
        raise ReportingError("One or more selected fields are not available for this dataset.")
    selected_filters = {}
    for key, value in (filters or {}).items():
        if value in (None, ""):
            continue
        allowed = dataset["filters"].get(key)
        if dataset_key == "service_requests" and key == "priority":
            allowed = {
                row["priority_key"] for row in service_requests.list_priorities()
            }
        if allowed is None or value not in allowed:
            raise ReportingError(f"Invalid {key} filter for this report dataset.")
        selected_filters[key] = value
    definition = {"columns": columns, "filters": selected_filters}
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(cur, employee_id, "reports.create", None):
            raise ReportingError("Not authorized to create saved reports.")
        cur.execute(
            """INSERT INTO saved_reports
               (report_name,dataset_key,definition,created_by)
               VALUES (%s,%s,%s,%s)""",
            (name, dataset_key, json.dumps(definition), employee_id),
        )
        report_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'SAVED_REPORT_CREATED','saved_report',%s,'SUCCESS',
                       JSON_OBJECT('dataset_key',%s))""",
            (employee_id, str(report_id), dataset_key),
        )
        conn.commit()
        return report_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def _load_dataset(employee_id: int, dataset_key: str, filters: dict) -> list[dict]:
    if dataset_key == "service_requests":
        return service_requests.list_requests(
            actor_employee_id=employee_id, status=filters.get("status"),
            priority=filters.get("priority"), limit=200,
        )
    if dataset_key == "projects":
        return projects.list_projects(actor_employee_id=employee_id, status=filters.get("status"))
    if dataset_key == "assets":
        return assets.list_assets(actor_employee_id=employee_id, status=filters.get("status"))
    if dataset_key == "operations":
        return operations.list_operational_work_items(
            actor_employee_id=employee_id, domain=filters.get("domain"),
            status=filters.get("status"),
        )
    if dataset_key == "services":
        return service_inventory.list_service_records(
            actor_employee_id=employee_id, lifecycle_status=filters.get("status"),
        )
    if dataset_key == "training":
        return training.list_enrollments(
            actor_employee_id=employee_id,
        ) if not filters.get("status") else [
            row for row in training.list_enrollments(actor_employee_id=employee_id)
            if row["status"] == filters["status"]
        ]
    raise ReportingError("Unsupported report dataset.")


def run_report(*, employee_id: int, report_id: int) -> tuple[str, list[str], list[dict]]:
    """Run an owned saved report using the underlying services' authorization filters."""
    if not has_permission(employee_id, "reports.run"):
        raise ReportingError("Not authorized to run reports.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT report_name,dataset_key,definition FROM saved_reports
               WHERE report_id=%s AND created_by=%s""",
            (report_id, employee_id),
        )
        report = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not report:
        raise ReportingError("Saved report was not found.")
    definition = report["definition"]
    if isinstance(definition, str):
        definition = json.loads(definition)
    dataset_key = report["dataset_key"]
    dataset = DATASETS.get(dataset_key)
    if not dataset:
        raise ReportingError("Saved report dataset is no longer supported.")
    columns = definition.get("columns", [])
    filters = definition.get("filters", {})
    if not columns or any(column not in dataset["fields"] for column in columns):
        raise ReportingError("Saved report definition is invalid.")
    rows = _load_dataset(employee_id, dataset_key, filters)
    projected = [{column: row.get(column) for column in columns} for row in rows[:5000]]
    audit = get_connection()
    audit_cur = audit.cursor()
    try:
        if not has_permission_in_transaction(
            audit_cur, employee_id, "reports.run", None
        ):
            raise ReportingError("Not authorized to run reports.")
        audit_cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'SAVED_REPORT_EXPORTED','saved_report',%s,'SUCCESS',
                       JSON_OBJECT('row_count',%s))""",
            (employee_id, str(report_id), len(projected)),
        )
        audit.commit()
    except Exception:
        audit.rollback()
        raise
    finally:
        audit_cur.close()
        audit.close()
    return report["report_name"], columns, projected


def build_csv(columns: list[str], rows: list[dict]) -> str:
    """Serialize allowlisted report data with spreadsheet formula injection protection."""
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        values = []
        for column in columns:
            value = row.get(column)
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            elif isinstance(value, (list, tuple)):
                value = ", ".join(str(item) for item in value)
            elif value is None:
                value = ""
            else:
                value = str(value)
            if value.startswith(("=", "+", "-", "@", "\t", "\r")):
                value = "'" + value
            values.append(value)
        writer.writerow(values)
    return output.getvalue()
