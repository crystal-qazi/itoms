"""Input validation tests for asset and maintenance workflows."""
import pytest

from itoms.services import assets


def test_asset_validation_happens_before_database(monkeypatch):
    monkeypatch.setattr(assets, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(assets.AssetError, match="Asset tag"):
        assets.create_asset(
            actor_employee_id=1, asset_tag="bad tag", asset_name="Laptop",
            asset_type="COMPUTER", owner_team_id=1,
        )
    with pytest.raises(assets.AssetError, match="Asset name"):
        assets.create_asset(
            actor_employee_id=1, asset_tag="IT-001", asset_name=" ",
            asset_type="COMPUTER", owner_team_id=1,
        )


def test_asset_acquired_date_validation_happens_before_database(monkeypatch):
    monkeypatch.setattr(assets, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(assets.AssetError, match="valid ISO date"):
        assets.create_asset(
            actor_employee_id=1, asset_tag="IT-001", asset_name="Laptop",
            asset_type="COMPUTER", owner_team_id=1, acquired_on="2027-99-99",
        )


def test_maintenance_validation_happens_before_database(monkeypatch):
    monkeypatch.setattr(assets, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(assets.AssetError, match="issue description"):
        assets.create_maintenance(actor_employee_id=1, asset_id=1, issue_description=" ")
    with pytest.raises(assets.AssetError, match="Invalid maintenance status"):
        assets.update_maintenance_status(
            actor_employee_id=1, maintenance_id=1, new_status="APPROVED"
        )
