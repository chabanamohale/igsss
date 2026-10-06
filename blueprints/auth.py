
# Registration, sign-in, sign-out and password management.
import re
from datetime import datetime, date

from flask import (
    Blueprint, render_template, redirect, url_for, request,
    flash, session
)
from flask_login import (
    login_user, logout_user, login_required, current_user
)

from extensions import db
from models import User, Citizen, Notification, DISTRICTS
from utils import record_audit

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard_router"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = (
            User.query.filter_by(username=identifier).first()
            or User.query.filter_by(email=identifier.lower()).first()
        )

        if user is None or not user.check_password(password):
            flash(
                "That username or password is not correct.",
                "danger"
            )
            record_audit(
                "LOGIN_FAILED", "User", identifier,
                "Sign-in attempt rejected"
            )
            db.session.commit()
            return render_template(
                "auth/login.html",
                identifier=identifier
            )

        if not user.active:
            flash(
                "This account is suspended. Contact your system administrator.",
                "warning"
            )
            return render_template(
                "auth/login.html",
                identifier=identifier
            )

        login_user(user, remember=remember)
        user.last_login = datetime.utcnow()

        record_audit(
            "LOGIN", "User", user.username, "Signed in"
        )
        db.session.commit()

        nxt = request.args.get("next")
        return redirect(
            nxt if nxt and nxt.startswith("/")
            else url_for("main.dashboard_router")
        )

    return render_template(
        "auth/login.html",
        identifier=""
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    #Citizen self-registration. Staff accounts are created by an administrator.

    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard_router"))

    if request.method == "POST":
        form = {
            k: v.strip()
            for k, v in request.form.items()
        }
        errors = []

        # Extract and normalize form values
        username = form.get("username", "")
        email = form.get("email", "").lower()
        national_id = form.get("national_id", "")
        password = form.get("password", "")
        confirm = form.get("confirm", "")
        phone = form.get("phone", "")
        address = form.get("address", "")
        dob_string = form.get("date_of_birth", "")

        # Username validation
        if not username:
            errors.append("Username is required.")
        elif User.query.filter_by(username=username).first():
            errors.append("That username is already taken.")

        # Email validation
        if not email:
            errors.append("Email address is required.")
        elif not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", email
        ):
            errors.append("Enter a valid email address.")
        elif User.query.filter_by(email=email).first():
            errors.append(
                "An account already uses that email address."
            )

        # National ID: exactly 12 positive digits
        if not re.fullmatch(r"[0-9]{12}", national_id):
            errors.append(
                "National ID must contain exactly 12 digits."
            )
        elif int(national_id) <= 0:
            errors.append(
                "National ID must be a positive number."
            )
        elif Citizen.query.filter_by(
            national_id=national_id
        ).first():
            errors.append(
                "A profile already exists for that national ID."
            )

        # Mobile number: exactly 8 positive digits
        if not re.fullmatch(r"[0-9]{8}", phone):
            errors.append(
                "Mobile number must contain exactly 8 digits."
            )
        elif int(phone) <= 0:
            errors.append(
                "Mobile number must be a positive number."
            )

        # Physical address validation
        if (
            not address
            or len(address) < 5
            or not re.search(r"[A-Za-z]", address)
            or not re.search(r"[A-Za-z0-9]", address)
        ):
            errors.append(
                "Enter a valid physical address with at least "
                "5 characters, including letters."
            )

        # First and last name validation
        first_name = form.get("first_name", "")
        last_name = form.get("last_name", "")

        if not first_name or not re.fullmatch(
            r"[A-Za-z][A-Za-z '\-]*", first_name
        ):
            errors.append(
                "Enter a valid first name."
            )

        if not last_name or not re.fullmatch(
            r"[A-Za-z][A-Za-z '\-]*", last_name
        ):
            errors.append(
                "Enter a valid last name."
            )

        # Password validation
        if len(password) < 8:
            errors.append(
                "Choose a password of at least 8 characters."
            )

        if password != confirm:
            errors.append(
                "The two passwords do not match."
            )

        # Date of birth and age validation
        dob = None

        if not dob_string:
            errors.append(
                "Date of birth is required."
            )
        else:
            try:
                dob = datetime.strptime(
                    dob_string, "%Y-%m-%d"
                ).date()

                if dob > date.today():
                    errors.append(
                        "Date of birth cannot be in the future."
                    )
                else:
                    today = date.today()

                    age = (
                        today.year - dob.year
                        - (
                            (today.month, today.day)
                            < (dob.month, dob.day)
                        )
                    )

                    if age <= 0:
                        errors.append(
                            "Age must be a positive whole number "
                            "greater than zero."
                        )

            except ValueError:
                dob = None
                errors.append(
                    "Enter a valid date of birth."
                )

        # District validation
        district = form.get("district", "")

        if not district:
            errors.append(
                "Please select your district."
            )
        elif district not in DISTRICTS:
            errors.append(
                "Please select a valid district."
            )

        # Return the form with errors, preserving entered data
        if errors:
            for error in errors:
                flash(error, "danger")

            return render_template(
                "auth/register.html",
                form=form,
                districts=DISTRICTS,
                today=date.today().isoformat()
            )

        # Create citizen user account
        user = User(
            username=username,
            email=email,
            role="citizen"
        )
        user.set_password(password)

        # Create citizen profile
        citizen = Citizen(
            user=user,
            national_id=national_id,
            first_name=first_name,
            last_name=last_name,
            date_of_birth=dob,
            gender=form.get("gender"),
            phone=phone,
            email=email,
            address=address,
            district=district,
        )

        db.session.add_all([user, citizen])

        try:
            db.session.flush()

            # Notify the citizen that verification is pending
            Notification.send(
                user,
                "Your profile is waiting for verification",
                (
                    "Home Affairs will check your national ID "
                    "against the civil register. You can apply "
                    "for services as soon as it is verified."
                ),
                link="/citizen/profile",
                category="info",
            )

            # Record registration in the audit log
            record_audit(
                "REGISTER",
                "Citizen",
                citizen.national_id,
                "Citizen self-registered"
            )

            db.session.commit()

        except Exception:
            db.session.rollback()
            flash(
                "Registration could not be completed. "
                "Please try again.",
                "danger"
            )
            return render_template(
                "auth/register.html",
                form=form,
                districts=DISTRICTS,
                today=date.today().isoformat()
            )

        # Sign in the newly registered citizen
        login_user(user)

        flash(
            f"Welcome, {citizen.first_name}. "
            "Your profile has been created.",
            "success"
        )

        return redirect(
            url_for("citizen.dashboard")
        )

    return render_template(
        "auth/register.html",
        form={},
        districts=DISTRICTS,
        today=date.today().isoformat()
    )


@auth_bp.route("/logout")
@login_required
def logout():
    record_audit(
        "LOGOUT",
        "User",
        current_user.username,
        "Signed out"
    )
    db.session.commit()

    logout_user()
    session.clear()

    flash(
        "You have been signed out.",
        "info"
    )

    return redirect(
        url_for("main.home")
    )


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current", "")
        new = request.form.get("new", "")
        confirm = request.form.get("confirm", "")

        if not current_user.check_password(current):
            flash(
                "Your current password is not correct.",
                "danger"
            )

        elif len(new) < 8:
            flash(
                "Choose a new password of at least 8 characters.",
                "danger"
            )

        elif new != confirm:
            flash(
                "The two new passwords do not match.",
                "danger"
            )

        else:
            current_user.set_password(new)

            record_audit(
                "PASSWORD_CHANGE",
                "User",
                current_user.username,
                "Password updated"
            )
            db.session.commit()

            flash(
                "Your password has been changed.",
                "success"
            )

            return redirect(
                url_for("main.dashboard_router")
            )

    return render_template(
        "auth/password.html"
    )