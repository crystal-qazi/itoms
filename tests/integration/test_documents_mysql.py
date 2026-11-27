"""MySQL integration coverage for scan-gated document upload and download."""
from __future__ import annotations

import os
import tempfile
import shutil
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ITOMS_RUN_MYSQL_INTEGRATION") != "1",
    reason="requires the dedicated MySQL integration database",
)


@pytest.fixture()
def document_fixture(monkeypatch):
    from itoms import create_app
    from itoms.config import Config
    from itoms.db.connection import get_connection
    from itoms.services import documents

    storage = tempfile.mkdtemp(prefix="itoms-doc-test-")
    class MySQLTestConfig(Config):
        TESTING = True
        SECRET_KEY = "mysql-integration-only"
        DB_HOST = os.environ["ITOMS_DB_HOST"]
        DB_PORT = int(os.environ.get("ITOMS_DB_PORT", "3306"))
        DB_NAME = os.environ["ITOMS_DB_NAME"]
        DB_USER = os.environ["ITOMS_DB_USER"]
        DB_PASSWORD = os.environ["ITOMS_DB_PASSWORD"]
        DOCUMENT_STORAGE_ROOT = storage

    app = create_app(MySQLTestConfig)
    context = app.app_context()
    context.push()
    suffix = uuid.uuid4().hex[:12]
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO departments (department_name) VALUES (%s)", (f"Document Test {suffix}",))
        department_id = int(cursor.lastrowid)
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"DOC-{suffix}", f"Document Test Employee {suffix}", department_id),
        )
        employee_id = int(cursor.lastrowid)
        cursor.execute(
            "INSERT INTO application_roles (role_name,description) VALUES (%s,%s)",
            (f"Document Test Role {suffix}", "Temporary integration role"),
        )
        role_id = int(cursor.lastrowid)
        for key in ("document.upload", "document.read", "document.download", "document.allowlist.manage",
                    "document.share", "document.version.manage"):
            cursor.execute("SELECT permission_id FROM permissions WHERE permission_key=%s", (key,))
            permission = cursor.fetchone()
            assert permission, f"{key} must be seeded by migrations"
            cursor.execute("INSERT INTO role_permissions (role_id,permission_id) VALUES (%s,%s)", (role_id, permission[0]))
        cursor.execute(
            """INSERT INTO employee_role_assignments
               (employee_id,role_id,scope_type,is_active) VALUES (%s,%s,'OWN',TRUE)""",
            (employee_id, role_id),
        )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()

    monkeypatch.setattr(
        documents, "scan_with_trend_micro",
        lambda _content: {"status": "CLEAN", "details": "Integration scanner verdict: CLEAN"},
    )
    data = {"employee_id": employee_id, "department_id": department_id, "role_id": role_id,
            "suffix": suffix, "storage": storage}
    yield data

    cleanup = get_connection()
    cursor = cleanup.cursor()
    try:
        cursor.execute("SELECT file_id FROM managed_files WHERE uploaded_by=%s", (employee_id,))
        file_ids = [int(row[0]) for row in cursor.fetchall()]
        for file_id in file_ids:
            cursor.execute("DELETE FROM managed_file_shares WHERE file_id=%s", (file_id,))
            cursor.execute("DELETE FROM file_scan_events WHERE file_id=%s", (file_id,))
            cursor.execute("DELETE FROM managed_file_versions WHERE file_id=%s", (file_id,))
        if file_ids:
            marks = ",".join(["%s"] * len(file_ids))
            cursor.execute(f"DELETE FROM managed_files WHERE file_id IN ({marks})", tuple(file_ids))
        cursor.execute("DELETE FROM approval_requests WHERE requested_by=%s AND request_type='DOCUMENT_SHARE'", (employee_id,))
        cursor.execute("DELETE FROM employees WHERE employee_code=%s", (f"DOC-R-{suffix}",))
        cursor.execute("DELETE FROM audit_events WHERE actor_employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM employee_role_assignments WHERE employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM role_permissions WHERE role_id=%s", (role_id,))
        cursor.execute("DELETE FROM application_roles WHERE role_id=%s", (role_id,))
        cursor.execute("DELETE FROM employees WHERE employee_id=%s", (employee_id,))
        cursor.execute("DELETE FROM departments WHERE department_id=%s", (department_id,))
        cleanup.commit()
    except Exception:
        cleanup.rollback()
        raise
    finally:
        cursor.close()
        cleanup.close()
        context.pop()
        shutil.rmtree(storage, ignore_errors=True)


def test_clean_document_is_downloadable_and_metadata_is_audited(document_fixture, monkeypatch):
    from itoms.services.documents import upload_document, list_documents, download_document
    from itoms.db.connection import get_connection

    employee_id = document_fixture["employee_id"]
    result = upload_document(
        actor_employee_id=employee_id, filename="report.pdf",
        content=b"%PDF-1.7 safe integration fixture", classification="INTERNAL",
    )
    assert result["scan_status"] == "CLEAN"
    assert result["lifecycle_status"] == "ACTIVE"
    assert any(item["file_id"] == result["file_id"] for item in list_documents(employee_id=employee_id))
    content, filename, mime = download_document(employee_id=employee_id, file_id=result["file_id"])
    assert content.startswith(b"%PDF-")
    assert filename == "report.pdf"
    assert mime == "application/pdf"
    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT scan_status,lifecycle_status FROM managed_files WHERE file_id=%s",
            (result["file_id"],),
        )
        assert cursor.fetchone() == ("CLEAN", "ACTIVE")
    finally:
        cursor.close()
        connection.close()

    from itoms.services import documents
    monkeypatch.setattr(
        documents, "scan_with_trend_micro",
        lambda _content: {"status": "ERROR", "details": "Scanner unavailable"},
    )
    quarantined = upload_document(
        actor_employee_id=employee_id, filename="quarantined.pdf",
        content=b"%PDF-1.7 quarantined integration fixture", classification="CONFIDENTIAL",
    )
    assert quarantined["scan_status"] == "ERROR"
    assert quarantined["lifecycle_status"] == "QUARANTINED"
    with pytest.raises(documents.DocumentError, match="unavailable until a clean scan"):
        download_document(employee_id=employee_id, file_id=quarantined["file_id"])

    monkeypatch.setattr(
        documents, "scan_with_trend_micro",
        lambda _content: {"status": "CLEAN", "details": "Integration scanner verdict: CLEAN"},
    )
    versioned = documents.upload_document_version(
        actor_employee_id=employee_id, file_id=result["file_id"],
        filename="report-v2.pdf", content=b"%PDF-1.7 second version",
    )
    assert versioned["version_number"] == 2
    latest_content, _, _ = download_document(employee_id=employee_id, file_id=result["file_id"])
    assert latest_content == b"%PDF-1.7 second version"

    connection = get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            """INSERT INTO employees (employee_code,full_name,department_id,is_active)
               VALUES (%s,%s,%s,TRUE)""",
            (f"DOC-R-{document_fixture['suffix']}", "Document Share Recipient", document_fixture["department_id"]),
        )
        recipient_id = int(cursor.lastrowid)
        confidential = upload_document(
            actor_employee_id=employee_id, filename="confidential.pdf",
            content=b"%PDF-1.7 confidential integration fixture", classification="CONFIDENTIAL",
        )
        cursor.execute(
            """INSERT INTO approval_requests
               (request_type,resource_type,resource_id,requested_by,status,completed_at)
               VALUES ('DOCUMENT_SHARE','managed_file',%s,%s,'APPROVED',UTC_TIMESTAMP())""",
            (str(confidential["file_id"]), employee_id),
        )
        approval_id = int(cursor.lastrowid)
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    from datetime import datetime, timedelta, timezone
    expiry = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    with pytest.raises(documents.DocumentError, match="require an approved"):
        documents.create_document_share(
            actor_employee_id=employee_id, file_id=confidential["file_id"],
            recipient_employee_id=recipient_id, permission="DOWNLOAD", expires_at=expiry,
        )
    confidential_share_id = documents.create_document_share(
        actor_employee_id=employee_id, file_id=confidential["file_id"],
        recipient_employee_id=recipient_id, permission="DOWNLOAD", expires_at=expiry,
        approval_request_id=approval_id,
    )
    confidential_content, _, _ = documents.download_document(
        employee_id=recipient_id, file_id=confidential["file_id"]
    )
    assert confidential_content.startswith(b"%PDF-")

    # Internal shares need no approval and are revoked independently.
    share_id = documents.create_document_share(
        actor_employee_id=employee_id, file_id=result["file_id"],
        recipient_employee_id=recipient_id, permission="DOWNLOAD", expires_at=expiry,
    )
    shared_content, _, _ = documents.download_document(
        employee_id=recipient_id, file_id=result["file_id"]
    )
    assert shared_content == b"%PDF-1.7 second version"
    documents.revoke_document_share(actor_employee_id=employee_id, share_id=share_id)
    documents.revoke_document_share(actor_employee_id=employee_id, share_id=confidential_share_id)
    with pytest.raises(documents.DocumentError, match="not found"):
        documents.download_document(employee_id=recipient_id, file_id=result["file_id"])
    with pytest.raises(documents.DocumentError, match="not found"):
        documents.download_document(employee_id=recipient_id, file_id=confidential["file_id"])
