"""Unit validation for incident SLA escalation policy configuration."""
import pytest

from itoms.services import sla_escalations


def test_sla_policy_validation_precedes_database(monkeypatch):
    monkeypatch.setattr(sla_escalations, "has_permission", lambda *_: True)
    monkeypatch.setattr(sla_escalations, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(sla_escalations.SLAEscalationError, match="priority and SLA type"):
        sla_escalations.upsert_escalation_policy(
            actor_employee_id=1, priority="URGENT", sla_type="FIRST_RESPONSE",
            escalation_level=1, after_due_minutes=30,
        )
    with pytest.raises(sla_escalations.SLAEscalationError, match="between 1 and 9"):
        sla_escalations.upsert_escalation_policy(
            actor_employee_id=1, priority="HIGH", sla_type="RESOLUTION",
            escalation_level=10, after_due_minutes=30,
        )
    with pytest.raises(sla_escalations.SLAEscalationError, match="between 1 and 10,080"):
        sla_escalations.upsert_escalation_policy(
            actor_employee_id=1, priority="HIGH", sla_type="RESOLUTION",
            escalation_level=1, after_due_minutes=0,
        )
