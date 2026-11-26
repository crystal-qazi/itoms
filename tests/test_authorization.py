"""Unit tests for fail-closed authorization input handling."""
from itoms.services.authorization import ResourceContext

def test_resource_context_defaults_to_no_scope():
    context = ResourceContext()
    assert context.owner_employee_id is None
    assert context.team_id is None
    assert context.resource_type is None
