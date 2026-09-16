"""Public-facing pages: landing, service catalogue, status lookup, help."""
from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import current_user

from models import Service, Department, Application, Citizen
from extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard_router"))
    departments = Department.query.order_by(Department.id).all()
    featured = Service.query.filter_by(active=True).limit(6).all()
    stats = {
        "departments": Department.query.count(),
        "services": Service.query.filter_by(active=True).count(),
        "citizens": Citizen.query.count(),
        "processed": Application.query.filter(
            Application.status.in_(["Approved", "Collected"])).count(),
    }
    return render_template("main/home.html", departments=departments,
                           featured=featured, stats=stats)


@main_bp.route("/go")
def dashboard_router():
    """Send each signed-in user to the right home screen."""
    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))
    if current_user.is_admin:
        return redirect(url_for("admin.dashboard"))
    if current_user.is_employee:
        return redirect(url_for("employee.dashboard"))
    return redirect(url_for("citizen.dashboard"))


@main_bp.route("/services")
def services():
    dept_code = request.args.get("department", "")
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "name")
    query = Service.query.filter_by(active=True)
    if dept_code:
        dept = Department.query.filter_by(code=dept_code).first()
        if dept:
            query = query.filter_by(department_id=dept.id)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Service.name.ilike(like), Service.description.ilike(like)))
    order = {"fee": Service.fee, "days": Service.processing_days,
             "name": Service.name}.get(sort, Service.name)
    services = query.order_by(order).all()
    return render_template("main/services.html", services=services,
                           selected=dept_code, q=q, sort=sort)


@main_bp.route("/services/<code>")
def service_detail(code):
    service = Service.query.filter_by(code=code).first_or_404()
    return render_template("main/service_detail.html", service=service)


@main_bp.route("/track", methods=["GET", "POST"])
def track():
    """Look up an application by its reference without signing in."""
    application = None
    searched = False
    reference = ""
    if request.method == "POST":
        searched = True
        reference = request.form.get("reference", "").strip().upper()
        application = Application.query.filter_by(reference=reference).first()
    return render_template("main/track.html", application=application,
                           searched=searched, reference=reference)


@main_bp.route("/help")
def help_page():
    return render_template("main/help.html")
