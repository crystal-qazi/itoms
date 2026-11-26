"""Login and logout routes; account provisioning is intentionally admin-only."""
from __future__ import annotations
import hmac
import secrets
from flask import Blueprint, flash, g, redirect, render_template, render_template_string, request, session, url_for
from itoms.services.auth import authenticate, revoke_session, change_password, AuthenticationError, begin_totp_enrollment, confirm_totp_enrollment

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
LOGIN_TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ITOMS Sign in</title></head><body><main><h1>ITOMS</h1><h2>Sign in</h2>{% with messages=get_flashed_messages() %}{% for message in messages %}<p role="alert">{{ message }}</p>{% endfor %}{% endwith %}<form method="post"><input type="hidden" name="csrf_token" value="{{ csrf_token }}"><label>Username <input name="username" autocomplete="username" required maxlength="120"></label><label>Password <input type="password" name="password" autocomplete="current-password" required></label><label>Authenticator code (if MFA is enabled) <input name="otp_code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" autocomplete="one-time-code"></label><button type="submit">Sign in</button></form></main></body></html>"""

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    csrf = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    if request.method == "GET":
        return render_template_string(LOGIN_TEMPLATE, csrf_token=csrf)
    supplied = request.form.get("csrf_token", "")
    if not hmac.compare_digest(str(csrf), str(supplied)):
        return "Invalid request token", 400
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if not username or not password:
        flash("Invalid username or password.")
        return redirect(url_for("auth.login"))
    result = authenticate(username, password, ip_address=request.remote_addr,
                          user_agent=request.user_agent.string[:500],
                          otp_code=request.form.get('otp_code', '').strip() or None)
    if result is None:
        flash("Invalid username or password.")
        return redirect(url_for("auth.login"))
    account_id, token, must_change = result
    session.clear()
    session["account_id"] = account_id
    session["server_session_token"] = token
    session["csrf_token"] = secrets.token_urlsafe(32)
    session["must_change_password"] = must_change
    return redirect(url_for("auth.change_password_route") if must_change else url_for("auth.home"))


@auth_bp.route("/mfa/enroll", methods=["GET", "POST"])
def mfa_enroll():
    if not g.account_id:
        return redirect(url_for("auth.login"))
    csrf = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    if request.method == "GET":
        try:
            secret, uri = begin_totp_enrollment(g.account_id)
        except AuthenticationError as exc:
            return str(exc), 503
        return render_template_string("""<!doctype html><html lang="en"><meta charset="utf-8"><title>Set up MFA</title><h1>Set up authenticator</h1><p>Enter this secret manually in your authenticator app:</p><code>{{ secret }}</code><p>{{ uri }}</p><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf }}"><label>6-digit code <input name="code" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" required></label><button>Confirm MFA</button></form></html>""", secret=secret, uri=uri, csrf=csrf)
    if not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))):
        return "Invalid request token", 400
    try:
        recovery_codes = confirm_totp_enrollment(g.account_id, request.form.get("code", "").strip())
    except AuthenticationError as exc:
        flash(str(exc))
        return redirect(url_for("auth.mfa_enroll"))
    return render_template_string("""<!doctype html><html lang="en"><meta charset="utf-8"><title>Recovery codes</title><h1>Save your recovery codes</h1><p>Each code can be used once. Store them securely; they will not be shown again.</p><ul>{% for item in codes %}<li><code>{{ item }}</code></li>{% endfor %}</ul><a href="{{ url_for('auth.home') }}">Continue</a></html>""", codes=recovery_codes)

@auth_bp.get("/home")
def home():
    if not g.account_id:
        return redirect(url_for("auth.login"))
    if session.get("must_change_password"):
        return redirect(url_for("auth.change_password_route"))
    return render_template("dashboard.html", csrf_token_value=session.get("csrf_token", ""), summary=[{"label":"Open incidents","note":"Helpdesk module pending"},{"label":"My tasks","note":"Engineering tasks pending"},{"label":"Pending changes","note":"Change management pending"},{"label":"Service inventory","note":"Inventory module pending"}])

@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password_route():
    if not g.account_id:
        return redirect(url_for("auth.login"))
    csrf = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    if request.method == "GET":
        return render_template_string("""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Change password</title><h1>Change password</h1><form method="post"><input type="hidden" name="csrf_token" value="{{ csrf }}"><label>Current password <input type="password" name="current_password" required></label><label>New password <input type="password" name="new_password" required minlength="12"></label><button type="submit">Change password</button></form></html>""", csrf=csrf)
    if not hmac.compare_digest(str(csrf), str(request.form.get("csrf_token", ""))):
        return "Invalid request token", 400
    try:
        change_password(g.account_id, request.form.get("current_password", ""), request.form.get("new_password", ""))
    except (AuthenticationError, ValueError) as exc:
        flash(str(exc))
        return redirect(url_for("auth.change_password_route"))
    session.clear()
    flash("Password changed. Please sign in again.")
    return redirect(url_for("auth.login"))

@auth_bp.post("/logout")
def logout():
    csrf = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    if not csrf or not hmac.compare_digest(str(csrf), str(supplied)):
        return "Invalid request token", 400
    token = session.get("server_session_token")
    if token:
        revoke_session(token)
    session.clear()
    return redirect(url_for("auth.login"))
