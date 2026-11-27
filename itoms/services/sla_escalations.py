"""Configurable incident SLA escalation policies and idempotent monitor."""
from __future__ import annotations

from itoms.db.connection import get_connection
from itoms.services.authorization import has_permission


class SLAEscalationError(ValueError):
    """Invalid or unauthorized SLA escalation operation."""


PRIORITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
SLA_TYPES = {"FIRST_RESPONSE", "RESOLUTION"}


def list_escalation_policies(*, actor_employee_id: int) -> list[dict]:
    if not has_permission(actor_employee_id, "incident.sla.manage"):
        raise SLAEscalationError("Not authorized to manage SLA escalation policies.")
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            """SELECT policy_id,priority,sla_type,escalation_level,
                      after_due_minutes,is_active,updated_at
               FROM incident_sla_escalation_policies
               ORDER BY FIELD(priority,'CRITICAL','HIGH','MEDIUM','LOW'),
                        sla_type,escalation_level"""
        )
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()


def upsert_escalation_policy(
    *, actor_employee_id: int, priority: str, sla_type: str,
    escalation_level: int, after_due_minutes: int, is_active: bool = True,
) -> None:
    if not has_permission(actor_employee_id, "incident.sla.manage"):
        raise SLAEscalationError("Not authorized to manage SLA escalation policies.")
    priority = (priority or "").strip().upper()
    sla_type = (sla_type or "").strip().upper()
    if priority not in PRIORITIES or sla_type not in SLA_TYPES:
        raise SLAEscalationError("Select a valid priority and SLA type.")
    if type(escalation_level) is not int or not 1 <= escalation_level <= 9:
        raise SLAEscalationError("Escalation level must be between 1 and 9.")
    if type(after_due_minutes) is not int or not 1 <= after_due_minutes <= 10080:
        raise SLAEscalationError("Escalation delay must be between 1 and 10,080 minutes.")
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO incident_sla_escalation_policies
               (priority,sla_type,escalation_level,after_due_minutes,is_active)
               VALUES (%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 after_due_minutes=VALUES(after_due_minutes),
                 is_active=VALUES(is_active)""",
            (priority, sla_type, escalation_level, after_due_minutes, bool(is_active)),
        )
        cur.execute(
            """INSERT INTO audit_events
               (actor_employee_id,event_key,target_type,target_id,outcome,details)
               VALUES (%s,'INCIDENT_SLA_POLICY_UPDATED','incident_sla_policy',%s,'SUCCESS',
                       JSON_OBJECT('priority',%s,'sla_type',%s,'level',%s,
                                   'after_due_minutes',%s,'is_active',%s))""",
            (actor_employee_id, f"{priority}:{sla_type}:{escalation_level}",
             priority, sla_type, escalation_level, after_due_minutes, bool(is_active)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def process_sla_escalations(*, batch_size: int = 200) -> dict:
    """Create one in-app escalation per ticket/type/level; repeated runs are idempotent."""
    batch_size = max(1, min(int(batch_size), 1000))
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    events_created = 0
    notifications_created = 0
    try:
        cur.execute(
            """SELECT priority,sla_type,escalation_level,after_due_minutes
               FROM incident_sla_escalation_policies
               WHERE is_active=TRUE
               ORDER BY FIELD(priority,'CRITICAL','HIGH','MEDIUM','LOW'),
                        sla_type,escalation_level"""
        )
        policies = cur.fetchall()
        for policy in policies:
            if policy["sla_type"] == "FIRST_RESPONSE":
                due_column = "first_response_due_at"
                condition = "first_responded_at IS NULL AND status NOT IN ('CLOSED','CANCELLED')"
            else:
                due_column = "resolution_due_at"
                condition = "resolved_at IS NULL AND status NOT IN ('CLOSED','CANCELLED')"
            query = f"""SELECT ticket_id,ticket_number,priority,assigned_employee_id,
                               assigned_team_id,{due_column} AS due_at
                        FROM incident_tickets
                        WHERE priority=%s AND {due_column} IS NOT NULL AND {condition}
                          AND {due_column} <= DATE_SUB(UTC_TIMESTAMP(),INTERVAL %s MINUTE)
                        ORDER BY {due_column},ticket_id LIMIT %s"""
            cur.execute(query, (policy["priority"], policy["after_due_minutes"], batch_size))
            tickets = cur.fetchall()
            for ticket in tickets:
                cur.execute(
                    """INSERT IGNORE INTO incident_sla_escalation_events
                       (ticket_id,sla_type,escalation_level,due_at)
                       VALUES (%s,%s,%s,%s)""",
                    (ticket["ticket_id"], policy["sla_type"],
                     policy["escalation_level"], ticket["due_at"]),
                )
                if cur.rowcount != 1:
                    continue
                events_created += 1
                recipients = set()
                if ticket["assigned_employee_id"]:
                    cur.execute(
                        "SELECT employee_id FROM employees WHERE employee_id=%s AND is_active=TRUE",
                        (ticket["assigned_employee_id"],),
                    )
                    row = cur.fetchone()
                    if row:
                        recipients.add(int(row["employee_id"]))
                if ticket["assigned_team_id"]:
                    cur.execute(
                        """SELECT m.manager_employee_id
                           FROM team_management_assignments m
                           JOIN employees e ON e.employee_id=m.manager_employee_id
                           WHERE m.team_id=%s AND e.is_active=TRUE""",
                        (ticket["assigned_team_id"],),
                    )
                    recipients.update(int(row["manager_employee_id"]) for row in cur.fetchall())
                sla_label = "first response" if policy["sla_type"] == "FIRST_RESPONSE" else "resolution"
                title = f"Incident SLA escalation: {ticket['ticket_number']}"
                body = (
                    f"Priority {ticket['priority']} incident {ticket['ticket_number']} "
                    f"has exceeded its {sla_label} target (escalation level "
                    f"{policy['escalation_level']}). Please review the incident."
                )
                for recipient_id in sorted(recipients):
                    cur.execute(
                        """INSERT INTO notifications
                           (recipient_employee_id,notification_type,title,body,target_type,target_id)
                           VALUES (%s,'INCIDENT_SLA_ESCALATION',%s,%s,'incident',%s)""",
                        (recipient_id, title, body, str(ticket["ticket_id"])),
                    )
                    notification_id = int(cur.lastrowid)
                    cur.execute(
                        "INSERT INTO notification_outbox (notification_id,channel) VALUES (%s,'IN_APP')",
                        (notification_id,),
                    )
                    notifications_created += 1
                cur.execute(
                    """INSERT INTO audit_events
                       (actor_employee_id,event_key,target_type,target_id,outcome,details)
                       VALUES (NULL,'INCIDENT_SLA_ESCALATED','incident',%s,'SUCCESS',
                               JSON_OBJECT('sla_type',%s,'level',%s,'recipient_count',%s))""",
                    (str(ticket["ticket_id"]), policy["sla_type"],
                     policy["escalation_level"], len(recipients)),
                )
        conn.commit()
        return {"events_created": events_created, "notifications_created": notifications_created}
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()
