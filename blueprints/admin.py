"""
System administration: accounts and roles, department and service catalogue,
the permission matrix, and the full audit trail.
"""
from datetime import datetime, date, timedelta
from collections import Counter

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user
from sqlalchemy import or_

from extensions import db
from models import (User, Citizen, Employee, Department, Service, Application,
                    Payment, AuditLog, Notification, Document, DEPARTMENT_COLOURS)
from utils import admin_required, record_audit, ACCESS_MATRIX, AREA_LABELS

admin_bp = Blueprint("admin", __name__)


# --------------------------------------------------------------------------
# Overview
# --------------------------------------------------------------------------

@admin_bp.route("/")
@admin_required
def dashboard():
    apps = Application.query.all()
    stats = {
        "users": User.query.count(),
        "citizens": Citizen.query.count(),
        "employees": Employee.query.count(),
        "departments": Department.query.count(),
        "services": Service.query.count(),
        "applications": len(apps),
        "open": sum(1 for a in apps if not a.is_closed),
        "overdue": sum(1 for a in apps if a.is_overdue),
        "documents": Document.query.count(),
        "revenue": sum(p.amount for p in Payment.query.filter_by(status="Paid").all()),
        "unverified": Citizen.query.filter_by(verified=False).count(),
        "suspended": User.query.filter_by(active=False).count(),
    }

    load = []
    for d in Department.query.order_by(Department.id).all():
        dept_apps = [a for a in apps if a.department_id == d.id]
        load.append({
            "dept": d,
            "total": len(dept_apps),
            "open": sum(1 for a in dept_apps if not a.is_closed),
            "overdue": sum(1 for a in dept_apps if a.is_overdue),
            "staff": len(d.employees),
        })

    recent_logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(12).all()
    signins = AuditLog.query.filter_by(action="LOGIN_FAILED").filter(
        AuditLog.timestamp > datetime.utcnow() - timedelta(days=7)).count()

    return render_template("admin/dashboard.html", stats=stats, load=load,
                           recent_logs=recent_logs, failed_signins=signins)


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------

@admin_bp.route("/users")
@admin_required
def users():
    role = request.args.get("role", "")
    term = request.args.get("q", "").strip()
    query = User.query
    if role:
        query = query.filter_by(role=role)
    if term:
        query = query.filter(or_(User.username.ilike(f"%{term}%"),
                                 User.email.ilike(f"%{term}%")))
    return render_template("admin/users.html",
                           users=query.order_by(User.created_at.desc()).all(),
                           role=role, term=term)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def new_user():
    """Create a staff or administrator account."""
    if request.method == "POST":
        form = {k: v.strip() for k, v in request.form.items()}
        if User.query.filter(or_(User.username == form["username"],
                                 User.email == form["email"].lower())).first():
            flash("That username or email is already in use.", "danger")
            return render_template("admin/user_form.html", form=form)
        if len(form.get("password", "")) < 8:
            flash("Set a password of at least 8 characters.", "danger")
            return render_template("admin/user_form.html", form=form)

        user = User(username=form["username"], email=form["email"].lower(),
                    role=form.get("role", "employee"))
        user.set_password(form["password"])
        db.session.add(user)

        if user.role == "employee":
            db.session.add(Employee(
                user=user, employee_no=form.get("employee_no") or f"EMP{datetime.utcnow():%H%M%S}",
                full_name=form.get("full_name", form["username"]),
                department_id=int(form["department_id"]) if form.get("department_id") else None,
                position=form.get("position"), office=form.get("office"),
                phone=form.get("phone"),
                can_approve=bool(form.get("can_approve")),
                is_manager=bool(form.get("is_manager")),
            ))

        Notification.send(user, "Your account is ready",
                          "An administrator created this account for you. "
                          "Change your password the first time you sign in.",
                          link="/auth/password", category="info")
        record_audit("CREATE_USER", "User", user.username,
                     f"Created {user.role} account")
        db.session.commit()
        flash(f"Account “{user.username}” created.", "success")
        return redirect(url_for("admin.users"))

    return render_template("admin/user_form.html", form={})


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.id == current_user.id:
        flash("You cannot suspend your own account.", "warning")
        return redirect(url_for("admin.users"))
    user.active = not user.active
    record_audit("TOGGLE_USER", "User", user.username,
                 "Reinstated" if user.active else "Suspended")
    db.session.commit()
    flash(f"{user.username} is now {'active' if user.active else 'suspended'}.",
          "info")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/role", methods=["POST"])
@admin_required
def change_role(user_id):
    user = db.session.get(User, user_id) or abort(404)
    new_role = request.form.get("role")
    if new_role in ("citizen", "employee", "admin"):
        old = user.role
        user.role = new_role
        record_audit("CHANGE_ROLE", "User", user.username, f"{old} -> {new_role}")
        db.session.commit()
        flash(f"{user.username} is now a {new_role}.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reset", methods=["POST"])
@admin_required
def reset_password(user_id):
    user = db.session.get(User, user_id) or abort(404)
    temp = f"Reset{datetime.utcnow():%d%m%H%M}!"
    user.set_password(temp)
    record_audit("RESET_PASSWORD", "User", user.username, "Password reset by admin")
    db.session.commit()
    flash(f"Temporary password for {user.username}: {temp} — pass it on in person.",
          "warning")
    return redirect(url_for("admin.users"))


# --------------------------------------------------------------------------
# Departments and services
# --------------------------------------------------------------------------

@admin_bp.route("/departments", methods=["GET", "POST"])
@admin_required
def departments():
    if request.method == "POST":
        d = Department(
            code=request.form["code"].strip().upper(),
            name=request.form["name"].strip(),
            ministry=request.form.get("ministry", "").strip(),
            description=request.form.get("description", "").strip(),
            contact_phone=request.form.get("contact_phone", "").strip(),
            contact_email=request.form.get("contact_email", "").strip(),
            head_office=request.form.get("head_office", "").strip(),
        )
        db.session.add(d)
        record_audit("CREATE_DEPARTMENT", "Department", d.code, d.name)
        db.session.commit()
        flash(f"{d.name} added.", "success")
        return redirect(url_for("admin.departments"))
    return render_template("admin/departments.html",
                           departments=Department.query.order_by(Department.id).all())


@admin_bp.route("/services", methods=["GET", "POST"])
@admin_required
def services():
    if request.method == "POST":
        s = Service(
            code=request.form["code"].strip().upper(),
            name=request.form["name"].strip(),
            department_id=int(request.form["department_id"]),
            description=request.form.get("description", "").strip(),
            fee=float(request.form.get("fee") or 0),
            processing_days=int(request.form.get("processing_days") or 14),
            required_documents=request.form.get("required_documents", "").strip(),
        )
        db.session.add(s)
        record_audit("CREATE_SERVICE", "Service", s.code, s.name)
        db.session.commit()
        flash(f"{s.name} added to the catalogue.", "success")
        return redirect(url_for("admin.services"))
    return render_template("admin/services.html",
                           services=Service.query.order_by(Service.department_id).all())


@admin_bp.route("/services/<int:service_id>/toggle", methods=["POST"])
@admin_required
def toggle_service(service_id):
    s = db.session.get(Service, service_id) or abort(404)
    s.active = not s.active
    record_audit("TOGGLE_SERVICE", "Service", s.code,
                 "Opened" if s.active else "Closed to new applications")
    db.session.commit()
    flash(f"{s.name} is {'open' if s.active else 'closed'} to new applications.",
          "info")
    return redirect(url_for("admin.services"))


@admin_bp.route("/permissions")
@admin_required
def permissions():
    """Read-only view of the cross-department access matrix enforced in code."""
    return render_template("admin/permissions.html", matrix=ACCESS_MATRIX,
                           labels=AREA_LABELS, colours=DEPARTMENT_COLOURS,
                           departments=Department.query.order_by(Department.id).all())


# --------------------------------------------------------------------------
# Audit trail
# --------------------------------------------------------------------------

@admin_bp.route("/audit")
@admin_required
def audit():
    action = request.args.get("action", "")
    term = request.args.get("q", "").strip()
    query = AuditLog.query
    if action:
        query = query.filter_by(action=action)
    if term:
        query = query.filter(or_(AuditLog.actor.ilike(f"%{term}%"),
                                 AuditLog.entity_ref.ilike(f"%{term}%"),
                                 AuditLog.description.ilike(f"%{term}%")))
    logs = query.order_by(AuditLog.timestamp.desc()).limit(400).all()
    actions = sorted({a.action for a in AuditLog.query.all() if a.action})
    busiest = Counter(l.actor for l in AuditLog.query.all()).most_common(5)
    return render_template("admin/audit.html", logs=logs, actions=actions,
                           action=action, term=term, busiest=busiest)


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    if request.method == "POST":
        current_user.notify_email = request.form.get("notify_email") == "1"
        current_user.notify_sms = request.form.get("notify_sms") == "1"
        db.session.commit()
        flash("Your settings were saved.", "success")
        return redirect(url_for("admin.settings"))
    return render_template("admin/settings.html")
