"""
Citizen portal: the single citizen profile, service applications, documents,
payments, notifications and the citizen's own departmental records.
"""
from datetime import datetime, date

from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, abort, send_from_directory, current_app, jsonify)
from flask_login import login_required, current_user

from extensions import db
from models import (Service, Department, Application, Document, Payment,
                    Notification, Citizen, Favourite, Review, DISTRICTS,
                    reference_code)
from utils import citizen_required, record_audit, save_upload, allowed_file
from utils.helpers import advance_status, new_payment_for

citizen_bp = Blueprint("citizen", __name__)


def _me():
    """The Citizen row for the signed-in user."""
    if not current_user.citizen:
        abort(403)
    return current_user.citizen


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

@citizen_bp.route("/")
@citizen_required
def dashboard():
    me = _me()
    apps = me.applications
    counts = {
        "total": len(apps),
        "open": sum(1 for a in apps if not a.is_closed),
        "approved": sum(1 for a in apps if a.status in ("Approved", "Collected")),
        "action": sum(1 for a in apps if a.status in
                      ("Awaiting Payment", "Awaiting Documents")),
    }
    outstanding = sum(a.balance for a in apps if a.balance > 0 and not a.is_closed)
    recent = apps[:5]
    unread = [n for n in current_user.notifications if not n.read][:4]

    # Things the citizen should renew soon
    reminders = []
    for p in me.passports:
        if p.expiry_date and 0 < (p.expiry_date - date.today()).days < 180:
            reminders.append(("Passport", p.passport_no, p.expiry_date))
    for l in me.licences:
        if l.expiry_date and 0 < (l.expiry_date - date.today()).days < 180:
            reminders.append(("Driver licence", l.licence_no, l.expiry_date))
    for v in me.vehicles:
        if v.licence_expiry and 0 < (v.licence_expiry - date.today()).days < 90:
            reminders.append(("Vehicle licence", v.registration_no, v.licence_expiry))

    return render_template("citizen/dashboard.html", me=me, counts=counts,
                           recent=recent, unread=unread, reminders=reminders,
                           outstanding=outstanding)


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------

@citizen_bp.route("/profile", methods=["GET", "POST"])
@citizen_required
def profile():
    me = _me()
    if request.method == "POST":
        me.phone = request.form.get("phone", "").strip()
        me.email = request.form.get("email", "").strip().lower()
        me.address = request.form.get("address", "").strip()
        me.district = request.form.get("district", "").strip()
        record_audit("PROFILE_UPDATE", "Citizen", me.national_id,
                     "Citizen updated contact details")
        db.session.commit()
        flash("Your contact details have been saved.", "success")
        return redirect(url_for("citizen.profile"))
    return render_template("citizen/profile.html", me=me, districts=DISTRICTS)


@citizen_bp.route("/records")
@citizen_required
def records():
    """Everything the connected departments hold on this citizen, in one place."""
    me = _me()
    record_audit("VIEW_OWN_RECORDS", "Citizen", me.national_id,
                 "Citizen viewed their consolidated record")
    db.session.commit()
    return render_template("citizen/records.html", me=me)


# --------------------------------------------------------------------------
# Applying for a service
# --------------------------------------------------------------------------

@citizen_bp.route("/apply")
@citizen_required
def apply_catalogue():
    dept_code = request.args.get("department", "")
    query = Service.query.filter_by(active=True)
    if dept_code:
        dept = Department.query.filter_by(code=dept_code).first()
        if dept:
            query = query.filter_by(department_id=dept.id)
    services = query.order_by(Service.department_id, Service.name).all()
    return render_template("citizen/apply_catalogue.html", services=services,
                           selected=dept_code)


@citizen_bp.route("/apply/<code>", methods=["GET", "POST"])
@citizen_required
def apply(code):
    me = _me()
    service = Service.query.filter_by(code=code, active=True).first_or_404()

    if not me.verified:
        flash("Home Affairs has not verified your profile yet. You can browse "
              "services, but you cannot submit an application until it is verified.",
              "warning")

    if request.method == "POST":
        if not me.verified:
            flash("Your profile must be verified before you can apply.", "danger")
            return redirect(url_for("citizen.apply", code=code))

        application = Application.new_for(
            me, service,
            purpose=request.form.get("purpose", "").strip(),
            priority=request.form.get("priority", "Normal"),
        )
        db.session.add(application)
        db.session.flush()

        # Attach any files submitted with the form
        for file in request.files.getlist("documents"):
            if file and file.filename and allowed_file(file.filename):
                stored, original, kb = save_upload(file)
                db.session.add(Document(
                    citizen=me, application=application,
                    doc_type=request.form.get("doc_type", "Supporting document"),
                    original_name=original, stored_name=stored, size_kb=kb,
                ))

        # Raise the fee as a pending payment
        if service.fee and service.fee > 0:
            db.session.add(new_payment_for(application))
            advance_status(application, "Awaiting Payment",
                           f"Pay M{service.fee:,.2f} to start processing.",
                           notify=False)
        else:
            db.session.add(__import__("models").StatusHistory(
                application=application, from_status=None, to_status="Submitted",
                changed_by=me.full_name, note="Application submitted."))

        Notification.send(
            current_user, "Application received",
            f"{service.name} — your reference is {application.reference}. "
            f"Keep it to track progress.",
            link=f"/citizen/applications/{application.id}", category="success")

        record_audit("APPLY", "Application", application.reference,
                     f"Applied for {service.name}")
        db.session.commit()

        flash(f"Application submitted. Your reference is {application.reference}.",
              "success")
        return redirect(url_for("citizen.application_detail", app_id=application.id))

    # Documents already on file that can be reused — the core idea of the system
    reusable = [d for d in me.documents if d.verified]
    return render_template("citizen/apply.html", service=service, me=me,
                           reusable=reusable)


# --------------------------------------------------------------------------
# Tracking applications
# --------------------------------------------------------------------------

@citizen_bp.route("/applications")
@citizen_required
def applications():
    me = _me()
    status = request.args.get("status", "")
    items = me.applications
    if status:
        items = [a for a in items if a.status == status]
    return render_template("citizen/applications.html", applications=items,
                           status=status)


@citizen_bp.route("/applications/<int:app_id>")
@citizen_required
def application_detail(app_id):
    me = _me()
    application = db.session.get(Application, app_id)
    if not application or application.citizen_id != me.id:
        abort(404)
    return render_template("citizen/application_detail.html",
                           application=application)


@citizen_bp.route("/applications/<int:app_id>/cancel", methods=["POST"])
@citizen_required
def cancel_application(app_id):
    me = _me()
    application = db.session.get(Application, app_id)
    if not application or application.citizen_id != me.id:
        abort(404)
    if application.is_closed:
        flash("That application is already closed.", "warning")
    else:
        advance_status(application, "Rejected",
                       "Withdrawn by the applicant.", notify=False)
        db.session.commit()
        flash("Application withdrawn.", "info")
    return redirect(url_for("citizen.applications"))


@citizen_bp.route("/applications/<int:app_id>/documents", methods=["POST"])
@citizen_required
def add_document(app_id):
    me = _me()
    application = db.session.get(Application, app_id)
    if not application or application.citizen_id != me.id:
        abort(404)

    file = request.files.get("document")
    if not file or not file.filename:
        flash("Choose a file to upload.", "danger")
    elif not allowed_file(file.filename):
        flash("Upload a PDF, JPG, PNG or DOCX file.", "danger")
    else:
        stored, original, kb = save_upload(file)
        db.session.add(Document(
            citizen=me, application=application,
            doc_type=request.form.get("doc_type", "Supporting document"),
            original_name=original, stored_name=stored, size_kb=kb))
        if application.status == "Awaiting Documents":
            advance_status(application, "Under Review",
                           "Requested document supplied.", notify=False)
        record_audit("UPLOAD", "Document", original,
                     f"Attached to {application.reference}")
        db.session.commit()
        flash("Document uploaded.", "success")
    return redirect(url_for("citizen.application_detail", app_id=app_id))


# --------------------------------------------------------------------------
# Documents wallet
# --------------------------------------------------------------------------

@citizen_bp.route("/documents", methods=["GET", "POST"])
@citizen_required
def documents():
    me = _me()
    if request.method == "POST":
        file = request.files.get("document")
        if not file or not file.filename:
            flash("Choose a file to upload.", "danger")
        elif not allowed_file(file.filename):
            flash("Upload a PDF, JPG, PNG or DOCX file.", "danger")
        else:
            stored, original, kb = save_upload(file)
            db.session.add(Document(
                citizen=me, doc_type=request.form.get("doc_type", "Other"),
                original_name=original, stored_name=stored, size_kb=kb))
            record_audit("UPLOAD", "Document", original, "Added to document wallet")
            db.session.commit()
            flash("Document added to your wallet. Any department you apply to "
                  "can reuse it.", "success")
        return redirect(url_for("citizen.documents"))
    return render_template("citizen/documents.html", me=me)


@citizen_bp.route("/documents/<int:doc_id>/delete", methods=["POST"])
@citizen_required
def delete_document(doc_id):
    me = _me()
    doc = db.session.get(Document, doc_id)
    if not doc or doc.citizen_id != me.id:
        abort(404)
    if doc.verified:
        flash("Verified documents cannot be removed.", "warning")
    else:
        db.session.delete(doc)
        db.session.commit()
        flash("Document removed.", "info")
    return redirect(url_for("citizen.documents"))


@citizen_bp.route("/documents/<int:doc_id>/open")
@login_required
def open_document(doc_id):
    doc = db.session.get(Document, doc_id) or abort(404)
    owner = current_user.citizen and doc.citizen_id == current_user.citizen.id
    if not (owner or current_user.is_employee or current_user.is_admin):
        abort(403)
    record_audit("VIEW_DOCUMENT", "Document", doc.original_name,
                 f"Opened document of {doc.citizen.full_name}")
    db.session.commit()
    return send_from_directory(current_app.config["UPLOAD_FOLDER"],
                               doc.stored_name, as_attachment=False)


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------

@citizen_bp.route("/payments")
@citizen_required
def payments():
    me = _me()
    paid = sum(p.amount for p in me.payments if p.status == "Paid")
    pending = sum(p.amount for p in me.payments if p.status == "Pending")
    return render_template("citizen/payments.html", me=me, paid=paid,
                           pending=pending)


@citizen_bp.route("/payments/<int:pay_id>/pay", methods=["POST"])
@citizen_required
def pay(pay_id):
    me = _me()
    payment = db.session.get(Payment, pay_id)
    if not payment or payment.citizen_id != me.id:
        abort(404)
    if payment.status == "Paid":
        flash("That fee is already paid.", "info")
        return redirect(url_for("citizen.payments"))

    payment.method = request.form.get("method", "M-Pesa")
    payment.status = "Paid"
    payment.paid_at = datetime.utcnow()

    if payment.application and payment.application.status == "Awaiting Payment":
        advance_status(payment.application, "Under Review",
                       "Fee received. The department has been notified.")

    record_audit("PAYMENT", "Payment", payment.reference,
                 f"Paid M{payment.amount:,.2f} via {payment.method}")
    db.session.commit()
    flash(f"Payment of M{payment.amount:,.2f} received. "
          f"Receipt {payment.reference}.", "success")
    return redirect(url_for("citizen.payments"))


@citizen_bp.route("/payments/<int:pay_id>/receipt")
@citizen_required
def receipt(pay_id):
    me = _me()
    payment = db.session.get(Payment, pay_id)
    if not payment or payment.citizen_id != me.id:
        abort(404)
    return render_template("citizen/receipt.html", payment=payment, me=me)


# --------------------------------------------------------------------------
# Notifications
# --------------------------------------------------------------------------

@citizen_bp.route("/notifications")
@login_required
def notifications():
    return render_template("citizen/notifications.html",
                           items=current_user.notifications)


@citizen_bp.route("/notifications/read", methods=["POST"])
@login_required
def mark_read():
    for n in current_user.notifications:
        n.read = True
    db.session.commit()
    flash("All notifications marked as read.", "info")
    return redirect(url_for("citizen.notifications"))


@citizen_bp.route("/notifications/count")
@login_required
def notification_count():
    return jsonify({"unread": current_user.unread_count})


# --------------------------------------------------------------------------
# Favourites and reviews
# --------------------------------------------------------------------------

@citizen_bp.route("/favourites")
@citizen_required
def favourites():
    me = _me()
    favs = (Favourite.query.filter_by(citizen_id=me.id)
           .order_by(Favourite.created_at.desc()).all())
    return render_template("citizen/favourites.html", favourites=favs)


@citizen_bp.route("/reviews/new/<int:application_id>", methods=["GET", "POST"])
@citizen_required
def review_form(application_id):
    me = _me()
    app_ = Application.query.get_or_404(application_id)
    if app_.citizen_id != me.id or not app_.is_closed:
        abort(404)
    existing = Review.query.filter_by(application_id=app_.id).first()

    if request.method == "POST":
        try:
            rating = max(1, min(5, int(request.form.get("rating", 0))))
        except ValueError:
            rating = 0
        if not rating:
            flash("Choose a star rating before submitting.", "danger")
            return redirect(url_for("citizen.review_form", application_id=app_.id))
        comment = request.form.get("comment", "").strip()
        if existing:
            existing.rating, existing.comment = rating, comment
        else:
            db.session.add(Review(citizen=me, service=app_.service, application=app_,
                                  rating=rating, comment=comment))
        db.session.commit()
        flash("Thank you — your review was saved.", "success")
        return redirect(url_for("citizen.application_detail", app_id=app_.id))

    return render_template("citizen/review_form.html", application=app_, existing=existing)


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

@citizen_bp.route("/settings", methods=["GET", "POST"])
@citizen_required
def settings():
    if request.method == "POST":
        current_user.notify_email = request.form.get("notify_email") == "1"
        current_user.notify_sms = request.form.get("notify_sms") == "1"
        db.session.commit()
        flash("Your settings were saved.", "success")
        return redirect(url_for("citizen.settings"))
    return render_template("citizen/settings.html")
