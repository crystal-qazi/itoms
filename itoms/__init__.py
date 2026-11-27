"""ITOMS application package."""
from flask import Flask, g, session, request, redirect, url_for

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
    app.config.setdefault("MAX_CONTENT_LENGTH", 1024 * 1024)
    configure_logging(app.config.get("LOG_LEVEL", "INFO"))

    @app.before_request
    def validate_server_session():
        token = session.get("server_session_token")
        if not token:
            g.account_id = None
            g.employee_id = None
            g.mfa_enabled = False
            return
        from itoms.services.auth import validate_session
        identity = validate_session(token)
        if identity is None:
            session.clear()
            g.account_id = None
            g.employee_id = None
            g.mfa_enabled = False
        else:
            g.account_id, g.employee_id, g.mfa_enabled = identity

        # Require password rotation first, then verified MFA before app access.
        if g.account_id:
            endpoint = request.endpoint or ""
            if session.get("must_change_password"):
                if endpoint not in {"auth.change_password_route", "auth.logout", "static"}:
                    return redirect(url_for("auth.change_password_route"))
            elif not g.mfa_enabled:
                if endpoint not in {"auth.mfa_enroll", "auth.logout", "static"}:
                    return redirect(url_for("auth.mfa_enroll"))

    @app.after_request
    def apply_security_headers(response):
        response.headers.setdefault("Cache-Control", "no-store, private")
        response.headers.setdefault("Pragma", "no-cache")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'")
        return response

    from itoms.web.health import health_bp
    from itoms.web.auth import auth_bp
    from itoms.web.grafana import grafana_bp
    from itoms.web.incidents import incidents_bp
    from itoms.web.service_requests import service_requests_bp
    from itoms.web.engineering_tasks import engineering_tasks_bp
    from itoms.web.service_inventory import service_inventory_bp
    from itoms.web.notifications import notifications_bp
    from itoms.web.approvals import approval_bp
    from itoms.web.changes import change_bp
    from itoms.web.releases import release_bp
    from itoms.web.sqa import sqa_bp
    from itoms.web.role_permissions import role_permissions_bp
    from itoms.web.projects import projects_bp
    from itoms.web.assets import assets_bp
    from itoms.web.operations import operations_bp
    from itoms.web.training import training_bp
    from itoms.web.vendors import vendors_bp
    from itoms.web.reports import reports_bp
    from itoms.web.problems import problems_bp
    from itoms.web.sla_admin import sla_admin_bp
    from itoms.web.documents import documents_bp
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(grafana_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(service_requests_bp)
    app.register_blueprint(engineering_tasks_bp)
    app.register_blueprint(service_inventory_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(approval_bp)
    app.register_blueprint(change_bp)
    app.register_blueprint(release_bp)
    app.register_blueprint(sqa_bp)
    app.register_blueprint(role_permissions_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(operations_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(vendors_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(problems_bp)
    app.register_blueprint(sla_admin_bp)
    app.register_blueprint(documents_bp)
    register_cli(app)
    return app
