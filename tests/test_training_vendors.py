"""Validation tests for training and vendor directory services."""
import pytest

from itoms.services import training, vendors


def test_course_title_validation_precedes_database(monkeypatch):
    monkeypatch.setattr(training, "has_permission", lambda *_: True)
    monkeypatch.setattr(training, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(training.TrainingError, match="Course title"):
        training.create_course(actor_employee_id=1, course_title=" ")


def test_vendor_contact_validation_precedes_database(monkeypatch):
    monkeypatch.setattr(vendors, "has_permission", lambda *_: True)
    monkeypatch.setattr(vendors, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(vendors.VendorError, match="valid support email"):
        vendors.create_vendor(actor_employee_id=1, vendor_name="SupportCo", support_email="not-an-email")
    with pytest.raises(vendors.VendorError, match="HTTPS"):
        vendors.create_vendor(
            actor_employee_id=1, vendor_name="SupportCo",
            support_portal_url="http://support.example.com",
        )
    with pytest.raises(vendors.VendorError, match="credentials"):
        vendors.create_vendor(
            actor_employee_id=1, vendor_name="SupportCo",
            support_portal_url="https://user:pass@support.example.com",
        )
