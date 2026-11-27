"""Department/team context propagation for Change and Release authorization."""
from itoms.services.change_management import _context as change_context
from itoms.services.release_management import _ctx as release_context
from itoms.services.authorization import ResourceContext


def test_change_context_includes_requester_department_and_owner_team():
    context = change_context({
        "change_id": 25,
        "requested_by": 10,
        "department_id": 7,
        "team_id": 3,
    })

    assert context == ResourceContext(
        owner_employee_id=10,
        team_id=3,
        department_id=7,
        resource_type="change",
        resource_id="25",
    )


def test_change_context_without_team_still_supports_department_scope():
    context = change_context({
        "change_id": 26,
        "requested_by": 11,
        "department_id": 8,
        "team_id": None,
    })

    assert context.department_id == 8
    assert context.team_id is None


def test_release_context_includes_creator_department_and_service_team():
    context = release_context({
        "release_id": 5,
        "created_by": 10,
        "department_id": 7,
        "team_id": 3,
    })

    assert context == ResourceContext(
        owner_employee_id=10,
        team_id=3,
        department_id=7,
        resource_type="release",
        resource_id="5",
    )


def test_release_context_without_service_team_still_supports_department_scope():
    context = release_context({
        "release_id": 6,
        "created_by": 12,
        "department_id": 9,
        "team_id": None,
    })

    assert context.department_id == 9
    assert context.team_id is None
