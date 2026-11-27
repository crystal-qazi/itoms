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
        cur.execute("INSERT INTO audit_events (actor_employee_id,event_key,target_type,target_id,outcome) VALUES (%s,'NOTIFICATION_CREATED','notification',%s,'SUCCESS')", (actor_employee_id,str(notification_id)))
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
            FROM notification_outbox WHERE delivery_status='PENDING' AND channel='IN_APP'
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


def count_unread(*, employee_id: int) -> int:
    """Count unread notifications belonging only to the supplied employee."""
    conn = get_connection(); cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM notifications WHERE recipient_employee_id=%s AND read_at IS NULL", (employee_id,))
        return int(cur.fetchone()[0])
    finally:
        cur.close(); conn.close()


def process_in_app_outbox_batch(*, batch_size: int = 25) -> int:
    """Complete queued in-app deliveries; other channels remain untouched until configured."""
    rows = claim_outbox_batch(batch_size=batch_size)
    completed = 0
    for row in rows:
        complete_outbox_item(outbox_id=row["outbox_id"], success=True)
        completed += 1
    return completed


def recover_stale_outbox(
    *, stale_after_seconds: int = 300, max_attempts: int = 8, batch_size: int = 100,
) -> dict:
    """Release abandoned worker claims and retry or dead-letter them safely."""
    stale_after_seconds = max(60, min(int(stale_after_seconds), 86400))
    max_attempts = max(1, min(int(max_attempts), 20))
    batch_size = max(1, min(int(batch_size), 500))
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    recovered = 0
    dead = 0
    try:
        cur.execute(
            """SELECT outbox_id,attempt_count FROM notification_outbox
               WHERE delivery_status='PROCESSING'
                 AND locked_at < DATE_SUB(UTC_TIMESTAMP(), INTERVAL %s SECOND)
               ORDER BY locked_at,outbox_id LIMIT %s FOR UPDATE SKIP LOCKED""",
            (stale_after_seconds, batch_size),
        )
        rows = cur.fetchall()
        for row in rows:
            attempts = int(row["attempt_count"]) + 1
            is_dead = attempts >= max_attempts
            delay = min(3600, 2 ** min(attempts, 10) * 15)
            cur.execute(
                """UPDATE notification_outbox
                   SET delivery_status=%s,attempt_count=%s,
                       available_at=CASE WHEN %s=1 THEN available_at
                           ELSE DATE_ADD(UTC_TIMESTAMP(),INTERVAL %s SECOND) END,
                       locked_at=NULL,last_error=%s
                   WHERE outbox_id=%s AND delivery_status='PROCESSING'""",
                ("DEAD" if is_dead else "PENDING", attempts, int(is_dead), delay,
                 "Recovered stale worker claim", row["outbox_id"]),
            )
            if cur.rowcount:
                recovered += 1
                dead += int(is_dead)
                cur.execute(
                    """INSERT INTO audit_events
                       (actor_employee_id,event_key,target_type,target_id,outcome,details)
                       VALUES (NULL,'NOTIFICATION_OUTBOX_RECOVERED','notification_outbox',%s,'SUCCESS',
                               JSON_OBJECT('attempt_count',%s,'dead_lettered',%s))""",
                    (str(row["outbox_id"]), attempts, bool(is_dead)),
                )
        conn.commit()
        return {"recovered": recovered, "dead_lettered": dead}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def replay_dead_letter(*, actor_employee_id: int, outbox_id: int) -> None:
    """Audited, permission-controlled replay of one dead-lettered outbox row."""
    if not has_permission(actor_employee_id, "notifications.outbox.replay"):
        raise NotificationError("Not authorized to replay notification outbox items.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT delivery_status FROM notification_outbox WHERE outbox_id=%s FOR UPDATE",
            (outbox_id,),
        )
        row = cur.fetchone()
        if not row or row[0] != "DEAD":
            raise NotificationError("Outbox item is not in the dead-letter queue.")
        cur.execute(
            """UPDATE notification_outbox SET delivery_status='PENDING',
               attempt_count=0,available_at=UTC_TIMESTAMP(),locked_at=NULL,
               last_error=NULL,sent_at=NULL WHERE outbox_id=%s""",
            (outbox_id,),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome)
               VALUES (%s,'NOTIFICATION_OUTBOX_REPLAYED','notification_outbox',%s,'SUCCESS')""",
            (actor_employee_id, str(outbox_id)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
