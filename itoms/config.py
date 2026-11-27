"""Application configuration with environment-backed settings."""
from __future__ import annotations

import os
from cryptography.fernet import Fernet


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
    GRAFANA_WEBHOOK_SECRET = os.getenv("ITOMS_GRAFANA_WEBHOOK_SECRET")
    GRAFANA_SERVICE_EMPLOYEE_ID = int(os.getenv("ITOMS_GRAFANA_SERVICE_EMPLOYEE_ID", "0"))
    DOCUMENT_STORAGE_ROOT = os.getenv("ITOMS_DOCUMENT_STORAGE_ROOT")
    TREND_MICRO_ICAP_HOST = os.getenv("ITOMS_TREND_MICRO_ICAP_HOST")
    TREND_MICRO_ICAP_PORT = int(os.getenv("ITOMS_TREND_MICRO_ICAP_PORT", "1344"))
    TREND_MICRO_ICAP_SERVICE = os.getenv("ITOMS_TREND_MICRO_ICAP_SERVICE", "avscan")
    TREND_MICRO_ICAP_TIMEOUT = float(os.getenv("ITOMS_TREND_MICRO_ICAP_TIMEOUT", "15"))
    SMTP_HOST = os.getenv("ITOMS_SMTP_HOST")
    SMTP_PORT = int(os.getenv("ITOMS_SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("ITOMS_SMTP_USERNAME")
    SMTP_PASSWORD = os.getenv("ITOMS_SMTP_PASSWORD")
    SMTP_FROM = os.getenv("ITOMS_SMTP_FROM")
    SMTP_USE_STARTTLS = os.getenv("ITOMS_SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes"}
    SMTP_USE_SSL = os.getenv("ITOMS_SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"}
    SMTP_TIMEOUT = float(os.getenv("ITOMS_SMTP_TIMEOUT", "15"))
    MAX_CONTENT_LENGTH = 11 * 1024 * 1024

    @classmethod
    def validate(cls, config: dict) -> None:
        if not config.get("SECRET_KEY") and not config.get("TESTING"):
            raise RuntimeError("ITOMS_SECRET_KEY must be configured.")
        if not config.get("TESTING"):
            key = config.get("TOTP_ENCRYPTION_KEY")
            if not key:
                raise RuntimeError("ITOMS_TOTP_ENCRYPTION_KEY must be configured.")
            try:
                Fernet(key.encode("utf-8"))
            except (ValueError, TypeError):
                raise RuntimeError("ITOMS_TOTP_ENCRYPTION_KEY must be a valid Fernet key.") from None
