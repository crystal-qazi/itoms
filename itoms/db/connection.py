"""MySQL connection factory using the official connector and native SQL."""
from __future__ import annotations

from flask import current_app
import mysql.connector


def get_connection():
    """Create a connection from app configuration; callers must close it."""
    cfg = current_app.config
    return mysql.connector.connect(
        host=cfg["DB_HOST"], port=cfg["DB_PORT"], database=cfg["DB_NAME"],
        user=cfg["DB_USER"], password=cfg["DB_PASSWORD"],
        connection_timeout=cfg["DB_CONNECT_TIMEOUT"],
        autocommit=False,
    )
