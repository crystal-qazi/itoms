"""Secure document upload and download routes."""
from __future__ import annotations

import hmac
from io import BytesIO
from flask import Blueprint, abort, flash, g, make_response, redirect, render_template, request, send_file, session, url_for

from itoms.security.decorators import login_required
from itoms.services.authorization import has_permission
from itoms.services.documents import (
    DocumentError, list_allowed_file_types, list_documents, list_document_shares,
    set_file_type_allowlist, upload_document, upload_document_version,
    create_document_share, revoke_document_share, download_document,
    list_document_versions, archive_document, permanently_delete_document,
)

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


def _valid_csrf() -> bool:
    token = session.get("csrf_token", "")
    supplied = request.form.get("csrf_token", "")
    return bool(token and hmac.compare_digest(str(token), str(supplied)))


@documents_bp.get("/")
@login_required
def index():
    items = list_documents(employee_id=g.employee_id)
    can_manage_types = has_permission(g.employee_id, "document.allowlist.manage")
    allowed_types = []
    if can_manage_types:
        try:
            allowed_types = list_allowed_file_types(actor_employee_id=g.employee_id)
        except DocumentError:
            allowed_types = []
    return render_template(
        "documents/index.html", documents=items, shares=list_document_shares(employee_id=g.employee_id),
        versions={item["file_id"]: list_document_versions(employee_id=g.employee_id, file_id=item["file_id"])
                  for item in items},
        can_upload=has_permission(g.employee_id, "document.upload"),
        can_manage_types=can_manage_types, allowed_types=allowed_types,
        csrf_token_value=session.get("csrf_token", ""),
    )


@documents_bp.post("/")
@login_required
def upload():
    if not _valid_csrf():
        return "Invalid request token", 400
    uploaded = request.files.get("document")
    if not uploaded:
        flash("Choose a document to upload.", "danger")
        return redirect(url_for("documents.index"))
    try:
        result = upload_document(
            actor_employee_id=g.employee_id, filename=uploaded.filename or "",
            content=uploaded.read(10 * 1024 * 1024 + 1),
            classification=request.form.get("classification", "INTERNAL").upper(),
        )
        if result["scan_status"] == "CLEAN":
            flash("Document uploaded and cleared by Trend Micro.", "success")
        else:
            flash("Document is quarantined because the antivirus scan did not confirm CLEAN.", "warning")
    except DocumentError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("documents.index"))


@documents_bp.post("/allowlist")
@login_required
def allowlist():
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        set_file_type_allowlist(
            actor_employee_id=g.employee_id,
            extension=request.form.get("extension", ""),
            mime_type=request.form.get("mime_type", ""),
            description=request.form.get("description", ""),
            is_active=request.form.get("is_active") == "1",
        )
        flash("Document file type allowlist updated.", "success")
    except DocumentError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("documents.index"))



@documents_bp.post("/<int:file_id>/versions")
@login_required
def version_upload(file_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    uploaded = request.files.get("document")
    if not uploaded:
        flash("Choose a new document version.", "danger")
        return redirect(url_for("documents.index"))
    try:
        result = upload_document_version(
            actor_employee_id=g.employee_id, file_id=file_id,
            filename=uploaded.filename or "", content=uploaded.read(10 * 1024 * 1024 + 1),
        )
        if result["scan_status"] == "CLEAN":
            flash(f"Version {result['version_number']} uploaded and cleared by Trend Micro.", "success")
        else:
            flash("New version is quarantined until a clean antivirus scan is confirmed.", "warning")
    except DocumentError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("documents.index"))


@documents_bp.post("/<int:file_id>/shares")
@login_required
def share(file_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        create_document_share(
            actor_employee_id=g.employee_id, file_id=file_id,
            recipient_employee_id=int(request.form.get("recipient_employee_id", "")),
            permission="DOWNLOAD", expires_at=request.form.get("expires_at", ""),
            approval_request_id=int(request.form["approval_request_id"])
            if request.form.get("approval_request_id", "").strip() else None,
        )
        flash("Document download share created.", "success")
    except (DocumentError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid document share.", "danger")
    return redirect(url_for("documents.index"))


@documents_bp.post("/shares/<int:share_id>/revoke")
@login_required
def share_revoke(share_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        revoke_document_share(actor_employee_id=g.employee_id, share_id=share_id)
        flash("Document share revoked.", "success")
    except DocumentError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("documents.index"))



@documents_bp.post("/<int:file_id>/archive")
@login_required
def archive(file_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        archive_document(actor_employee_id=g.employee_id, file_id=file_id)
        flash("Document archived and active shares revoked.", "success")
    except DocumentError as exc:
        flash(str(exc), "danger")
    return redirect(url_for("documents.index"))


@documents_bp.post("/<int:file_id>/delete")
@login_required
def permanent_delete(file_id: int):
    if not _valid_csrf():
        return "Invalid request token", 400
    try:
        permanently_delete_document(
            actor_employee_id=g.employee_id, file_id=file_id,
            approval_request_id=int(request.form.get("approval_request_id", "")),
        )
        flash("Document permanently deleted after approval.", "success")
    except (DocumentError, ValueError, TypeError) as exc:
        flash(str(exc) or "Invalid deletion approval.", "danger")
    return redirect(url_for("documents.index"))


@documents_bp.get("/<int:file_id>/download")
@login_required
def download(file_id: int):
    try:
        content, filename, mime_type = download_document(employee_id=g.employee_id, file_id=file_id)
    except DocumentError:
        abort(404)
    response = make_response(send_file(
        BytesIO(content), mimetype=mime_type, as_attachment=True,
        download_name=filename, conditional=False,
    ))
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
