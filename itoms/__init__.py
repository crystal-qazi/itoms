"""ITOMS application package."""
from flask import Flask

from itoms.config import Config
from itoms.logging_config import configure_logging


def create_app(config_class: type[Config] = Config) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.from_prefixed_env(prefix="ITOMS")
    if app.config.get("TESTING"):
        app.config.setdefault("SECRET_KEY", "test-only-key")
    config_class.validate(app.config)
    configure_logging(app.config.get("LOG_LEVEL", "INFO"))

    from itoms.web.health import health_bp
    app.register_blueprint(health_bp)
    return app
