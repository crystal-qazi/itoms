"""Password policy primitives; authentication workflows call these functions."""
from __future__ import annotations
import re

class PasswordPolicyError(ValueError):
    """Password does not meet policy requirements."""

def validate_password(password: str) -> None:
    """Validate the configured baseline password complexity and length."""
    if len(password) < 12:
        raise PasswordPolicyError("Password must contain at least 12 characters.")
    if not re.search(r"[a-z]", password):
        raise PasswordPolicyError("Password must include a lowercase letter.")
    if not re.search(r"[A-Z]", password):
        raise PasswordPolicyError("Password must include an uppercase letter.")
    if not re.search(r"\d", password):
        raise PasswordPolicyError("Password must include a number.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise PasswordPolicyError("Password must include a special character.")
