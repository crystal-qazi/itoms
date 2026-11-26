"""Reusable route guards; authorization remains server-side and fail-closed."""
from __future__ import annotations
from functools import wraps
from flask import abort, g, redirect, session, url_for
from itoms.services.authorization import ResourceContext, has_permission

def login_required(view):
    """Require an authenticated account and enforce first-login password change."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not getattr(g, "account_id", None) or not getattr(g, "employee_id", None):
            return redirect(url_for("auth.login"))
        if session.get("must_change_password") and view.__name__ != "change_password_route":
            return redirect(url_for("auth.change_password_route"))
        return view(*args, **kwargs)
    return wrapped

def permission_required(permission_key: str, resource_resolver=None):
    """Require an explicit permission for the current employee and trusted resource context."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            employee_id = getattr(g, "employee_id", None)
            if not employee_id:
                return redirect(url_for("auth.login"))
            resource = resource_resolver(*args, **kwargs) if resource_resolver else ResourceContext()
            if not has_permission(employee_id, permission_key, resource):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
