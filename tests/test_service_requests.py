"""Unit validation tests for the basic Service Requests workflow."""
import pytest

from itoms.services import service_requests


def test_create_request_rejects_empty_title_before_database(monkeypatch):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened for invalid input"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="title"):
        service_requests.create_request(
            actor_employee_id=1, title=" ", description="A valid description"
        )


def test_create_request_rejects_invalid_priority_before_database(monkeypatch):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened for invalid input"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="priority"):
        service_requests.create_request(
            actor_employee_id=1, title="Need access", description="Please provide access.",
            priority="X" * 31,
        )


def test_completion_requires_resolution_notes_before_database(monkeypatch):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened without resolution notes"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="Resolution notes"):
        service_requests.transition_request(
            actor_employee_id=1, request_id=7, new_status="COMPLETED"
        )


def test_invalid_transition_name_is_rejected_before_database(monkeypatch):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened for an invalid status"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="Invalid service request status"):
        service_requests.transition_request(
            actor_employee_id=1, request_id=7, new_status="APPROVED",
            resolution_notes="Not a supported state",
        )


def test_category_name_validation_is_enforced(monkeypatch):
    monkeypatch.setattr(service_requests, "has_permission", lambda *_: True)
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened for an invalid category"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="Category name"):
        service_requests.create_category(actor_employee_id=1, category_name="x")


def test_pending_transition_requires_reason_before_database(monkeypatch):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened without a pending reason"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="pending reason"):
        service_requests.transition_request(
            actor_employee_id=1, request_id=7, new_status="ON_HOLD",
        )


@pytest.mark.parametrize("body", ["", "   ", "x" * 5001])
def test_comment_validation_rejects_invalid_body_before_database(monkeypatch, body):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened for an invalid comment"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="Comment"):
        service_requests.add_comment(
            actor_employee_id=1, request_id=7, body=body,
        )

def test_create_priority_rejects_invalid_key_before_database(monkeypatch):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened for an invalid priority key"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="Priority key"):
        service_requests.create_priority(
            actor_employee_id=1, priority_key="X", priority_label="Urgent",
        )


def test_update_priority_rejects_boolean_sort_order_before_database(monkeypatch):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened for an invalid sort order"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match="sort order"):
        service_requests.update_priority(
            actor_employee_id=1, priority_key="HIGH", priority_label="High",
            sort_order=True, is_active=True,
        )

@pytest.mark.parametrize(
    "filters, message",
    [
        ({"search": "x" * 121}, "search text"),
        ({"created_from": "not-a-date"}, "start date"),
        ({"created_from": "2026-02-02", "created_to": "2026-02-01"}, "Start date"),
    ],
)
def test_advanced_search_rejects_invalid_filters_before_database(monkeypatch, filters, message):
    monkeypatch.setattr(
        service_requests, "get_connection",
        lambda: pytest.fail("database must not be opened for invalid search filters"),
    )
    with pytest.raises(service_requests.ServiceRequestError, match=message):
        service_requests.list_requests(actor_employee_id=1, **filters)

