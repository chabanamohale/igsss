"""
Role-based access control and the cross-department data-sharing matrix.

The documentation's privacy requirement is that employees see only what their
official duties require. That rule lives here, in one place, so every route
enforces the same policy.
"""
from functools import wraps

from flask import abort, flash, redirect, url_for, request
from flask_login import current_user


# Which record areas each department may read on a citizen profile.
# Keys are department codes; values are record-area keys used in templates.
ACCESS_MATRIX = {
    "HA": {"identity", "civil", "passport", "documents", "applications"},
    "POL": {"identity", "police", "traffic_licence", "vehicle", "applications"},
    "TRF": {"identity", "traffic_licence", "vehicle", "applications"},
    "FIN": {"identity", "finance", "payments", "applications"},
    "PEN": {"identity", "pension", "civil", "applications"},
    "PAS": {"identity", "passport", "civil", "documents", "applications"},
}

AREA_LABELS = {
    "identity": "Identity and contact details",
    "civil": "Civil registration",
    "passport": "Passport records",
    "police": "Police clearance",
    "traffic_licence": "Driver licence",
    "vehicle": "Vehicle registration",
    "finance": "Tax and revenue",
    "pension": "Pension and grants",
    "payments": "Payment history",
    "documents": "Uploaded documents",
    "applications": "Service applications",
}


def can_access(user, area):
    """True if this user's department is cleared to read the given record area."""
    if user.is_anonymous:
        return False
    if user.is_admin:
        return True
    if user.is_employee and user.employee and user.employee.department:
        return area in ACCESS_MATRIX.get(user.employee.department.code, set())
    return False


def visible_areas(user):
    if user.is_admin:
        return set(AREA_LABELS)
    if user.is_employee and user.employee and user.employee.department:
        return ACCESS_MATRIX.get(user.employee.department.code, set())
    return set()


# --------------------------------------------------------------------------
# Decorators
# --------------------------------------------------------------------------

def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))
            if current_user.role not in roles:
                flash("Your account does not have access to that area.", "danger")
                return redirect(url_for("main.home"))
            return view(*args, **kwargs)
        return wrapped
    return decorator


citizen_required = role_required("citizen")
employee_required = role_required("employee", "admin")
admin_required = role_required("admin")


def department_required(*codes):
    """Restrict a view to employees of specific departments."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login", next=request.path))
            if current_user.is_admin:
                return view(*args, **kwargs)
            emp = getattr(current_user, "employee", None)
            if not emp or not emp.department or emp.department.code not in codes:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def area_required(area):
    """Guard a view behind a record-area permission."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not can_access(current_user, area):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator
