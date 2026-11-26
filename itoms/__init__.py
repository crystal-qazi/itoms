"""ITOMS application package."""
from flask import Flask, g, session

from itoms.config import Config
from itoms.logging_config import configure_logging
from itoms.cli import register_cli


def create_app(config_class: type[Config] = Config) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    app.config.from_prefixed_env(prefix="ITOMS")
    if app.config.get("TESTING"):
        app.config.setdefault("SECRET_KEY", "test-only-key")
    config_class.validate(app.config)
    app.config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    app.config.setdefault("SESSION_COOKIE_SECURE", not app.config.get("TESTING", False))
    app.config.setdefault("PERMANENT_SESSION_LIFETIME", 3600)
    configure_logging(app.config.get("LOG_LEVEL", "INFO"))

    @app.before_request
    def validate_server_session():
        token = session.get("server_session_token")
        if not token:
            g.account_id = None
            g.employee_id = None
            return
        from itoms.services.auth import validate_session
        identity = validate_session(token)
        if identity is None:
            session.clear()
            g.account_id = None
            g.employee_id = None
        else:
            g.account_id, g.employee_id = identity

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        return response

    from itoms.web.health import health_bp
    from itoms.web.auth import auth_bp
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    register_cli(app)
    return app
