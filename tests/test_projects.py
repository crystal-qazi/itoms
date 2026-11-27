"""Input validation tests for project management."""
import pytest

from itoms.services import projects


@pytest.mark.parametrize("key", ["", "A", "bad key", "x" * 81])
def test_project_key_validation_happens_before_database(monkeypatch, key):
    monkeypatch.setattr(projects, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(projects.ProjectError, match="Project key"):
        projects.create_project(
            actor_employee_id=1, project_key=key, project_name="Valid project",
            team_ids=[1],
        )


def test_project_dates_must_be_valid_and_ordered_before_database(monkeypatch):
    monkeypatch.setattr(projects, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(projects.ProjectError, match="valid ISO date"):
        projects.create_project(
            actor_employee_id=1, project_key="OPS-2027", project_name="Valid project",
            team_ids=[1], start_date="2027-99-99",
        )
    with pytest.raises(projects.ProjectError, match="cannot be before"):
        projects.create_project(
            actor_employee_id=1, project_key="OPS-2027", project_name="Valid project",
            team_ids=[1], start_date="2027-05-02", target_end_date="2027-05-01",
        )


def test_project_requires_unique_valid_team_ids_before_database(monkeypatch):
    monkeypatch.setattr(projects, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(projects.ProjectError, match="once"):
        projects.create_project(
            actor_employee_id=1, project_key="OPS-2027", project_name="Valid project",
            team_ids=[1, 1],
        )
    with pytest.raises(projects.ProjectError, match="1 and 20"):
        projects.create_project(
            actor_employee_id=1, project_key="OPS-2027", project_name="Valid project",
            team_ids=[],
        )


def test_milestone_validation_happens_before_database(monkeypatch):
    monkeypatch.setattr(projects, "get_connection", lambda: pytest.fail("database should not be opened"))
    with pytest.raises(projects.ProjectError, match="Milestone title"):
        projects.create_milestone(actor_employee_id=1, project_id=1, title=" ")
    with pytest.raises(projects.ProjectError, match="Invalid milestone status"):
        projects.update_milestone_status(
            actor_employee_id=1, milestone_id=1, new_status="APPROVED"
        )
