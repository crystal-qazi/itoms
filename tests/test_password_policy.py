"""Unit tests for password policy primitives."""
import pytest
from itoms.security.password_policy import PasswordPolicyError, validate_password

@pytest.mark.parametrize("password", ["shortA1!", "lowercaseonly123!", "UPPERCASE123!", "NoSpecialChars123", "NoNumber!!Password"])
def test_rejects_noncompliant_passwords(password):
    with pytest.raises(PasswordPolicyError):
        validate_password(password)

def test_accepts_compliant_password():
    validate_password("Secure-Password-123")
