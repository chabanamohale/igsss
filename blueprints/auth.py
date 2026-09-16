"""Registration, sign-in, sign-out and password management."""
from datetime import datetime, date

from flask import (Blueprint, render_template, redirect, url_for, request,
                   flash, session)
from flask_login import login_user, logout_user, login_required, current_user

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

        user = (User.query.filter_by(username=identifier).first()
                or User.query.filter_by(email=identifier.lower()).first())

        if user is None or not user.check_password(password):
            flash("That username or password is not correct.", "danger")
            record_audit("LOGIN_FAILED", "User", identifier,
                         "Sign-in attempt rejected")
            db.session.commit()
            return render_template("auth/login.html", identifier=identifier)

        if not user.active:
            flash("This account is suspended. Contact your system administrator.",
                  "warning")
            return render_template("auth/login.html", identifier=identifier)

        login_user(user, remember=remember)
        user.last_login = datetime.utcnow()
        record_audit("LOGIN", "User", user.username, "Signed in")
        db.session.commit()

        nxt = request.args.get("next")
        return redirect(nxt if nxt and nxt.startswith("/") else
                        url_for("main.dashboard_router"))

    return render_template("auth/login.html", identifier="")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Citizen self-registration. Staff accounts are created by an administrator."""
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard_router"))

    if request.method == "POST":
        form = {k: v.strip() for k, v in request.form.items()}
        errors = []

        if User.query.filter_by(username=form.get("username")).first():
            errors.append("That username is already taken.")
        if User.query.filter_by(email=form.get("email", "").lower()).first():
            errors.append("An account already uses that email address.")
        if Citizen.query.filter_by(national_id=form.get("national_id")).first():
            errors.append("A profile already exists for that national ID.")
        if len(form.get("password", "")) < 8:
            errors.append("Choose a password of at least 8 characters.")
        if form.get("password") != form.get("confirm"):
            errors.append("The two passwords do not match.")
        if not form.get("national_id", "").isdigit() or len(form["national_id"]) < 8:
            errors.append("Enter your national ID as digits only, at least 8 of them.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth/register.html", form=form,
                                   districts=DISTRICTS)

        user = User(username=form["username"], email=form["email"].lower(),
                    role="citizen")
        user.set_password(form["password"])

        dob = None
        if form.get("date_of_birth"):
            try:
                dob = datetime.strptime(form["date_of_birth"], "%Y-%m-%d").date()
            except ValueError:
                dob = None

        citizen = Citizen(
            user=user, national_id=form["national_id"],
            first_name=form["first_name"], last_name=form["last_name"],
            date_of_birth=dob, gender=form.get("gender"),
            phone=form.get("phone"), email=form["email"].lower(),
            address=form.get("address"), district=form.get("district"),
        )
        db.session.add_all([user, citizen])
        db.session.flush()

        Notification.send(
            user, "Your profile is waiting for verification",
            "Home Affairs will check your national ID against the civil register. "
            "You can apply for services as soon as it is verified.",
            link="/citizen/profile", category="info",
        )
        record_audit("REGISTER", "Citizen", citizen.national_id,
                     "Citizen self-registered")
        db.session.commit()

        login_user(user)
        flash(f"Welcome, {citizen.first_name}. Your profile has been created.",
              "success")
        return redirect(url_for("citizen.dashboard"))

    return render_template("auth/register.html", form={}, districts=DISTRICTS)


@auth_bp.route("/logout")
@login_required
def logout():
    record_audit("LOGOUT", "User", current_user.username, "Signed out")
    db.session.commit()
    logout_user()
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("main.home"))


@auth_bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current = request.form.get("current", "")
        new = request.form.get("new", "")
        confirm = request.form.get("confirm", "")

        if not current_user.check_password(current):
            flash("Your current password is not correct.", "danger")
        elif len(new) < 8:
            flash("Choose a new password of at least 8 characters.", "danger")
        elif new != confirm:
            flash("The two new passwords do not match.", "danger")
        else:
            current_user.set_password(new)
            record_audit("PASSWORD_CHANGE", "User", current_user.username,
                         "Password updated")
            db.session.commit()
            flash("Your password has been changed.", "success")
            return redirect(url_for("main.dashboard_router"))

    return render_template("auth/password.html")
