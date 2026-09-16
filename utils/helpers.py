"""Small shared helpers: audit writing, uploads, status transitions, formatting."""
import os
from datetime import datetime

from flask import current_app, request
from flask_login import current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import AuditLog, Notification, StatusHistory, reference_code


# --------------------------------------------------------------------------
# Audit trail
# --------------------------------------------------------------------------

def record_audit(action, entity=None, entity_ref=None, description=None):
    """Write one line to the audit log. Called on every read of citizen data."""
    actor = "System"
    dept = None
    user = None
    if current_user and current_user.is_authenticated:
        user = current_user
        actor = current_user.display_name
        if current_user.is_employee and current_user.employee and current_user.employee.department:
            dept = current_user.employee.department.name
        elif current_user.is_admin:
            dept = "System Administration"

    log = AuditLog(
        user=user, actor=actor, department=dept, action=action,
        entity=entity, entity_ref=entity_ref, description=description,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(log)
    return log


# --------------------------------------------------------------------------
# Uploads
# --------------------------------------------------------------------------

def allowed_file(filename):
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]


def save_upload(file_storage):
    """Store an upload under a collision-proof name. Returns (stored, original, kb)."""
    original = secure_filename(file_storage.filename)
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    stored = f"{stamp}_{original}"
    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, stored)
    file_storage.save(path)
    size_kb = max(1, os.path.getsize(path) // 1024)
    return stored, original, size_kb


# --------------------------------------------------------------------------
# Application workflow
# --------------------------------------------------------------------------

def advance_status(application, new_status, note=None, notify=True):
    """Move an application to a new status, recording history and notifying."""
    old = application.status
    if old == new_status and not note:
        return application

    application.status = new_status
    application.updated_at = datetime.utcnow()

    actor = current_user.display_name if current_user.is_authenticated else "System"
    db.session.add(StatusHistory(
        application=application, from_status=old, to_status=new_status,
        changed_by=actor, note=note,
    ))

    if notify and application.citizen and application.citizen.user:
        category = {"Approved": "success", "Rejected": "danger",
                    "Collected": "success"}.get(new_status, "info")
        Notification.send(
            application.citizen.user,
            f"{application.service.name}: {new_status.lower()}",
            note or f"Reference {application.reference} moved to “{new_status}”.",
            link=f"/citizen/applications/{application.id}",
            category=category,
        )

    record_audit("STATUS_CHANGE", "Application", application.reference,
                 f"{old} -> {new_status}")
    return application


def new_payment_for(application, method="M-Pesa"):
    from models import Payment
    return Payment(
        reference=reference_code("PAY"),
        citizen=application.citizen,
        application=application,
        amount=application.balance,
        method=method,
        description=f"Fee for {application.service.name}",
    )


# --------------------------------------------------------------------------
# Formatting (registered as Jinja filters)
# --------------------------------------------------------------------------

def money(value):
    try:
        return f"M{float(value):,.2f}"
    except (TypeError, ValueError):
        return "M0.00"


def humanise(dt):
    """Relative time for feeds: '4 minutes ago', '3 days ago'."""
    if not dt:
        return "—"
    delta = datetime.utcnow() - dt
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = int(seconds // 60)
        return f"{m} minute{'s' if m > 1 else ''} ago"
    if seconds < 86400:
        h = int(seconds // 3600)
        return f"{h} hour{'s' if h > 1 else ''} ago"
    if delta.days < 30:
        return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
    return dt.strftime("%d %b %Y")
