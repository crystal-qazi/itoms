"""Release approval request validation tests."""
import pytest

from itoms.services import release_management


def test_release_approval_request_requires_approvers(monkeypatch):
    monkeypatch.setattr(release_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(release_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(release_management.ReleaseError, match="1–10 distinct approvers"):
        release_management.transition_release(
            actor_employee_id=10,
            release_id=5,
            new_status="REQUEST_APPROVAL",
            approver_employee_ids=[],
        )


def test_release_approval_request_rejects_requester_as_approver(monkeypatch):
    monkeypatch.setattr(release_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(release_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(release_management.ReleaseError, match="other than yourself"):
        release_management.transition_release(
            actor_employee_id=10,
            release_id=5,
            new_status="REQUEST_APPROVAL",
            approver_employee_ids=[11, 10],
        )


def test_release_approval_request_requires_approval_permission(monkeypatch):
    def permission(_actor, key, *_context):
        return key != "approvals.create"

    monkeypatch.setattr(release_management, "has_permission", permission)
    monkeypatch.setattr(release_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(release_management.ReleaseError, match="not authorized to submit"):
        release_management.transition_release(
            actor_employee_id=10,
            release_id=5,
            new_status="REQUEST_APPROVAL",
            approver_employee_ids=[11],
        )


def test_release_approval_request_limits_reason(monkeypatch):
    monkeypatch.setattr(release_management, "has_permission", lambda *_: True)
    monkeypatch.setattr(release_management, "get_connection", lambda: pytest.fail("database must not be opened"))

    with pytest.raises(release_management.ReleaseError, match="reason is too long"):
        release_management.transition_release(
            actor_employee_id=10,
            release_id=5,
            new_status="REQUEST_APPROVAL",
            approver_employee_ids=[11],
            approval_reason="x" * 4001,
        )
