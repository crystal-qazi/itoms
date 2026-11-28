"""In-app notifications and durable outbox primitives."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import parseaddr
import smtplib
import ssl

from flask import current_app

from itoms.db.connection import get_connection
from itoms.services.authorization import has_permission, has_permission_in_transaction

class NotificationError(ValueError):
    """Notification operation was invalid or unauthorized."""

def _valid_email_address(value: str | None) -> bool:
    """Accept a single mailbox address without header injection or display-name ambiguity."""
    if not value or any(char in value for char in "\r\n"):
        return False
    address = parseaddr(value.strip())[1]
    if (not address or address != value.strip() or address.count("@") != 1
            or any(char.isspace() for char in address) or len(address) > 254):
        return False
    local_part, domain = address.rsplit("@", 1)
    return bool(local_part and domain)

def create_notification(*, actor_employee_id: int, recipient_employee_id: int,
                        notification_type: str, title: str, body: str,
                        target_type: str | None = None, target_id: str | None = None,
                        channels: tuple[str, ...] | list[str] = ("IN_APP",)) -> int:
    """Persist notification and delivery outbox atomically."""
    if not has_permission(actor_employee_id, "notifications.send"):
        raise NotificationError("Not authorized to send notifications.")
    if not title.strip() or not body.strip() or len(title) > 200 or len(notification_type) > 80:
        raise NotificationError("A valid type, title and body are required; title limit is 200 characters.")
    if not isinstance(channels, (tuple, list)) or not channels:
        raise NotificationError("Select at least one supported notification channel.")
    normalized_channels = tuple(dict.fromkeys(str(channel).upper() for channel in channels))
    if any(channel not in {"IN_APP", "EMAIL"} for channel in normalized_channels):
        raise NotificationError("Unsupported notification delivery channel.")
    conn=get_connection(); cur=conn.cursor()
    try:
        if not has_permission_in_transaction(
            cur, actor_employee_id, "notifications.send", None,
            lock_employee_ids=[recipient_employee_id],
        ):
            raise NotificationError("Not authorized to send notifications.")
        cur.execute("SELECT email FROM employees WHERE employee_id=%s AND is_active=TRUE FOR UPDATE",(recipient_employee_id,))
        recipient = cur.fetchone()
        if not recipient:
            raise NotificationError("Recipient is unavailable.")
        recipient_email = recipient[0]
        if "EMAIL" in normalized_channels and not _valid_email_address(recipient_email):
            raise NotificationError("Recipient does not have a valid email address.")
        cur.execute("""INSERT INTO notifications
            (recipient_employee_id,notification_type,title,body,target_type,target_id)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (recipient_employee_id,notification_type,title.strip(),body.strip(),target_type,target_id))
        notification_id=int(cur.lastrowid)
        for channel in normalized_channels:
            cur.execute(
                "INSERT INTO notification_outbox (notification_id,channel) VALUES (%s,%s)",
                (notification_id, channel),
            )
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

def claim_outbox_batch(*, batch_size: int = 25, channel: str = "IN_APP") -> list[dict]:
    """Atomically claim due rows for one delivery channel on MySQL 8."""
    channel = (channel or "").upper()
    if channel not in {"IN_APP", "EMAIL"}:
        raise NotificationError("Unsupported notification delivery channel.")
    batch_size=max(1,min(int(batch_size),100))
    conn=get_connection(); cur=conn.cursor(dictionary=True)
    try:
        cur.execute("""SELECT outbox_id,notification_id,channel,attempt_count
            FROM notification_outbox WHERE delivery_status='PENDING' AND channel=%s
            AND available_at<=UTC_TIMESTAMP() ORDER BY outbox_id
            LIMIT %s FOR UPDATE SKIP LOCKED""",(channel,batch_size))
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
    rows = claim_outbox_batch(batch_size=batch_size, channel="IN_APP")
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
            """SELECT outbox_id,attempt_count FROM notification_outbox FORCE INDEX (idx_outbox_recovery)
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



def _send_notification_email(notification_id: int) -> None:
    """Send one plain-text notification using the configured authenticated SMTP transport."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT e.email,n.title,n.body FROM notifications n
               JOIN employees e ON e.employee_id=n.recipient_employee_id
               WHERE n.notification_id=%s AND e.is_active=TRUE""",
            (notification_id,),
        )
        row = cur.fetchone()
    finally:
        cur.close()
        conn.close()
    if not row or not _valid_email_address(row[0]):
        raise NotificationError("Notification recipient email is unavailable.")

    host = current_app.config.get("SMTP_HOST")
    port = int(current_app.config.get("SMTP_PORT", 587))
    sender = current_app.config.get("SMTP_FROM")
    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    use_starttls = bool(current_app.config.get("SMTP_USE_STARTTLS", True))
    use_ssl = bool(current_app.config.get("SMTP_USE_SSL", False))
    timeout = float(current_app.config.get("SMTP_TIMEOUT", 15))
    if not host or not _valid_email_address(sender):
        raise NotificationError("SMTP host and a valid sender address must be configured.")
    if use_starttls == use_ssl:
        raise NotificationError("Configure exactly one secure SMTP mode: STARTTLS or implicit TLS.")

    message = EmailMessage()
    message["Subject"] = str(row[1]).replace("\\r", " ").replace("\\n", " ")[:200]
    message["From"] = sender
    message["To"] = row[0]
    message.set_content(str(row[2]))

    context = ssl.create_default_context()
    if use_ssl:
        with smtplib.SMTP_SSL(host, port, timeout=timeout, context=context) as smtp:
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
            if username:
                smtp.login(username, password or "")
            smtp.send_message(message)


def process_email_outbox_batch(*, batch_size: int = 25) -> int:
    """Deliver explicitly queued EMAIL notifications; failures use the shared retry/dead-letter policy."""
    if (not current_app.config.get("SMTP_HOST")
            or not _valid_email_address(current_app.config.get("SMTP_FROM"))):
        raise NotificationError("SMTP is not configured; email outbox items remain queued.")
    use_starttls = bool(current_app.config.get("SMTP_USE_STARTTLS", True))
    use_ssl = bool(current_app.config.get("SMTP_USE_SSL", False))
    if use_starttls == use_ssl:
        raise NotificationError("Configure exactly one secure SMTP mode: STARTTLS or implicit TLS.")
    rows = claim_outbox_batch(batch_size=batch_size, channel="EMAIL")
    sent = 0
    for row in rows:
        try:
            _send_notification_email(int(row["notification_id"]))
        except Exception as exc:
            complete_outbox_item(
                outbox_id=row["outbox_id"], success=False,
                error=f"SMTP delivery failed ({type(exc).__name__}).",
            )
        else:
            complete_outbox_item(outbox_id=row["outbox_id"], success=True)
            sent += 1
    return sent

def replay_dead_letter(*, actor_employee_id: int, outbox_id: int) -> None:
    """Audited, permission-controlled replay of one dead-lettered outbox row."""
    if not has_permission(actor_employee_id, "notifications.outbox.replay"):
        raise NotificationError("Not authorized to replay notification outbox items.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        if not has_permission_in_transaction(
            cur, actor_employee_id, "notifications.outbox.replay", None
        ):
            raise NotificationError("Not authorized to replay notification outbox items.")
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
