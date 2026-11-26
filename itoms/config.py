"""Application configuration with environment-backed settings."""
from __future__ import annotations

import os


class Config:
    SECRET_KEY = os.getenv("ITOMS_SECRET_KEY")
    DEBUG = False
    TESTING = False
    DB_HOST = os.getenv("ITOMS_DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("ITOMS_DB_PORT", "3306"))
    DB_NAME = os.getenv("ITOMS_DB_NAME", "itoms_dev")
    DB_USER = os.getenv("ITOMS_DB_USER", "itoms_app")
    DB_PASSWORD = os.getenv("ITOMS_DB_PASSWORD", "")
    DB_CONNECT_TIMEOUT = int(os.getenv("ITOMS_DB_CONNECT_TIMEOUT", "5"))
    LOG_LEVEL = os.getenv("ITOMS_LOG_LEVEL", "INFO")
    TOTP_ENCRYPTION_KEY = os.getenv("ITOMS_TOTP_ENCRYPTION_KEY")

    @classmethod
    def validate(cls, config: dict) -> None:
        if not config.get("SECRET_KEY") and not config.get("TESTING"):
            raise RuntimeError("ITOMS_SECRET_KEY must be configured.")
