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



class GateCursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.statements = []

    def execute(self, statement, params):
        self.statements.append((statement, params))

    def fetchone(self):
        return next(self.rows)


def test_release_gate_requires_completed_plan_and_cases():
    from itoms.services.release_management import ReleaseError, _assert_sqa_release_gate

    cursor = GateCursor([(0,)])
    try:
        _assert_sqa_release_gate(cursor, "REL-1")
    except ReleaseError as exc:
        assert "completed test plan" in str(exc)
    else:
        raise AssertionError("Release gate must reject a release without a completed plan")


def test_release_gate_requires_passed_cases_and_unambiguous_signoff():
    from itoms.services.release_management import _assert_sqa_release_gate

    cursor = GateCursor([(1,), (2,), (0,), (0,), (1, 0)])
    _assert_sqa_release_gate(cursor, "REL-2")
    assert len(cursor.statements) == 5


def test_release_gate_rejects_any_sqa_rejection():
    from itoms.services.release_management import ReleaseError, _assert_sqa_release_gate

    cursor = GateCursor([(1,), (1,), (0,), (0,), (1, 1)])
    try:
        _assert_sqa_release_gate(cursor, "REL-3")
    except ReleaseError as exc:
        assert "APPROVED sign-off" in str(exc)
    else:
        raise AssertionError("Release gate must reject conflicting SQA sign-offs")
