"""Health endpoint blueprint."""
from flask import Blueprint

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health() -> dict[str, str]:
    """Provide a simple process health response without exposing internals."""
    return {"status": "ok", "application": "ITOMS"}
