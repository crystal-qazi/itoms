"""Validation tests for Problem Management."""
import pytest

from itoms.services import problems


def test_problem_validation_precedes_database(monkeypatch):
    monkeypatch.setattr(problems, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(problems.ProblemError, match="title"):
        problems.create_problem(
            actor_employee_id=1, title=" ", description="Details", owner_team_id=1,
        )
    with pytest.raises(problems.ProblemError, match="priority"):
        problems.create_problem(
            actor_employee_id=1, title="Recurring outage", description="Details",
            owner_team_id=1, priority="URGENT",
        )


def test_known_error_requires_workaround_before_database(monkeypatch):
    monkeypatch.setattr(problems, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(problems.ProblemError, match="workaround"):
        problems.create_known_error(
            actor_employee_id=1, problem_id=1, title="Known fault",
            symptoms="Intermittent failure", workaround=" ",
        )


def test_invalid_problem_status_precedes_database(monkeypatch):
    monkeypatch.setattr(problems, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(problems.ProblemError, match="Invalid problem status"):
        problems.transition_problem(actor_employee_id=1, problem_id=1, new_status="APPROVED")
