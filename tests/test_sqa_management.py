"""SQA route registration and lifecycle contract tests."""
from itoms import create_app
from itoms.services.sqa import DEFECT_SEVERITIES, SIGNOFF_DECISIONS, TEST_RESULTS


class TestConfig:
    SECRET_KEY = "testing-key"
    TESTING = True
    DB_HOST = "127.0.0.1"
    DB_PORT = 3306
    DB_NAME = "test"
    DB_USER = "test"
    DB_PASSWORD = ""
    DB_CONNECT_TIMEOUT = 1
    LOG_LEVEL = "CRITICAL"

    @classmethod
    def validate(cls, config):
        return None


def test_sqa_blueprint_registers_all_workflow_routes():
    app = create_app(TestConfig)
    expected = {
        "sqa.index", "sqa.create_plan", "sqa.detail", "sqa.add_case",
        "sqa.execute_case", "sqa.defect", "sqa.complete", "sqa.signoff",
    }
    assert expected.issubset(app.view_functions)


def test_sqa_result_and_severity_catalogues_are_closed_sets():
    assert TEST_RESULTS == {"PASS", "FAIL", "BLOCKED", "RETEST"}
    assert DEFECT_SEVERITIES == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert SIGNOFF_DECISIONS == {"APPROVED", "REJECTED", "CONDITIONAL"}
