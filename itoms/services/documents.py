"""Secure document upload, quarantine, scan gating and download primitives."""
from __future__ import annotations

import hashlib
import os
import re
import socket
import uuid
import zipfile
from io import BytesIO
from pathlib import Path

from flask import current_app

from itoms.db.connection import get_connection
from itoms.services.authorization import ResourceContext, has_permission


class DocumentError(ValueError):
    """Invalid, unavailable or unauthorized document operation."""


MAX_FILE_BYTES = 10 * 1024 * 1024
CLASSIFICATIONS = {"PUBLIC", "INTERNAL", "RESTRICTED", "CONFIDENTIAL"}


def detect_file_type(filename: str, content: bytes) -> tuple[str, str] | None:
    """Detect a small safe set of types using signatures and container structure."""
    safe_name = (filename or "").replace("\\", "/").split("/")[-1]
    extension = Path(safe_name).suffix.lower().lstrip(".")
    if not extension or not content:
        return None
    if extension == "pdf" and content.startswith(b"%PDF-"):
        return extension, "application/pdf"
    if extension == "png" and content.startswith(b"\x89PNG\r\n\x1a\n"):
        return extension, "image/png"
    if extension in {"jpg", "jpeg"} and content.startswith(b"\xff\xd8\xff"):
        return extension, "image/jpeg"
    if extension == "gif" and content[:6] in {b"GIF87a", b"GIF89a"}:
        return extension, "image/gif"
    if extension == "txt":
        try:
            content.decode("utf-8")
            if b"\x00" not in content:
                return extension, "text/plain"
        except UnicodeDecodeError:
            return None
    office_types = {
        "docx": ("word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        "xlsx": ("xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "pptx": ("ppt/presentation.xml", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    }
    if extension in office_types and content.startswith(b"PK"):
        expected, mime = office_types[extension]
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
                if "[Content_Types].xml" in names and expected in names:
                    return extension, mime
        except (zipfile.BadZipFile, OSError, ValueError):
            return None
    return None


def parse_icap_verdict(response: bytes) -> tuple[str, str]:
    """Fail closed: only ICAP 204 (no modification, no infection) is accepted as clean."""
    header = response.split(b"\r\n\r\n", 1)[0].decode("latin-1", errors="replace")
    first = header.splitlines()[0] if header else ""
    if re.match(r"^ICAP/1\.[0-9]\s+204(?:\s|$)", first):
        return "CLEAN", "Trend Micro ICAP returned 204 No Modification."
    if re.match(r"^ICAP/1\.[0-9]\s+200(?:\s|$)", first):
        return "INFECTED", "Trend Micro ICAP modified or blocked the submitted content."
    return "ERROR", "Trend Micro ICAP returned an unsupported or malformed response."


def scan_with_trend_micro(content: bytes) -> dict:
    """Submit content to a configured Trend Micro ICAP RESPmod service."""
    host = current_app.config.get("TREND_MICRO_ICAP_HOST")
    port = int(current_app.config.get("TREND_MICRO_ICAP_PORT", 1344))
    service = current_app.config.get("TREND_MICRO_ICAP_SERVICE", "avscan")
    timeout = float(current_app.config.get("TREND_MICRO_ICAP_TIMEOUT", 15))
    if not host:
        return {"status": "ERROR", "details": "Trend Micro ICAP scanner is not configured."}
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", service):
        return {"status": "ERROR", "details": "Trend Micro ICAP service name is invalid."}
    req_header = b"GET / HTTP/1.1\r\nHost: itoms.local\r\n\r\n"
    res_header = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: "
        + str(len(content)).encode("ascii") + b"\r\n\r\n"
    )
    encapsulated = (
        f"Encapsulated: req-hdr=0, res-hdr={len(req_header)}, "
        f"res-body={len(req_header) + len(res_header)}\r\n"
    ).encode("ascii")
    icap_header = (
        f"RESPMOD icap://{host}:{port}/{service} ICAP/1.0\r\n"
        f"Host: {host}\r\nAllow: 204\r\n".encode("ascii")
        + encapsulated + b"\r\n"
    )
    body = (
        req_header + res_header + f"{len(content):X}\r\n".encode("ascii")
        + content + b"\r\n0\r\n\r\n"
    )
    try:
        with socket.create_connection((host, port), timeout=timeout) as client:
            client.settimeout(timeout)
            client.sendall(icap_header + body)
            response = bytearray()
            while b"\r\n\r\n" not in response and len(response) < 65536:
                chunk = client.recv(4096)
                if not chunk:
                    break
                response.extend(chunk)
        status, details = parse_icap_verdict(bytes(response))
        return {"status": status, "details": details}
    except (OSError, ValueError, TimeoutError) as exc:
        return {"status": "ERROR", "details": f"Trend Micro ICAP scan failed: {type(exc).__name__}."}


def _storage_root() -> Path:
    configured = current_app.config.get("DOCUMENT_STORAGE_ROOT")
    if not configured:
        raise DocumentError("Document storage is not configured.")
    root = Path(configured).expanduser().resolve()
    app_root = Path(current_app.root_path).resolve()
    try:
        root.relative_to(app_root)
    except ValueError:
        pass
    else:
        raise DocumentError("Document storage must be outside the application web root.")
    static_folder = current_app.static_folder
    if static_folder:
        static_root = Path(static_folder).resolve()
        try:
            root.relative_to(static_root)
        except ValueError:
            pass
        else:
            raise DocumentError("Document storage must be outside the static web directory.")
    return root


def _safe_storage_path(storage_key: str) -> Path:
    if not re.fullmatch(r"files/[a-f0-9]{32}", storage_key or ""):
        raise DocumentError("Document storage reference is invalid.")
    root = _storage_root()
    path = (root / storage_key).resolve()
    if root not in path.parents:
        raise DocumentError("Document storage reference is invalid.")
    return path


def list_allowed_file_types(*, actor_employee_id: int) -> list[dict]:
    if not has_permission(actor_employee_id, "document.allowlist.manage"):
        raise DocumentError("Not authorized to manage document file types.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT extension,mime_type,description,is_active
               FROM document_file_type_allowlist ORDER BY extension"""
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def set_file_type_allowlist(
    *, actor_employee_id: int, extension: str, mime_type: str,
    description: str = "", is_active: bool = True,
) -> None:
    if not has_permission(actor_employee_id, "document.allowlist.manage"):
        raise DocumentError("Not authorized to manage document file types.")
    extension = (extension or "").strip().lower().lstrip(".")
    mime_type = (mime_type or "").strip().lower()
    description = (description or "").strip()
    if not re.fullmatch(r"[a-z0-9]{1,12}", extension):
        raise DocumentError("File extension must contain 1–12 letters or digits.")
    if not re.fullmatch(r"[a-z0-9.+-]+/[a-z0-9.+-]+", mime_type):
        raise DocumentError("Enter a valid MIME type.")
    if len(description) > 200:
        raise DocumentError("File type description is too long.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO document_file_type_allowlist
               (extension,mime_type,description,is_active)
               VALUES (%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE mime_type=VALUES(mime_type),
                 description=VALUES(description),is_active=VALUES(is_active)""",
            (extension, mime_type, description or None, bool(is_active)),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'DOCUMENT_FILE_TYPE_ALLOWLIST_UPDATED','document_file_type',%s,'SUCCESS',
                       JSON_OBJECT('mime_type',%s,'is_active',%s))""",
            (actor_employee_id, extension, mime_type, bool(is_active)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def upload_document(
    *, actor_employee_id: int, filename: str, content: bytes,
    classification: str = "INTERNAL",
) -> dict:
    if not has_permission(actor_employee_id, "document.upload"):
        raise DocumentError("Not authorized to upload documents.")
    if classification not in CLASSIFICATIONS:
        raise DocumentError("Invalid document classification.")
    if not isinstance(content, bytes) or not content or len(content) > MAX_FILE_BYTES:
        raise DocumentError("Document must be non-empty and no larger than 10 MiB.")
    raw_name = (filename or "").replace("\\", "/").split("/")[-1]
    if (not raw_name or len(raw_name) > 255
            or any(ord(char) < 32 or ord(char) == 127 for char in raw_name)):
        raise DocumentError("Document filename is invalid.")
    detected = detect_file_type(raw_name, content)
    if not detected:
        raise DocumentError("File signature is unsupported or does not match its extension.")
    extension, mime_type = detected

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT 1 FROM document_file_type_allowlist
               WHERE extension=%s AND mime_type=%s AND is_active=TRUE""",
            (extension, mime_type),
        )
        if not cur.fetchone():
            raise DocumentError("This file type is not enabled by the administrator.")
    finally:
        cur.close()
        conn.close()

    scan = scan_with_trend_micro(content)
    scan_status = scan.get("status", "ERROR")
    if scan_status not in {"CLEAN", "INFECTED", "ERROR"}:
        scan_status = "ERROR"
    lifecycle = "ACTIVE" if scan_status == "CLEAN" else "QUARANTINED"
    opaque_id = str(uuid.uuid4())
    storage_key = f"files/{uuid.uuid4().hex}"
    path = _safe_storage_path(storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    except OSError as exc:
        raise DocumentError("Document could not be stored safely.") from exc

    checksum = hashlib.sha256(content).hexdigest()
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO managed_files
               (opaque_id,original_filename,storage_key,detected_mime_type,
                file_size_bytes,sha256_checksum,classification,scan_status,
                lifecycle_status,uploaded_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (opaque_id, raw_name, storage_key, mime_type, len(content), checksum,
             classification, scan_status, lifecycle, actor_employee_id),
        )
        file_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO managed_file_versions
               (file_id,version_number,storage_key,file_size_bytes,
                sha256_checksum,detected_mime_type,scan_status,uploaded_by)
               VALUES (%s,1,%s,%s,%s,%s,%s,%s)""",
            (file_id, storage_key, len(content), checksum, mime_type, scan_status, actor_employee_id),
        )
        version_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO file_scan_events
               (file_id,file_version_id,scanner_name,scanner_engine_version,scan_result,details)
               VALUES (%s,%s,'Trend Micro ICAP',%s,%s,%s)""",
            (file_id, version_id, scan.get("engine_version"), scan_status,
             (scan.get("details") or "No scanner details.")[:500]),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'DOCUMENT_UPLOADED','managed_file',%s,'SUCCESS',
                       JSON_OBJECT('classification',%s,'scan_status',%s))""",
            (actor_employee_id, str(file_id), classification, scan_status),
        )
        conn.commit()
        return {"file_id": file_id, "scan_status": scan_status, "lifecycle_status": lifecycle}
    except Exception:
        conn.rollback()
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        cur.close()
        conn.close()


def list_documents(*, employee_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT file_id,opaque_id,original_filename,detected_mime_type,
                      file_size_bytes,classification,scan_status,lifecycle_status,
                      uploaded_by,created_at
               FROM managed_files ORDER BY created_at DESC,file_id DESC LIMIT 500"""
        )
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    visible = []
    for row in rows:
        context = ResourceContext(
            owner_employee_id=row["uploaded_by"], resource_type="document",
            resource_id=str(row["file_id"]),
        )
        if has_permission(employee_id, "document.read", context):
            row["can_download"] = (
                row["scan_status"] == "CLEAN"
                and row["lifecycle_status"] == "ACTIVE"
                and has_permission(employee_id, "document.download", context)
            )
            visible.append(row)
    return visible


def download_document(*, employee_id: int, file_id: int) -> tuple[bytes, str, str]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT original_filename,storage_key,detected_mime_type,
                      scan_status,lifecycle_status,uploaded_by
               FROM managed_files WHERE file_id=%s""",
            (file_id,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row:
        raise DocumentError("Document was not found.")
    context = ResourceContext(
        owner_employee_id=row["uploaded_by"], resource_type="document",
        resource_id=str(file_id),
    )
    if not has_permission(employee_id, "document.download", context):
        raise DocumentError("Document was not found.")
    if row["scan_status"] != "CLEAN" or row["lifecycle_status"] != "ACTIVE":
        raise DocumentError("Document is unavailable until a clean scan and active lifecycle are confirmed.")
    path = _safe_storage_path(row["storage_key"])
    try:
        content = path.read_bytes()
    except OSError:
        raise DocumentError("Document content is unavailable.") from None
    if len(content) > MAX_FILE_BYTES:
        raise DocumentError("Stored document exceeds the permitted size.")
    return content, row["original_filename"], row["detected_mime_type"]
