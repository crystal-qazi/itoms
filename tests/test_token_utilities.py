"""Tests for token generation and digesting."""
from itoms.security.tokens import generate_token, token_digest

def test_token_is_unique_and_digest_is_stable():
    token_a, token_b = generate_token(), generate_token()
    assert token_a != token_b
    assert token_digest(token_a) == token_digest(token_a)
    assert token_digest(token_a) != token_a
