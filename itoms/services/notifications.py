"""In-app notifications and durable outbox primitives."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from itoms.db.connection import get_connection
from itoms.services.authorization import has_permission

class NotificationError(ValueError):
    """Notification operation was invalid or unauthorized."""

def create_notification(*, actor_employee_id: int, recipient_employee_id: int,
                        notification_type: str, title: str, body: str,
                        target_type: str | None = None, target_id: str | None = None) -> int:
    """Persist notification and delivery outbox atomically."""
    if not has_permission(actor_employee_id, "notifications.send"):
        raise NotificationError("Not authorized to send notifications.")
    if not title.strip() or not body.strip() or len(title) > 200 or len(notification_type) > 80:
        raise NotificationError("A valid type, title and body are required; title limit is 200 characters.")
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT 1 FROM employees WHERE employee_id=%s AND is_active=TRUE",(recipient_employee_id,))
        if not cur.fetchone():
            raise NotificationError("Recipient is unavailable.")
        cur.execute("""INSERT INTO notifications
            (recipient_employee_id,notification_type,title,body,target_type,target_id)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (recipient_employee_id,notification_type,title.strip(),body.strip(),target_type,target_id))
        notification_id=int(cur.lastrowid)
        cur.execute("INSERT INTO notification_outbox (notification_id,channel) VALUES (%s,'IN_APP')",(notification_id,))
        conn.commit()
        return notification_id
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()

def list_inbox(*, employee_id: int, limit: int = 30, unread_only: bool = False) -> list[dict]:
    """Return only the caller's inbox; clamp page size."""
    limit=max(1,min(int(limit),100))
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        sql="SELECT notification_id,notification_type,title,body,target_type,target_id,created_at,read_at FROM notifications WHERE recipient_employee_id=%s"
        if unread_only: sql += " AND read_at IS NULL"
        sql += " ORDER BY created_at DESC,notification_id DESC LIMIT %s"
        cur.execute(sql,(employee_id,limit))
        return cur.fetchall()
    finally:
        cur.close(); conn.close()

def mark_read(*, employee_id: int, notification_id: int) -> bool:
    """Mark a notification read only for its owner."""
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("""UPDATE notifications SET read_at=UTC_TIMESTAMP()
            WHERE notification_id=%s AND recipient_employee_id=%s AND read_at IS NULL""",
            (notification_id,employee_id))
        conn.commit()
        return cur.rowcount == 1
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()

def claim_outbox_batch(*, batch_size: int = 25) -> list[dict]:
    """Atomically claim due rows for a worker; supports concurrent workers on MySQL 8."""
    batch_size=max(1,min(int(batch_size),100))
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT outbox_id,notification_id,channel,attempt_count
            FROM notification_outbox WHERE delivery_status='PENDING'
            AND available_at<=UTC_TIMESTAMP() ORDER BY outbox_id
            LIMIT %s FOR UPDATE SKIP LOCKED""",(batch_size,))
        rows=cur.fetchall()
        if rows:
            ids=[row["outbox_id"] for row in rows]
            placeholders=",".join(["%s"]*len(ids))
            cur.execute(f"""UPDATE notification_outbox SET delivery_status='PROCESSING',
                locked_at=UTC_TIMESTAMP() WHERE outbox_id IN ({placeholders})""",tuple(ids))
        conn.commit()
        return rows
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()

def complete_outbox_item(*, outbox_id: int, success: bool, error: str | None = None,
                         max_attempts: int = 8) -> None:
    """Complete a claimed row or schedule bounded exponential retry/dead-letter."""
    conn=get_connection(); cur=conn.cursor()
    try:
        cur.execute("SELECT attempt_count,delivery_status FROM notification_outbox WHERE outbox_id=%s FOR UPDATE",(outbox_id,))
        row=cur.fetchone()
        if not row or row[1] != "PROCESSING":
            raise NotificationError("Outbox item is not currently claimed.")
        attempts=row[0]+1
        if success:
            cur.execute("""UPDATE notification_outbox SET delivery_status='SENT',
                attempt_count=%s,sent_at=UTC_TIMESTAMP(),locked_at=NULL,last_error=NULL WHERE outbox_id=%s""",(attempts,outbox_id))
        else:
            dead=attempts>=max_attempts
            delay=min(3600,2**min(attempts,10)*15)
            cur.execute("""UPDATE notification_outbox SET delivery_status=%s,attempt_count=%s,
                available_at=DATE_ADD(UTC_TIMESTAMP(),INTERVAL %s SECOND),locked_at=NULL,last_error=%s
                WHERE outbox_id=%s""",("DEAD" if dead else "PENDING",attempts,delay,(error or "Delivery failed")[:500],outbox_id))
        conn.commit()
    except Exception:
        conn.rollback(); raise
    finally:
        cur.close(); conn.close()
