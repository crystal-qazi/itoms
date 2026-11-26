"""Configuration validation tests for required cryptographic secrets."""
import pytest
from cryptography.fernet import Fernet
from itoms.config import Config

def test_production_configuration_requires_secret_key():
    with pytest.raises(RuntimeError, match="ITOMS_SECRET_KEY"):
        Config.validate({"TESTING": False, "SECRET_KEY": None})

def test_production_configuration_requires_valid_totp_key():
    with pytest.raises(RuntimeError, match="ITOMS_TOTP_ENCRYPTION_KEY"):
        Config.validate({"TESTING": False, "SECRET_KEY": "configured", "TOTP_ENCRYPTION_KEY": "invalid"})

def test_production_configuration_accepts_fernet_key():
    Config.validate({"TESTING": False, "SECRET_KEY": "configured",
                     "TOTP_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")})

def test_test_configuration_can_omit_production_secrets():
    Config.validate({"TESTING": True})
