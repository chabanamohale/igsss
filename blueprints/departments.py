"""
The six departmental modules. Each one exposes the records that department owns
and writes to, on top of the shared citizen profile anchored by Home Affairs.
"""
from datetime import datetime, date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from extensions import db
from models import (Citizen, Department, CivilRecord, Vehicle, DriverLicence,
                    Passport, PoliceRecord, PensionRecord, FinanceRecord,
                    Application, Payment, Notification, reference_code)
from utils import employee_required, department_required, record_audit

departments_bp = Blueprint("departments", __name__)


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _citizen_or_404(citizen_id):
    return db.session.get(Citizen, int(citizen_id)) or abort(404)


# ==========================================================================
# Home Affairs — identity and civil registration
# ==========================================================================

@departments_bp.route("/home-affairs")
@employee_required
@department_required("HA")
def home_affairs():
    unverified = Citizen.query.filter_by(verified=False).order_by(
        Citizen.created_at.desc()).all()
    recent_records = CivilRecord.query.order_by(
        CivilRecord.registered_at.desc()).limit(10).all()
    stats = {
        "citizens": Citizen.query.count(),
        "verified": Citizen.query.filter_by(verified=True).count(),
        "pending": len(unverified),
        "civil": CivilRecord.query.count(),
    }
    return render_template("departments/home_affairs.html", unverified=unverified,
                           recent=recent_records, stats=stats)


@departments_bp.route("/home-affairs/civil", methods=["POST"])
@employee_required
@department_required("HA")
def register_civil():
    citizen = _citizen_or_404(request.form["citizen_id"])
    record = CivilRecord(
        citizen=citizen,
        record_type=request.form.get("record_type", "Birth"),
        reference=reference_code("CIV"),
        event_date=_parse_date(request.form.get("event_date")),
        place=request.form.get("place", "").strip(),
        details=request.form.get("details", "").strip(),
    )
    db.session.add(record)
    Notification.send(citizen.user, "Civil record registered",
                      f"A {record.record_type.lower()} record was added to your "
                      f"profile. Reference {record.reference}.",
                      link="/citizen/records", category="info")
    record_audit("CIVIL_REGISTER", "CivilRecord", record.reference,
                 f"{record.record_type} registered for {citizen.full_name}")
    db.session.commit()
    flash(f"{record.record_type} record registered as {record.reference}.", "success")
    return redirect(url_for("departments.home_affairs"))


# ==========================================================================
# Passport Services
# ==========================================================================

@departments_bp.route("/passport")
@employee_required
@department_required("PAS", "HA")
def passport():
    passports = Passport.query.order_by(Passport.issue_date.desc()).limit(50).all()
    dept = Department.query.filter_by(code="PAS").first()
    queue = Application.query.filter_by(department_id=dept.id).filter(
        ~Application.status.in_(["Approved", "Rejected", "Collected"])).all() if dept else []
    expiring = [p for p in Passport.query.all()
                if p.expiry_date and 0 < (p.expiry_date - date.today()).days < 365]
    return render_template("departments/passport.html", passports=passports,
                           queue=queue, expiring=expiring)


@departments_bp.route("/passport/issue", methods=["POST"])
@employee_required
@department_required("PAS", "HA")
def issue_passport():
    citizen = _citizen_or_404(request.form["citizen_id"])
    if not citizen.verified:
        flash("This citizen's identity is not verified. Home Affairs must verify "
              "the profile before a travel document is issued.", "danger")
        return redirect(url_for("departments.passport"))

    issue = _parse_date(request.form.get("issue_date")) or date.today()
    p = Passport(
        citizen=citizen,
        passport_no=request.form.get("passport_no", "").strip().upper()
                    or f"LS{reference_code('')[1:7]}",
        passport_type=request.form.get("passport_type", "Ordinary"),
        issue_date=issue,
        expiry_date=issue + timedelta(days=365 * 10),
        issuing_office=request.form.get("issuing_office", "Maseru Head Office"),
    )
    db.session.add(p)
    Notification.send(citizen.user, "Passport issued",
                      f"Passport {p.passport_no} is ready for collection at "
                      f"{p.issuing_office}.", link="/citizen/records",
                      category="success")
    record_audit("ISSUE_PASSPORT", "Passport", p.passport_no,
                 f"Issued to {citizen.full_name}")
    db.session.commit()
    flash(f"Passport {p.passport_no} issued.", "success")
    return redirect(url_for("departments.passport"))


# ==========================================================================
# Police — clearance certificates
# ==========================================================================

@departments_bp.route("/police")
@employee_required
@department_required("POL")
def police():
    records = PoliceRecord.query.order_by(PoliceRecord.id.desc()).limit(50).all()
    pending = [r for r in records if r.clearance_status == "Pending"]
    flagged = [r for r in records if r.clearance_status == "Flagged"]
    return render_template("departments/police.html", records=records,
                           pending=pending, flagged=flagged)


@departments_bp.route("/police/clearance", methods=["POST"])
@employee_required
@department_required("POL")
def create_clearance():
    citizen = _citizen_or_404(request.form["citizen_id"])
    rec = PoliceRecord(
        citizen=citizen,
        case_number=reference_code("PCC"),
        record_type=request.form.get("record_type", "Clearance"),
        clearance_status="Pending",
        fingerprints_taken=bool(request.form.get("fingerprints")),
        remarks=request.form.get("remarks", "").strip(),
        station=request.form.get("station", "Police Headquarters, Maseru"),
    )
    db.session.add(rec)
    record_audit("PCC_OPEN", "PoliceRecord", rec.case_number,
                 f"Clearance file opened for {citizen.full_name}")
    db.session.commit()
    flash(f"Clearance file {rec.case_number} opened.", "success")
    return redirect(url_for("departments.police"))


@departments_bp.route("/police/<int:rec_id>/decide", methods=["POST"])
@employee_required
@department_required("POL")
def decide_clearance(rec_id):
    rec = db.session.get(PoliceRecord, rec_id) or abort(404)
    outcome = request.form.get("outcome", "Clear")
    rec.clearance_status = outcome
    rec.remarks = request.form.get("remarks", rec.remarks)
    if outcome == "Clear":
        rec.issued_date = date.today()
        rec.expiry_date = date.today() + timedelta(days=180)
    Notification.send(
        rec.citizen.user, f"Police clearance: {outcome.lower()}",
        f"Case {rec.case_number} has been decided. "
        + ("Your certificate is valid for six months."
           if outcome == "Clear" else "Contact the issuing station for details."),
        link="/citizen/records",
        category="success" if outcome == "Clear" else "warning")
    record_audit("PCC_DECISION", "PoliceRecord", rec.case_number, outcome)
    db.session.commit()
    flash(f"Case {rec.case_number} marked “{outcome}”.", "success")
    return redirect(url_for("departments.police"))


# ==========================================================================
# Traffic & Transport — licences and vehicles
# ==========================================================================

@departments_bp.route("/traffic")
@employee_required
@department_required("TRF")
def traffic():
    licences = DriverLicence.query.order_by(DriverLicence.id.desc()).limit(40).all()
    vehicles = Vehicle.query.order_by(Vehicle.id.desc()).limit(40).all()
    expiring = [v for v in Vehicle.query.all()
                if v.licence_expiry and v.licence_expiry < date.today() + timedelta(days=60)]
    return render_template("departments/traffic.html", licences=licences,
                           vehicles=vehicles, expiring=expiring)


@departments_bp.route("/traffic/licence", methods=["POST"])
@employee_required
@department_required("TRF")
def issue_licence():
    citizen = _citizen_or_404(request.form["citizen_id"])
    if not citizen.verified:
        flash("Identity must be verified by Home Affairs first.", "danger")
        return redirect(url_for("departments.traffic"))
    issue = _parse_date(request.form.get("issue_date")) or date.today()
    lic = DriverLicence(
        citizen=citizen,
        licence_no=request.form.get("licence_no", "").strip().upper()
                   or reference_code("DL"),
        licence_class=request.form.get("licence_class", "B"),
        issue_date=issue,
        expiry_date=issue + timedelta(days=365 * 5),
        restrictions=request.form.get("restrictions", "").strip(),
    )
    db.session.add(lic)
    Notification.send(citizen.user, "Driver licence issued",
                      f"Licence {lic.licence_no}, class {lic.licence_class}, "
                      f"valid to {lic.expiry_date:%d %b %Y}.",
                      link="/citizen/records", category="success")
    record_audit("ISSUE_LICENCE", "DriverLicence", lic.licence_no,
                 f"Issued to {citizen.full_name}")
    db.session.commit()
    flash(f"Licence {lic.licence_no} issued.", "success")
    return redirect(url_for("departments.traffic"))


@departments_bp.route("/traffic/vehicle", methods=["POST"])
@employee_required
@department_required("TRF")
def register_vehicle():
    citizen = _citizen_or_404(request.form["citizen_id"])
    v = Vehicle(
        citizen=citizen,
        registration_no=request.form.get("registration_no", "").strip().upper(),
        make=request.form.get("make", "").strip(),
        model=request.form.get("model", "").strip(),
        year=int(request.form.get("year") or 0) or None,
        colour=request.form.get("colour", "").strip(),
        engine_no=request.form.get("engine_no", "").strip(),
        chassis_no=request.form.get("chassis_no", "").strip(),
        licence_expiry=date.today() + timedelta(days=365),
        roadworthy_expiry=date.today() + timedelta(days=365),
    )
    db.session.add(v)
    record_audit("REGISTER_VEHICLE", "Vehicle", v.registration_no,
                 f"Registered to {citizen.full_name}")
    db.session.commit()
    flash(f"Vehicle {v.registration_no} registered.", "success")
    return redirect(url_for("departments.traffic"))


@departments_bp.route("/traffic/vehicle/<int:veh_id>/renew", methods=["POST"])
@employee_required
@department_required("TRF")
def renew_vehicle(veh_id):
    v = db.session.get(Vehicle, veh_id) or abort(404)
    v.licence_expiry = date.today() + timedelta(days=365)
    record_audit("RENEW_VEHICLE", "Vehicle", v.registration_no, "Licence renewed")
    db.session.commit()
    flash(f"{v.registration_no} licensed to {v.licence_expiry:%d %b %Y}.", "success")
    return redirect(url_for("departments.traffic"))


# ==========================================================================
# Finance — revenue and taxpayer accounts
# ==========================================================================

@departments_bp.route("/finance")
@employee_required
@department_required("FIN")
def finance():
    payments = Payment.query.order_by(Payment.created_at.desc()).limit(60).all()
    collected = sum(p.amount for p in Payment.query.filter_by(status="Paid").all())
    outstanding = sum(p.amount for p in Payment.query.filter_by(status="Pending").all())
    accounts = FinanceRecord.query.all()
    by_department = {}
    for p in Payment.query.filter_by(status="Paid").all():
        if p.application and p.application.department:
            name = p.application.department.name
            by_department[name] = by_department.get(name, 0) + p.amount
    return render_template("departments/finance.html", payments=payments,
                           collected=collected, outstanding=outstanding,
                           accounts=accounts,
                           by_department=sorted(by_department.items(),
                                                key=lambda x: -x[1]))


@departments_bp.route("/finance/account", methods=["POST"])
@employee_required
@department_required("FIN")
def update_account():
    citizen = _citizen_or_404(request.form["citizen_id"])
    rec = citizen.finance_record
    if not rec:
        rec = FinanceRecord(citizen=citizen, tax_number=reference_code("TAX"))
        db.session.add(rec)
    rec.tax_status = request.form.get("tax_status", "Compliant")
    rec.outstanding_balance = float(request.form.get("outstanding_balance") or 0)
    rec.last_filed = _parse_date(request.form.get("last_filed")) or date.today()
    record_audit("TAX_UPDATE", "FinanceRecord", rec.tax_number,
                 f"Account updated for {citizen.full_name}")
    db.session.commit()
    flash("Taxpayer account updated.", "success")
    return redirect(url_for("departments.finance"))


@departments_bp.route("/finance/payments/<int:pay_id>/reverse", methods=["POST"])
@employee_required
@department_required("FIN")
def reverse_payment(pay_id):
    p = db.session.get(Payment, pay_id) or abort(404)
    p.status = "Reversed"
    record_audit("PAYMENT_REVERSAL", "Payment", p.reference,
                 request.form.get("reason", "Reversed by Finance"))
    db.session.commit()
    flash(f"Payment {p.reference} reversed.", "warning")
    return redirect(url_for("departments.finance"))


# ==========================================================================
# Pensions — Old Age Pension and grants
# ==========================================================================

@departments_bp.route("/pensions")
@employee_required
@department_required("PEN")
def pensions():
    records = PensionRecord.query.order_by(PensionRecord.id.desc()).all()
    # Age-based eligibility read straight off the Home Affairs profile
    eligible_unregistered = [
        c for c in Citizen.query.all()
        if c.pension_eligible and not c.pension_records
    ]
    payroll = sum(r.monthly_amount for r in records if r.status == "Active")
    return render_template("departments/pensions.html", records=records,
                           candidates=eligible_unregistered, payroll=payroll)


@departments_bp.route("/pensions/enrol", methods=["POST"])
@employee_required
@department_required("PEN")
def enrol_pension():
    citizen = _citizen_or_404(request.form["citizen_id"])
    grant = request.form.get("grant_type", "Old Age Pension")

    if grant == "Old Age Pension" and not citizen.pension_eligible:
        flash(f"{citizen.full_name} is {citizen.age or 'of unknown age'}. The Old "
              f"Age Pension starts at 70.", "danger")
        return redirect(url_for("departments.pensions"))
    if not citizen.verified:
        flash("Identity must be verified by Home Affairs before enrolment.", "danger")
        return redirect(url_for("departments.pensions"))

    rec = PensionRecord(
        citizen=citizen, pension_no=reference_code("PEN"), grant_type=grant,
        monthly_amount=float(request.form.get("monthly_amount") or 850),
        pay_point=request.form.get("pay_point", "Maseru Post Office"),
        next_payment=date.today().replace(day=1) + timedelta(days=32),
        registered_on=date.today(),
    )
    db.session.add(rec)
    Notification.send(citizen.user, "Enrolled for a grant",
                      f"{grant} — M{rec.monthly_amount:,.2f} monthly at "
                      f"{rec.pay_point}. Pension number {rec.pension_no}.",
                      link="/citizen/records", category="success")
    record_audit("PENSION_ENROL", "PensionRecord", rec.pension_no,
                 f"{grant} enrolment for {citizen.full_name}")
    db.session.commit()
    flash(f"{citizen.full_name} enrolled as {rec.pension_no}.", "success")
    return redirect(url_for("departments.pensions"))


@departments_bp.route("/pensions/<int:rec_id>/suspend", methods=["POST"])
@employee_required
@department_required("PEN")
def suspend_pension(rec_id):
    rec = db.session.get(PensionRecord, rec_id) or abort(404)
    rec.status = "Suspended" if rec.status == "Active" else "Active"
    record_audit("PENSION_STATUS", "PensionRecord", rec.pension_no, rec.status)
    db.session.commit()
    flash(f"{rec.pension_no} is now {rec.status.lower()}.", "info")
    return redirect(url_for("departments.pensions"))
