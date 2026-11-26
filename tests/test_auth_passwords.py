"""Authentication security utility tests."""
from itoms.services.auth import hash_password, verify_password

def test_password_hash_is_not_plaintext_and_verifies():
    raw = "Strong-Password-123!"
    stored = hash_password(raw)
    assert stored != raw
    assert verify_password(stored, raw)
    assert not verify_password(stored, "wrong")
