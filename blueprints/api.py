"""
REST API — read and write endpoints returning JSON, used by the interactive
parts of the interface (live notifications, favourites, the drag-and-drop
queue board, and the charts on the reporting pages).

All endpoints below sit under /api/v1. Two public, read-only endpoints do
not require a session (service catalogue, application tracking — the same
data already visible on the public site). Everything else is session
authenticated exactly like the rest of the application; there is no
separate API token, so a signed-in citizen or officer's own browser session
is what authorises these calls.
"""
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func

from extensions import db
from models import (Service, Department, Application, StatusHistory,
                    Favourite, Review, Notification, AuditLog, STATUS_FLOW)
from utils.helpers import advance_status

api_bp = Blueprint("api", __name__)


def _citizen_or_404():
    if not current_user.is_authenticated or not current_user.citizen:
        abort(403)
    return current_user.citizen


# --------------------------------------------------------------------------
# Public, read-only
# --------------------------------------------------------------------------

@api_bp.route("/services")
def services():
    """Service catalogue as JSON — the same data as /services."""
    dept = request.args.get("department", "")
    q = request.args.get("q", "").strip().lower()
    query = Service.query.filter_by(active=True)
    if dept:
        d = Department.query.filter_by(code=dept).first()
        if d:
            query = query.filter_by(department_id=d.id)
    items = query.order_by(Service.name).all()
    if q:
        items = [s for s in items if q in s.name.lower() or q in (s.description or "").lower()]
    return jsonify({"count": len(items), "services": [
        {"code": s.code, "name": s.name, "department": s.department.code,
         "fee": s.fee, "processing_days": s.processing_days,
         "rating": s.average_rating, "reviews": s.review_count}
        for s in items
    ]})


@api_bp.route("/track/<reference>")
def track(reference):
    app_ = Application.query.filter_by(reference=reference.upper()).first()
    if not app_:
        return jsonify({"found": False}), 404
    return jsonify({
        "found": True, "reference": app_.reference, "status": app_.status,
        "service": app_.service.name, "department": app_.department.name,
        "submitted_at": app_.submitted_at.isoformat(),
        "due_date": app_.due_date.isoformat() if app_.due_date else None,
        "is_overdue": app_.is_overdue,
        "history": [{"status": h.to_status, "at": h.changed_at.isoformat()}
                   for h in app_.history],
    })


# --------------------------------------------------------------------------
# Notifications (any signed-in role)
# --------------------------------------------------------------------------

@api_bp.route("/notifications")
@login_required
def notifications():
    items = current_user.notifications[:8]
    return jsonify({
        "unread": current_user.unread_count,
        "items": [{"title": n.title, "message": n.message, "link": n.link or "#",
                   "read": n.read} for n in items],
    })


@api_bp.route("/notifications/count")
@login_required
def notifications_count():
    return jsonify({"unread": current_user.unread_count})


# --------------------------------------------------------------------------
# Favourites (citizens)
# --------------------------------------------------------------------------

@api_bp.route("/favourites/<int:service_id>", methods=["POST"])
@login_required
def toggle_favourite(service_id):
    me = _citizen_or_404()
    service = Service.query.get_or_404(service_id)
    existing = Favourite.query.filter_by(citizen_id=me.id, service_id=service.id).first()
    if existing:
        db.session.delete(existing)
        favourited = False
    else:
        db.session.add(Favourite(citizen_id=me.id, service_id=service.id))
        favourited = True
    db.session.commit()
    return jsonify({"favourited": favourited, "service_id": service.id})


# --------------------------------------------------------------------------
# Reviews (citizens, only on their own decided applications)
# --------------------------------------------------------------------------

@api_bp.route("/reviews", methods=["POST"])
@login_required
def submit_review():
    me = _citizen_or_404()
    data = request.get_json(silent=True) or request.form
    application_id = data.get("application_id")
    rating = data.get("rating")
    comment = (data.get("comment") or "").strip()

    app_ = Application.query.get_or_404(int(application_id)) if application_id else None
    if not app_ or app_.citizen_id != me.id or not app_.is_closed:
        return jsonify({"ok": False, "message": "That application cannot be reviewed."}), 400
    try:
        rating = max(1, min(5, int(rating)))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "message": "Choose a star rating."}), 400

    existing = Review.query.filter_by(application_id=app_.id).first()
    if existing:
        existing.rating, existing.comment = rating, comment
    else:
        db.session.add(Review(citizen_id=me.id, service_id=app_.service_id,
                              application_id=app_.id, rating=rating, comment=comment))
    db.session.commit()
    return jsonify({"ok": True, "message": "Thank you — your review was saved."})


# --------------------------------------------------------------------------
# Queue board — drag and drop status changes (employees / admin)
# --------------------------------------------------------------------------

@api_bp.route("/queue/status", methods=["POST"])
@login_required
def queue_status():
    if not (current_user.is_employee or current_user.is_admin):
        return jsonify({"ok": False, "message": "Not permitted."}), 403
    data = request.get_json(silent=True) or {}
    app_ = Application.query.get(data.get("application_id"))
    new_status = data.get("status")
    if not app_ or new_status not in STATUS_FLOW:
        return jsonify({"ok": False, "message": "Unknown application or status."}), 400

    emp = current_user.employee
    if emp and app_.department_id != emp.department_id and not current_user.is_admin:
        return jsonify({"ok": False, "message": "That case belongs to another department."}), 403

    advance_status(app_, new_status, note="Moved on the queue board.")
    db.session.commit()
    return jsonify({"ok": True, "message": f"{app_.reference} moved to {new_status}."})


# --------------------------------------------------------------------------
# Admin / reporting statistics for charts
# --------------------------------------------------------------------------

@api_bp.route("/stats")
@login_required
def stats():
    if not (current_user.is_admin or current_user.is_employee):
        abort(403)

    scope = Application.query
    if current_user.is_employee and current_user.employee and not current_user.is_admin:
        scope = scope.filter_by(department_id=current_user.employee.department_id)

    apps = scope.all()
    by_status = {}
    by_department = {}
    daily = {}
    for a in apps:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        dep = a.department.code if a.department else "—"
        by_department[dep] = by_department.get(dep, 0) + 1
        day = a.submitted_at.date().isoformat()
        daily[day] = daily.get(day, 0) + 1

    last_14 = []
    for i in range(13, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).date().isoformat()
        last_14.append({"date": d, "count": daily.get(d, 0)})

    return jsonify({
        "by_status": by_status,
        "by_department": by_department,
        "last_14_days": last_14,
        "total": len(apps),
    })
