"""Structured audit event writer. Caller must supply sanitized details."""
from __future__ import annotations
import json
from itoms.db.connection import get_connection

def record_event(*, event_key: str, actor_employee_id: int | None = None,
                 target_type: str | None = None, target_id: str | None = None,
                 outcome: str = "SUCCESS", request_id: str | None = None,
                 details: dict | None = None) -> None:
    """Persist a security/administrative event; never pass secret material."""
    if outcome not in {"SUCCESS", "FAILURE", "DENIED"}:
        raise ValueError("Invalid audit outcome.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO audit_events
            (actor_employee_id,event_key,target_type,target_id,outcome,request_id,details)
            VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (actor_employee_id,event_key,target_type,target_id,outcome,request_id,
             json.dumps(details, separators=(",", ":")) if details is not None else None),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
