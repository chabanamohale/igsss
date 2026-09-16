"""
Government employee workspace: the departmental queue, citizen lookup with
permission filtering, identity verification, and management reporting.
"""
from datetime import datetime, date, timedelta
from collections import Counter

from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, abort, jsonify)
from flask_login import login_required, current_user
from sqlalchemy import or_, func

from extensions import db
from models import (Citizen, Application, Department, Service, Employee,
                    Notification, AuditLog, AccessRequest, Payment, Document,
                    STATUS_FLOW, reference_code)
from utils import employee_required, record_audit, visible_areas, can_access
from utils.helpers import advance_status

employee_bp = Blueprint("employee", __name__)


def _dept():
    """Department of the signed-in officer (None for administrators)."""
    if current_user.is_employee and current_user.employee:
        return current_user.employee.department
    return None


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

@employee_bp.route("/")
@employee_required
def dashboard():
    dept = _dept()
    query = Application.query
    if dept:
        query = query.filter_by(department_id=dept.id)

    all_apps = query.order_by(Application.submitted_at.desc()).all()
    open_apps = [a for a in all_apps if not a.is_closed]
    counts = {
        "queue": len(open_apps),
        "unassigned": sum(1 for a in open_apps if a.officer_id is None),
        "mine": sum(1 for a in open_apps
                    if current_user.employee and a.officer_id == current_user.employee.id),
        "overdue": sum(1 for a in open_apps if a.is_overdue),
        "today": sum(1 for a in all_apps
                     if a.submitted_at.date() == date.today()),
        "closed": len(all_apps) - len(open_apps),
    }

    status_mix = Counter(a.status for a in all_apps)
    # 14-day intake trend for the sparkline
    trend = []
    for i in range(13, -1, -1):
        day = date.today() - timedelta(days=i)
        trend.append({"label": day.strftime("%d %b"),
                      "count": sum(1 for a in all_apps
                                   if a.submitted_at.date() == day)})

    pending_access = []
    if dept:
        pending_access = AccessRequest.query.filter_by(
            owning_department_id=dept.id, status="Pending").all()

    return render_template("employee/dashboard.html", dept=dept, counts=counts,
                           recent=all_apps[:8], status_mix=status_mix,
                           trend=trend, pending_access=pending_access)


# --------------------------------------------------------------------------
# Work queue
# --------------------------------------------------------------------------

@employee_bp.route("/queue")
@employee_required
def queue():
    dept = _dept()
    status = request.args.get("status", "")
    scope = request.args.get("scope", "all")
    term = request.args.get("q", "").strip()

    query = Application.query
    if dept:
        query = query.filter_by(department_id=dept.id)
    if status:
        query = query.filter_by(status=status)
    if scope == "mine" and current_user.employee:
        query = query.filter_by(officer_id=current_user.employee.id)
    elif scope == "unassigned":
        query = query.filter(Application.officer_id.is_(None))
    if term:
        query = query.join(Citizen).filter(or_(
            Application.reference.ilike(f"%{term}%"),
            Citizen.national_id.ilike(f"%{term}%"),
            Citizen.first_name.ilike(f"%{term}%"),
            Citizen.last_name.ilike(f"%{term}%"),
        ))

    items = query.order_by(Application.submitted_at.desc()).all()
    return render_template("employee/queue.html", applications=items,
                           status=status, scope=scope, term=term,
                           statuses=STATUS_FLOW, dept=dept)


@employee_bp.route("/queue/board")
@employee_required
def queue_board():
    dept = _dept()
    query = Application.query
    if dept:
        query = query.filter_by(department_id=dept.id)
    open_statuses = [s for s in STATUS_FLOW if s not in ("Rejected", "Collected")]
    items = (query.filter(Application.status.in_(open_statuses))
            .order_by(Application.submitted_at.desc()).limit(60).all())
    columns = {s: [] for s in open_statuses}
    for a in items:
        columns.setdefault(a.status, []).append(a)
    return render_template("employee/queue_board.html", columns=columns,
                           column_order=open_statuses, dept=dept)


@employee_bp.route("/settings", methods=["GET", "POST"])
@employee_required
def settings():
    if request.method == "POST":
        current_user.notify_email = request.form.get("notify_email") == "1"
        current_user.notify_sms = request.form.get("notify_sms") == "1"
        db.session.commit()
        flash("Your settings were saved.", "success")
        return redirect(url_for("employee.settings"))
    return render_template("employee/settings.html")


@employee_bp.route("/applications/<int:app_id>")
@employee_required
def application_detail(app_id):
    application = db.session.get(Application, app_id) or abort(404)
    dept = _dept()
    if dept and application.department_id != dept.id and not current_user.is_admin:
        abort(403)

    record_audit("VIEW_APPLICATION", "Application", application.reference,
                 f"Opened file for {application.citizen.full_name}")
    db.session.commit()

    officers = []
    if dept:
        officers = Employee.query.filter_by(department_id=dept.id).all()
    return render_template("employee/application_detail.html",
                           application=application, statuses=STATUS_FLOW,
                           officers=officers)


@employee_bp.route("/applications/<int:app_id>/claim", methods=["POST"])
@employee_required
def claim(app_id):
    application = db.session.get(Application, app_id) or abort(404)
    if not current_user.employee:
        abort(403)
    application.officer = current_user.employee
    if application.status == "Submitted":
        advance_status(application, "Under Review",
                       f"Assigned to {current_user.employee.full_name}.")
    record_audit("CLAIM", "Application", application.reference, "Case claimed")
    db.session.commit()
    flash(f"{application.reference} is now assigned to you.", "success")
    return redirect(url_for("employee.application_detail", app_id=app_id))


@employee_bp.route("/applications/<int:app_id>/assign", methods=["POST"])
@employee_required
def assign(app_id):
    application = db.session.get(Application, app_id) or abort(404)
    officer_id = request.form.get("officer_id")
    officer = db.session.get(Employee, int(officer_id)) if officer_id else None
    application.officer = officer
    record_audit("ASSIGN", "Application", application.reference,
                 f"Reassigned to {officer.full_name if officer else 'nobody'}")
    db.session.commit()
    flash("Case reassigned.", "success")
    return redirect(url_for("employee.application_detail", app_id=app_id))


@employee_bp.route("/applications/<int:app_id>/status", methods=["POST"])
@employee_required
def update_status(app_id):
    application = db.session.get(Application, app_id) or abort(404)
    new_status = request.form.get("status")
    note = request.form.get("note", "").strip()

    if new_status not in STATUS_FLOW:
        flash("That is not a valid status.", "danger")
        return redirect(url_for("employee.application_detail", app_id=app_id))

    if new_status in ("Approved", "Collected") and application.balance > 0:
        flash(f"There is an unpaid balance of M{application.balance:,.2f}. "
              f"Clear the fee before approving.", "warning")
        return redirect(url_for("employee.application_detail", app_id=app_id))

    if new_status == "Rejected" and not note:
        flash("Give the applicant a reason before rejecting.", "danger")
        return redirect(url_for("employee.application_detail", app_id=app_id))

    if new_status == "Rejected":
        application.decision_reason = note
    advance_status(application, new_status, note or None)
    db.session.commit()
    flash(f"{application.reference} is now “{new_status}”.", "success")
    return redirect(url_for("employee.application_detail", app_id=app_id))


@employee_bp.route("/applications/<int:app_id>/note", methods=["POST"])
@employee_required
def add_note(app_id):
    application = db.session.get(Application, app_id) or abort(404)
    note = request.form.get("note", "").strip()
    if note:
        stamp = datetime.utcnow().strftime("%d %b %Y %H:%M")
        entry = f"[{stamp}] {current_user.display_name}: {note}"
        application.officer_notes = (
            f"{application.officer_notes}\n{entry}" if application.officer_notes
            else entry)
        record_audit("NOTE", "Application", application.reference, "Case note added")
        db.session.commit()
        flash("Note added to the case file.", "success")
    return redirect(url_for("employee.application_detail", app_id=app_id))


@employee_bp.route("/documents/<int:doc_id>/verify", methods=["POST"])
@employee_required
def verify_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    doc.verified = True
    doc.verified_by = current_user.display_name
    record_audit("VERIFY_DOCUMENT", "Document", doc.original_name,
                 f"Verified for {doc.citizen.full_name}")
    db.session.commit()
    flash("Document marked as verified. It can now be reused across departments.",
          "success")
    return redirect(request.referrer or url_for("employee.dashboard"))


# --------------------------------------------------------------------------
# Citizen lookup
# --------------------------------------------------------------------------

@employee_bp.route("/search")
@employee_required
def search():
    term = request.args.get("q", "").strip()
    results = []
    if term:
        results = Citizen.query.filter(or_(
            Citizen.national_id.ilike(f"%{term}%"),
            Citizen.first_name.ilike(f"%{term}%"),
            Citizen.last_name.ilike(f"%{term}%"),
            Citizen.phone.ilike(f"%{term}%"),
        )).limit(25).all()
        record_audit("SEARCH", "Citizen", term,
                     f"Searched citizen register ({len(results)} matches)")
        db.session.commit()
    return render_template("employee/search.html", results=results, term=term)


@employee_bp.route("/citizens/<int:citizen_id>")
@employee_required
def citizen_profile(citizen_id):
    citizen = db.session.get(Citizen, citizen_id) or abort(404)
    areas = visible_areas(current_user)
    record_audit("VIEW_CITIZEN", "Citizen", citizen.national_id,
                 f"Opened profile of {citizen.full_name}")
    db.session.commit()
    return render_template("employee/citizen_profile.html", citizen=citizen,
                           areas=areas, dept=_dept())


@employee_bp.route("/citizens/<int:citizen_id>/verify", methods=["POST"])
@employee_required
def verify_citizen(citizen_id):
    """Home Affairs anchors the single citizen profile by verifying identity."""
    citizen = db.session.get(Citizen, citizen_id) or abort(404)
    dept = _dept()
    if dept and dept.code != "HA" and not current_user.is_admin:
        flash("Only Home Affairs can verify a citizen identity.", "danger")
        return redirect(url_for("employee.citizen_profile", citizen_id=citizen_id))

    citizen.verified = True
    citizen.verified_on = datetime.utcnow()
    citizen.verified_by = current_user.display_name

    Notification.send(citizen.user, "Your identity is verified",
                      "Home Affairs has confirmed your national ID. You can now "
                      "apply for any connected government service.",
                      link="/citizen/apply", category="success")
    record_audit("VERIFY_IDENTITY", "Citizen", citizen.national_id,
                 "Identity verified against the civil register")
    db.session.commit()
    flash(f"{citizen.full_name} is verified. Other departments can now rely on "
          f"this profile.", "success")
    return redirect(url_for("employee.citizen_profile", citizen_id=citizen_id))


@employee_bp.route("/verify", methods=["GET", "POST"])
@employee_required
def verify_identity():
    """Quick counter check: type a national ID, confirm the person in front of you."""
    citizen = None
    searched = False
    national_id = ""
    if request.method == "POST":
        searched = True
        national_id = request.form.get("national_id", "").strip()
        citizen = Citizen.query.filter_by(national_id=national_id).first()
        record_audit("IDENTITY_CHECK", "Citizen", national_id,
                     "Match found" if citizen else "No match in the register")
        db.session.commit()
    return render_template("employee/verify.html", citizen=citizen,
                           searched=searched, national_id=national_id)


# --------------------------------------------------------------------------
# Cross-department data sharing
# --------------------------------------------------------------------------

@employee_bp.route("/access-requests", methods=["GET", "POST"])
@employee_required
def access_requests():
    dept = _dept()
    if request.method == "POST":
        citizen = db.session.get(Citizen, int(request.form["citizen_id"]))
        owner = db.session.get(Department, int(request.form["owning_department_id"]))
        req = AccessRequest(
            reference=reference_code("REQ"),
            requesting_department=dept, owning_department=owner,
            citizen=citizen, requested_by=current_user.display_name,
            reason=request.form.get("reason", "").strip(),
        )
        db.session.add(req)
        record_audit("ACCESS_REQUEST", "AccessRequest", req.reference,
                     f"Requested {owner.name} data on {citizen.full_name}")
        db.session.commit()
        flash(f"Request {req.reference} sent to {owner.name}.", "success")
        return redirect(url_for("employee.access_requests"))

    incoming = AccessRequest.query.filter_by(
        owning_department_id=dept.id).all() if dept else AccessRequest.query.all()
    outgoing = AccessRequest.query.filter_by(
        requesting_department_id=dept.id).all() if dept else []
    return render_template("employee/access_requests.html", incoming=incoming,
                           outgoing=outgoing, dept=dept)


@employee_bp.route("/access-requests/<int:req_id>/<decision>", methods=["POST"])
@employee_required
def decide_access(req_id, decision):
    req = db.session.get(AccessRequest, req_id) or abort(404)
    if decision not in ("grant", "deny"):
        abort(400)
    req.status = "Granted" if decision == "grant" else "Denied"
    req.decided_by = current_user.display_name
    req.decided_at = datetime.utcnow()
    record_audit("ACCESS_DECISION", "AccessRequest", req.reference,
                 f"{req.status} to {req.requesting_department.name}")
    db.session.commit()
    flash(f"Request {req.reference} {req.status.lower()}.", "info")
    return redirect(url_for("employee.access_requests"))


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

@employee_bp.route("/reports")
@employee_required
def reports():
    dept = _dept()
    query = Application.query
    if dept:
        query = query.filter_by(department_id=dept.id)
    apps = query.all()

    by_status = Counter(a.status for a in apps)
    by_service = Counter(a.service.name for a in apps if a.service)
    by_district = Counter(a.citizen.district for a in apps
                          if a.citizen and a.citizen.district)

    closed = [a for a in apps if a.is_closed]
    turnaround = None
    if closed:
        days = [(a.updated_at - a.submitted_at).days for a in closed]
        turnaround = round(sum(days) / len(days), 1)

    revenue = db.session.query(func.sum(Payment.amount)).filter(
        Payment.status == "Paid").scalar() or 0
    if dept:
        revenue = sum(p.amount for p in Payment.query.filter_by(status="Paid").all()
                      if p.application and p.application.department_id == dept.id)

    monthly = Counter(a.submitted_at.strftime("%b %Y") for a in apps)

    record_audit("REPORT", "Report", dept.code if dept else "ALL",
                 "Generated departmental performance report")
    db.session.commit()

    return render_template("employee/reports.html", dept=dept, total=len(apps),
                           by_status=by_status, by_service=by_service.most_common(8),
                           by_district=by_district.most_common(10),
                           turnaround=turnaround, revenue=revenue,
                           monthly=sorted(monthly.items()), approved=len(closed))


@employee_bp.route("/activity")
@employee_required
def activity():
    """The officer's own trail — every employee can see what they themselves did."""
    logs = AuditLog.query.filter_by(user_id=current_user.id).order_by(
        AuditLog.timestamp.desc()).limit(200).all()
    return render_template("employee/activity.html", logs=logs)
