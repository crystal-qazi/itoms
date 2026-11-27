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
            priority="URGENT",
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
