"""Unit tests for incident status transition rules."""
from itoms.services.incidents import TRANSITIONS

def test_incident_resolution_can_be_reopened_and_closed():
    assert TRANSITIONS["RESOLVED"] == {"CLOSED", "OPEN"}

def test_closed_and_cancelled_incidents_are_terminal():
    assert TRANSITIONS["CLOSED"] == set()
    assert TRANSITIONS["CANCELLED"] == set()

def test_new_incident_cannot_skip_open_workflow():
    assert TRANSITIONS["NEW"] == {"OPEN", "CANCELLED"}
