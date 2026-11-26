"""Authentication service primitives backed by MySQL and Werkzeug password hashing."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import secrets
from werkzeug.security import check_password_hash, generate_password_hash
from itoms.db.connection import get_connection
from itoms.security.tokens import generate_token, token_digest

MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15
IDLE_TIMEOUT_MINUTES = 60

class AuthenticationError(ValueError):
    """Authentication could not be completed."""

def hash_password(password: str) -> str:
    return generate_password_hash(password, method="scrypt")

def verify_password(password_hash: str, password: str) -> bool:
    return check_password_hash(password_hash, password)

def authenticate(username: str, password: str, *, ip_address: str | None = None,
                 user_agent: str | None = None) -> tuple[int, str, bool] | None:
    """Verify credentials, enforce lockout and create a server-side session."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT account_id, password_hash, account_status, failed_login_count,
            locked_until, session_version, must_change_password
            FROM user_accounts WHERE username=%s FOR UPDATE""", (username,))
        row = cur.fetchone()
        if not row or row[2] != "ACTIVE":
            cur.execute("""INSERT INTO authentication_events
                (account_id,username_attempted,event_type,ip_address,user_agent)
                VALUES (%s,%s,'LOGIN_FAILURE',%s,%s)""",
                (row[0] if row else None, username, ip_address, user_agent))
            conn.commit()
            return None
        account_id, password_hash, status, failed, locked_until, version, must_change = row
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if locked_until and locked_until > now:
            cur.execute("""INSERT INTO authentication_events
                (account_id,username_attempted,event_type,ip_address,user_agent)
                VALUES (%s,%s,'LOCKOUT',%s,%s)""", (account_id, username, ip_address, user_agent))
            conn.commit()
            return None
        if not verify_password(password_hash, password):
            failed += 1
            lock_until = now + timedelta(minutes=LOCKOUT_MINUTES) if failed >= MAX_FAILED_LOGINS else None
            cur.execute("""UPDATE user_accounts SET failed_login_count=%s, locked_until=%s
                WHERE account_id=%s""", (failed, lock_until, account_id))
            cur.execute("""INSERT INTO authentication_events
                (account_id,username_attempted,event_type,ip_address,user_agent)
                VALUES (%s,%s,%s,%s,%s)""",
                (account_id, username, "LOCKOUT" if lock_until else "LOGIN_FAILURE", ip_address, user_agent))
            conn.commit()
            return None
        raw_token = generate_token()
        cur.execute("""UPDATE user_accounts SET failed_login_count=0, locked_until=NULL,
            last_login_at=UTC_TIMESTAMP() WHERE account_id=%s""", (account_id,))
        cur.execute("""INSERT INTO user_sessions
            (account_id,token_hash,session_version,last_activity_at,expires_at,ip_address,user_agent)
            VALUES (%s,%s,%s,UTC_TIMESTAMP(),DATE_ADD(UTC_TIMESTAMP(), INTERVAL 60 MINUTE),%s,%s)""",
            (account_id, token_digest(raw_token), version, ip_address, user_agent))
        cur.execute("""INSERT INTO authentication_events
            (account_id,username_attempted,event_type,ip_address,user_agent)
            VALUES (%s,%s,'LOGIN_SUCCESS',%s,%s)""", (account_id, username, ip_address, user_agent))
        conn.commit()
        return account_id, raw_token, bool(must_change)
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def validate_session(raw_token: str) -> int | None:
    """Validate session version, account state, revocation and idle timeout."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""SELECT s.account_id FROM user_sessions s
            JOIN user_accounts a ON a.account_id=s.account_id
            WHERE s.token_hash=%s AND s.revoked_at IS NULL
            AND s.expires_at>UTC_TIMESTAMP()
            AND s.last_activity_at>DATE_SUB(UTC_TIMESTAMP(), INTERVAL 60 MINUTE)
            AND s.session_version=a.session_version AND a.account_status='ACTIVE'""",
            (token_digest(raw_token),))
        row = cur.fetchone()
        if not row:
            return None
        cur.execute("UPDATE user_sessions SET last_activity_at=UTC_TIMESTAMP(), expires_at=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 60 MINUTE) WHERE token_hash=%s", (token_digest(raw_token),))
        conn.commit()
        return row[0]
    finally:
        cur.close()
        conn.close()

def revoke_session(raw_token: str) -> None:
    """Revoke one session without affecting other active sessions."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""UPDATE user_sessions SET revoked_at=UTC_TIMESTAMP(), revoke_reason='USER_LOGOUT'
            WHERE token_hash=%s AND revoked_at IS NULL""", (token_digest(raw_token),))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
