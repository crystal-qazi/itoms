"""ITOMS application package."""
from flask import Flask

from itoms.config import Config


def create_app(config_class: type[Config] = Config) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.from_prefixed_env(prefix="ITOMS")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "application": "ITOMS"}

    return app
