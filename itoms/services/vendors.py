"""Support-contact-only vendor directory."""
from __future__ import annotations

import re
from urllib.parse import urlparse

from itoms.db.connection import get_connection
from itoms.services.authorization import has_permission, has_permission_in_transaction


class VendorError(ValueError):
    """Invalid or unauthorized vendor directory operation."""


def list_vendors(*, actor_employee_id: int, include_inactive: bool = False) -> list[dict]:
    if not (has_permission(actor_employee_id, "vendor.directory.read")
            or has_permission(actor_employee_id, "vendor.directory.manage")):
        raise VendorError("Not authorized to read the vendor directory.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT vendor_id,vendor_name,service_description,support_email,
                      support_phone,support_portal_url,is_active,created_at
               FROM vendor_directory
               WHERE (%s=TRUE OR is_active=TRUE)
               ORDER BY vendor_name LIMIT 500""",
            (bool(include_inactive),),
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def create_vendor(
    *, actor_employee_id: int, vendor_name: str, service_description: str = "",
    support_email: str = "", support_phone: str = "", support_portal_url: str = "",
) -> int:
    name = (vendor_name or "").strip()
    description = (service_description or "").strip()
    email = (support_email or "").strip()
    phone = (support_phone or "").strip()
    portal = (support_portal_url or "").strip()
    if not name or len(name) > 200:
        raise VendorError("Vendor name is required (maximum 200 characters).")
    if len(description) > 5000 or len(email) > 254 or len(phone) > 50 or len(portal) > 500:
        raise VendorError("One or more vendor contact fields exceed their allowed length.")
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise VendorError("Enter a valid support email address.")
    if portal:
        parsed = urlparse(portal)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
                or re.search(r"(?i)(password|passwd|token|secret|api[_-]?key)\s*=", parsed.query)):
            raise VendorError("Support portal must be HTTPS and must not contain embedded credentials or secret query values.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(cur, actor_employee_id, "vendor.directory.manage", None):
            raise VendorError("Not authorized to manage the vendor directory.")
        cur.execute(
            """SELECT vendor_id FROM vendor_directory
               WHERE LOWER(vendor_name)=LOWER(%s) LIMIT 1""",
            (name,),
        )
        if cur.fetchone():
            raise VendorError("A vendor with this name already exists.")
        cur.execute(
            """INSERT INTO vendor_directory
               (vendor_name,service_description,support_email,support_phone,support_portal_url)
               VALUES (%s,%s,%s,%s,%s)""",
            (name, description or None, email or None, phone or None, portal or None),
        )
        vendor_id = int(cur.lastrowid)
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'VENDOR_DIRECTORY_CREATED','vendor',%s,'SUCCESS')""",
            (actor_employee_id, str(vendor_id)),
        )
        conn.commit()
        return vendor_id
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def set_vendor_active(*, actor_employee_id: int, vendor_id: int, is_active: bool) -> None:
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(cur, actor_employee_id, "vendor.directory.manage", None):
            raise VendorError("Not authorized to manage the vendor directory.")
        cur.execute("SELECT vendor_name FROM vendor_directory WHERE vendor_id=%s FOR UPDATE", (vendor_id,))
        row = cur.fetchone()
        if not row:
            raise VendorError("Vendor was not found.")
        cur.execute("UPDATE vendor_directory SET is_active=%s WHERE vendor_id=%s", (bool(is_active), vendor_id))
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'VENDOR_DIRECTORY_STATUS_CHANGED','vendor',%s,'SUCCESS',
                       JSON_OBJECT('is_active',%s))""",
            (actor_employee_id, str(vendor_id), bool(is_active)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
