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

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        return response

    from itoms.web.health import health_bp
    app.register_blueprint(health_bp)
    return app
