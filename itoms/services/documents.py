"""Secure document upload, quarantine, scan gating and download primitives."""
from __future__ import annotations

import hashlib
import os
import re
import socket
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
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
    root = _storage_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
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
            """SELECT f.file_id,f.opaque_id,f.original_filename,f.detected_mime_type,
                      f.file_size_bytes,f.classification,f.scan_status,f.lifecycle_status,
                      f.uploaded_by,f.created_at,
                      EXISTS(SELECT 1 FROM managed_file_shares s
                             WHERE s.file_id=f.file_id AND s.shared_with_employee_id=%s
                               AND s.permission='DOWNLOAD' AND s.revoked_at IS NULL
                               AND s.expires_at>UTC_TIMESTAMP()) AS shared_download
               FROM managed_files f ORDER BY f.created_at DESC,f.file_id DESC LIMIT 500""",
            (employee_id,),
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
        can_read = has_permission(employee_id, "document.read", context) or bool(row["shared_download"])
        if can_read:
            row["can_download"] = (
                row["scan_status"] == "CLEAN"
                and row["lifecycle_status"] == "ACTIVE"
                and (bool(row["shared_download"]) or has_permission(employee_id, "document.download", context))
            )
            row["can_share"] = has_permission(employee_id, "document.share", context)
            row["can_version"] = has_permission(employee_id, "document.version.manage", context)
            visible.append(row)
    return visible


def download_document(*, employee_id: int, file_id: int) -> tuple[bytes, str, str]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT f.original_filename,f.storage_key,f.detected_mime_type,f.sha256_checksum,
                      f.scan_status,f.lifecycle_status,f.uploaded_by,
                      EXISTS(SELECT 1 FROM managed_file_shares s
                             WHERE s.file_id=f.file_id AND s.shared_with_employee_id=%s
                               AND s.permission='DOWNLOAD' AND s.revoked_at IS NULL
                               AND s.expires_at>UTC_TIMESTAMP()) AS shared_download
               FROM managed_files f WHERE f.file_id=%s""",
            (employee_id, file_id),
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
    if not row["shared_download"] and not has_permission(employee_id, "document.download", context):
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
    if hashlib.sha256(content).hexdigest() != row["sha256_checksum"]:
        raise DocumentError("Stored document integrity check failed.")
    return content, row["original_filename"], row["detected_mime_type"]


def _validate_document_payload(filename: str, content: bytes) -> tuple[str, str, str]:
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
    return raw_name, extension, mime_type


def _store_scanned_version(
    *, actor_employee_id: int, file_id: int, filename: str, content: bytes,
    classification: str,
) -> dict:
    raw_name, _extension, mime_type = _validate_document_payload(filename, content)
    scan = scan_with_trend_micro(content)
    scan_status = scan.get("status", "ERROR")
    if scan_status not in {"CLEAN", "INFECTED", "ERROR"}:
        scan_status = "ERROR"
    lifecycle = "ACTIVE" if scan_status == "CLEAN" else "QUARANTINED"
    storage_key = f"files/{uuid.uuid4().hex}"
    path = _safe_storage_path(storage_key)
    root = _storage_root()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
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
        cur.execute("SELECT file_id FROM managed_files WHERE file_id=%s FOR UPDATE", (file_id,))
        if not cur.fetchone():
            raise DocumentError("Document was not found.")
        cur.execute(
            "SELECT COALESCE(MAX(version_number),0)+1 FROM managed_file_versions WHERE file_id=%s",
            (file_id,),
        )
        version_number = int(cur.fetchone()[0])
        cur.execute(
            """INSERT INTO managed_file_versions
               (file_id,version_number,storage_key,file_size_bytes,
                sha256_checksum,detected_mime_type,scan_status,uploaded_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (file_id, version_number, storage_key, len(content), checksum,
             mime_type, scan_status, actor_employee_id),
        )
        version_id = int(cur.lastrowid)
        cur.execute(
            """UPDATE managed_files SET original_filename=%s,storage_key=%s,
               detected_mime_type=%s,file_size_bytes=%s,sha256_checksum=%s,
               classification=%s,scan_status=%s,lifecycle_status=%s
               WHERE file_id=%s""",
            (raw_name, storage_key, mime_type, len(content), checksum,
             classification, scan_status, lifecycle, file_id),
        )
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
               VALUES (%s,'DOCUMENT_VERSION_UPLOADED','managed_file',%s,'SUCCESS',
                       JSON_OBJECT('version_number',%s,'scan_status',%s))""",
            (actor_employee_id, str(file_id), version_number, scan_status),
        )
        conn.commit()
        return {"file_id": file_id, "version_number": version_number,
                "scan_status": scan_status, "lifecycle_status": lifecycle}
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


def upload_document_version(
    *, actor_employee_id: int, file_id: int, filename: str, content: bytes,
) -> dict:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT uploaded_by,classification,lifecycle_status
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
    if not has_permission(actor_employee_id, "document.version.manage", context):
        raise DocumentError("Document was not found.")
    if row["lifecycle_status"] != "ACTIVE":
        raise DocumentError("Only active documents can receive a new version.")
    return _store_scanned_version(
        actor_employee_id=actor_employee_id, file_id=file_id,
        filename=filename, content=content, classification=row["classification"],
    )


def create_document_share(
    *, actor_employee_id: int, file_id: int, recipient_employee_id: int,
    permission: str, expires_at: str, approval_request_id: int | None = None,
) -> int:
    if permission != "DOWNLOAD":
        raise DocumentError("Only explicit DOWNLOAD shares are currently supported.")
    try:
        expiry = datetime.fromisoformat(expires_at)
    except (TypeError, ValueError):
        raise DocumentError("Share expiry must be a valid ISO date and time.") from None
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    expiry = expiry.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    if expiry <= now or expiry > now + timedelta(days=365):
        raise DocumentError("Share expiry must be in the future and within 365 days.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT uploaded_by,classification,scan_status,lifecycle_status
               FROM managed_files WHERE file_id=%s""",
            (file_id,),
        )
        file_row = cur.fetchone()
        if not file_row:
            raise DocumentError("Document was not found.")
        context = ResourceContext(
            owner_employee_id=file_row["uploaded_by"], resource_type="document",
            resource_id=str(file_id),
        )
        if not has_permission(actor_employee_id, "document.share", context):
            raise DocumentError("Document was not found.")
        if file_row["scan_status"] != "CLEAN" or file_row["lifecycle_status"] != "ACTIVE":
            raise DocumentError("Only clean active documents can be shared.")
        cur.execute(
            "SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE",
            (recipient_employee_id,),
        )
        if not cur.fetchone():
            raise DocumentError("Share recipient is inactive or unavailable.")
        if file_row["classification"] in {"RESTRICTED", "CONFIDENTIAL"}:
            if not approval_request_id:
                raise DocumentError("Restricted and confidential shares require an approved approval request.")
            cur.execute(
                """SELECT 1 FROM approval_requests
                   WHERE approval_request_id=%s AND requested_by=%s
                     AND request_type='DOCUMENT_SHARE' AND resource_type='managed_file'
                     AND resource_id=%s AND status='APPROVED'""",
                (approval_request_id, actor_employee_id, str(file_id)),
            )
            if not cur.fetchone():
                raise DocumentError("A matching approved document-share request is required.")
        elif approval_request_id is not None:
            raise DocumentError("Approval request is only accepted for restricted or confidential shares.")
        cur.execute(
            """INSERT INTO managed_file_shares
               (file_id,shared_with_employee_id,shared_by_employee_id,permission,
                expires_at,approval_request_id)
               VALUES (%s,%s,%s,'DOWNLOAD',%s,%s)""",
            (file_id, recipient_employee_id, actor_employee_id, expiry.replace(tzinfo=None), approval_request_id),
        )
        share_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'DOCUMENT_SHARED','managed_file_share',%s,'SUCCESS',
                       JSON_OBJECT('file_id',%s,'recipient_employee_id',%s,
                                   'expires_at',%s,'approval_request_id',%s))""",
            (actor_employee_id, str(share_id), file_id, recipient_employee_id,
             expiry.isoformat(), approval_request_id),
        )
        conn.commit()
        return share_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def revoke_document_share(*, actor_employee_id: int, share_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT s.file_id,f.uploaded_by FROM managed_file_shares s
               JOIN managed_files f ON f.file_id=s.file_id
               WHERE s.share_id=%s FOR UPDATE""",
            (share_id,),
        )
        row = cur.fetchone()
        if not row:
            raise DocumentError("Document share was not found.")
        context = ResourceContext(
            owner_employee_id=row["uploaded_by"], resource_type="document",
            resource_id=str(row["file_id"]),
        )
        if not has_permission(actor_employee_id, "document.share", context):
            raise DocumentError("Document share was not found.")
        cur.execute(
            "UPDATE managed_file_shares SET revoked_at=UTC_TIMESTAMP() WHERE share_id=%s AND revoked_at IS NULL",
            (share_id,),
        )
        if cur.rowcount:
            cur.execute(
                """INSERT INTO audit_events
                   (actor_employee_id,event_key,target_type,target_id,outcome)
                   VALUES (%s,'DOCUMENT_SHARE_REVOKED','managed_file_share',%s,'SUCCESS')""",
                (actor_employee_id, str(share_id)),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def list_document_shares(*, employee_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT s.share_id,s.file_id,f.original_filename,
                      s.shared_with_employee_id,e.full_name AS recipient_name,
                      s.permission,s.expires_at,s.revoked_at,
                      (s.revoked_at IS NULL AND s.expires_at>UTC_TIMESTAMP()) AS is_active
               FROM managed_file_shares s
               JOIN managed_files f ON f.file_id=s.file_id
               JOIN employees e ON e.employee_id=s.shared_with_employee_id
               WHERE f.uploaded_by=%s
               ORDER BY s.created_at DESC,s.share_id DESC LIMIT 500""",
            (employee_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def list_document_versions(*, employee_id: int, file_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT uploaded_by FROM managed_files WHERE file_id=%s",
            (file_id,),
        )
        owner = cur.fetchone()
        if not owner:
            raise DocumentError("Document was not found.")
        context = ResourceContext(
            owner_employee_id=owner["uploaded_by"], resource_type="document",
            resource_id=str(file_id),
        )
        if not has_permission(employee_id, "document.read", context):
            raise DocumentError("Document was not found.")
        cur.execute(
            """SELECT file_version_id,version_number,file_size_bytes,
                      detected_mime_type,scan_status,created_at
               FROM managed_file_versions WHERE file_id=%s
               ORDER BY version_number DESC""",
            (file_id,),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def archive_document(*, actor_employee_id: int, file_id: int) -> None:
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            "SELECT uploaded_by,lifecycle_status FROM managed_files WHERE file_id=%s FOR UPDATE",
            (file_id,),
        )
        row = cur.fetchone()
        if not row:
            raise DocumentError("Document was not found.")
        context = ResourceContext(
            owner_employee_id=row["uploaded_by"], resource_type="document",
            resource_id=str(file_id),
        )
        if not has_permission(actor_employee_id, "document.archive", context):
            raise DocumentError("Document was not found.")
        if row["lifecycle_status"] not in {"ACTIVE", "QUARANTINED"}:
            raise DocumentError("Only active or quarantined documents can be archived.")
        cur.execute(
            "UPDATE managed_files SET lifecycle_status='ARCHIVED' WHERE file_id=%s",
            (file_id,),
        )
        cur.execute(
            "UPDATE managed_file_shares SET revoked_at=UTC_TIMESTAMP() WHERE file_id=%s AND revoked_at IS NULL",
            (file_id,),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'DOCUMENT_ARCHIVED','managed_file',%s,'SUCCESS')""",
            (actor_employee_id, str(file_id)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def permanently_delete_document(
    *, actor_employee_id: int, file_id: int, approval_request_id: int,
) -> None:
    """Two-phase, approval-gated deletion; failed filesystem cleanup remains blocked as PENDING_DELETE."""
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT uploaded_by,lifecycle_status FROM managed_files
               WHERE file_id=%s FOR UPDATE""",
            (file_id,),
        )
        row = cur.fetchone()
        if not row:
            raise DocumentError("Document was not found.")
        context = ResourceContext(
            owner_employee_id=row["uploaded_by"], resource_type="document",
            resource_id=str(file_id),
        )
        if not has_permission(actor_employee_id, "document.delete", context):
            raise DocumentError("Document was not found.")
        cur.execute(
            """SELECT 1 FROM approval_requests
               WHERE approval_request_id=%s AND requested_by=%s
                 AND request_type='DOCUMENT_DELETE' AND resource_type='managed_file'
                 AND resource_id=%s AND status='APPROVED'""",
            (approval_request_id, actor_employee_id, str(file_id)),
        )
        if not cur.fetchone():
            raise DocumentError("A matching approved document-deletion request is required.")
        cur.execute(
            "UPDATE managed_files SET lifecycle_status='PENDING_DELETE' WHERE file_id=%s",
            (file_id,),
        )
        cur.execute(
            "UPDATE managed_file_shares SET revoked_at=UTC_TIMESTAMP() WHERE file_id=%s AND revoked_at IS NULL",
            (file_id,),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'DOCUMENT_DELETE_APPROVED','managed_file',%s,'SUCCESS')""",
            (actor_employee_id, str(file_id)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

    lookup = get_connection()
    lookup_cur = lookup.cursor()
    try:
        lookup_cur.execute(
            "SELECT storage_key FROM managed_file_versions WHERE file_id=%s",
            (file_id,),
        )
        storage_keys = {row[0] for row in lookup_cur.fetchall()}
        lookup_cur.execute("SELECT storage_key FROM managed_files WHERE file_id=%s", (file_id,))
        current = lookup_cur.fetchone()
        if current:
            storage_keys.add(current[0])
    finally:
        lookup_cur.close()
        lookup.close()
    for storage_key in storage_keys:
        path = _safe_storage_path(storage_key)
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise DocumentError("Document is blocked as PENDING_DELETE; filesystem cleanup must be retried.") from exc

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT lifecycle_status FROM managed_files WHERE file_id=%s FOR UPDATE",
            (file_id,),
        )
        state = cur.fetchone()
        if not state or state[0] != "PENDING_DELETE":
            raise DocumentError("Document deletion state changed; retry after review.")
        cur.execute("DELETE FROM managed_file_shares WHERE file_id=%s", (file_id,))
        cur.execute("DELETE FROM file_scan_events WHERE file_id=%s", (file_id,))
        cur.execute("DELETE FROM managed_file_versions WHERE file_id=%s", (file_id,))
        cur.execute("DELETE FROM managed_files WHERE file_id=%s", (file_id,))
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'DOCUMENT_PERMANENTLY_DELETED','managed_file',%s,'SUCCESS')""",
            (actor_employee_id, str(file_id)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
