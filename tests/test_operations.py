"""Validation tests for technical operations workflows."""
import pytest

from itoms.services import operations


def test_operational_work_validation_precedes_database(monkeypatch):
    monkeypatch.setattr(operations, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(operations.OperationsError, match="domain"):
        operations.create_operational_work_item(
            actor_employee_id=1, domain="SECURITY", title="Valid", description="Details",
            owner_team_id=1,
        )
    with pytest.raises(operations.OperationsError, match="title"):
        operations.create_operational_work_item(
            actor_employee_id=1, domain="NETWORK", title=" ", description="Details",
            owner_team_id=1,
        )


def test_oracle_inventory_rejects_credentials_and_invalid_values_before_database(monkeypatch):
    monkeypatch.setattr(operations, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(operations.OperationsError, match="credentials and secrets"):
        operations.create_oracle_database(
            actor_employee_id=1, service_id=1, environment_name="PROD",
            database_name="HIS", host_reference="oracle://admin:password@db01",
        )
    with pytest.raises(operations.OperationsError, match="criticality"):
        operations.create_oracle_database(
            actor_employee_id=1, service_id=1, environment_name="PROD",
            database_name="HIS", host_reference="db01.internal", criticality="URGENT",
        )


def test_work_status_validation_precedes_database(monkeypatch):
    monkeypatch.setattr(operations, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(operations.OperationsError, match="Invalid operations work status"):
        operations.update_work_status(actor_employee_id=1, work_item_id=1, new_status="APPROVED")
