"""Unit tests for safe saved-report definitions and CSV serialization."""
import pytest

from itoms.services import reporting


def test_report_definition_rejects_unknown_dataset_or_columns_before_database(monkeypatch):
    monkeypatch.setattr(reporting, "has_permission", lambda *_: True)
    monkeypatch.setattr(reporting, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(reporting.ReportingError, match="supported report dataset"):
        reporting.create_report(
            employee_id=1, report_name="Test", dataset_key="arbitrary_sql",
            columns=["id"],
        )
    with pytest.raises(reporting.ReportingError, match="not available"):
        reporting.create_report(
            employee_id=1, report_name="Test", dataset_key="operations",
            columns=["work_number", "DROP TABLE"],
        )


def test_csv_export_neutralizes_spreadsheet_formulas():
    csv_text = reporting.build_csv(
        ["title", "value"],
        [{"title": "=HYPERLINK(\"https://bad.example\")", "value": "-2"}],
    )
    assert "'=HYPERLINK" in csv_text
    assert "'-2" in csv_text


def test_csv_export_formats_dates_and_lists():
    from datetime import date
    csv_text = reporting.build_csv(
        ["date", "teams"], [{"date": date(2027, 1, 2), "teams": ["Network", "Oracle"]}],
    )
    assert "2027-01-02" in csv_text
    assert "Network, Oracle" in csv_text

def test_service_request_report_priority_filter_uses_active_configured_catalogue(monkeypatch):
    monkeypatch.setattr(reporting, "has_permission", lambda *_: True)
    monkeypatch.setattr(
        reporting.service_requests, "list_priorities",
        lambda: [{"priority_key": "URGENT"}, {"priority_key": "NORMAL"}],
    )
    monkeypatch.setattr(
        reporting, "get_connection",
        lambda: pytest.fail("invalid priority filters must be rejected before database writes"),
    )
    with pytest.raises(reporting.ReportingError, match="Invalid priority filter"):
        reporting.create_report(
            employee_id=1, report_name="Inactive priority",
            dataset_key="service_requests",
            columns=["request_number", "priority"],
            filters={"priority": "CRITICAL"},
        )

