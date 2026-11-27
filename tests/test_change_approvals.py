"""Change approval submission validation tests."""
import pytest

from itoms.services import change_management


def test_change_submission_requires_at_least_one_approver(monkeypatch):
    monkeypatch.setattr(change_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(change_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(change_management.ChangeError, match="1–10 distinct approvers"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SUBMITTED",
            approver_employee_ids=[],
        )


def test_change_submission_rejects_requester_as_approver(monkeypatch):
    monkeypatch.setattr(change_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(change_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(change_management.ChangeError, match="other than yourself"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SUBMITTED",
            approver_employee_ids=[11, 10],
        )


def test_change_submission_requires_approval_creation_permission(monkeypatch):
    def permission(_actor, key, *_context):
        return key != "approvals.create"

    monkeypatch.setattr(change_management, "has_permission", permission)
    monkeypatch.setattr(change_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(change_management.ChangeError, match="not authorized to submit"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SUBMITTED",
            approver_employee_ids=[11],
        )


def test_change_submission_limits_approval_reason(monkeypatch):
    monkeypatch.setattr(change_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(change_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(change_management.ChangeError, match="reason is too long"):
        change_management.transition_change(
            actor_employee_id=10,
            change_id=25,
            new_status="SUBMITTED",
            details="x" * 4001,
            approver_employee_ids=[11],
        )
