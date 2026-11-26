"""Tests for directory service validation."""
import pytest
from itoms.services.directory import DirectoryError, assign_employee_to_team

def test_rejects_invalid_ids_before_database_access():
    with pytest.raises(DirectoryError):
        assign_employee_to_team(0, 2)
    with pytest.raises(DirectoryError):
        assign_employee_to_team(1, -1)
