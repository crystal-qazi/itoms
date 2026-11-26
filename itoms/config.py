"""Application configuration."""
from __future__ import annotations

import os


class Config:
    SECRET_KEY = os.getenv("ITOMS_SECRET_KEY")
    DEBUG = False
    TESTING = False
