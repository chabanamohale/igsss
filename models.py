"""
Database models for the Integrated Government Services System.

Mirrors the ERD and class diagram in the project documentation:
User -> (Citizen | Employee), Department, Service, Application,
Document, Payment, Notification, and the six departmental record tables.
"""
from datetime import datetime, date, timedelta
import secrets

from flask_login import UserMixin

from extensions import db, bcrypt, login_manager


# --------------------------------------------------------------------------
# Reference data
# --------------------------------------------------------------------------

DEPARTMENT_COLOURS = {
    "HA": "#00453D",   # Home Affairs      - deep green
    "POL": "#1F3D6B",  # Police            - navy
    "TRF": "#8A5A17",  # Traffic           - bronze
    "FIN": "#0F5F63",  # Finance           - teal
    "PEN": "#5B3A6E",  # Pensions          - plum
    "PAS": "#7A2E33",  # Passport Services - oxblood
}

STATUS_FLOW = ["Submitted", "Under Review", "Awaiting Payment",
               "Awaiting Documents", "Approved", "Rejected", "Collected"]

DISTRICTS = [
    "Maseru", "Berea", "Leribe", "Butha-Buthe", "Mokhotlong",
    "Thaba-Tseka", "Qacha's Nek", "Quthing", "Mohale's Hoek", "Mafeteng",
]


def reference_code(prefix):
    """Human-quotable reference, e.g. APP-7F3K2Q."""
    return f"{prefix}-{secrets.token_hex(3).upper()}"


# --------------------------------------------------------------------------
# Accounts
# --------------------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="citizen")  # citizen|employee|admin
    active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notify_email = db.Column(db.Boolean, default=True)
    notify_sms = db.Column(db.Boolean, default=False)

    citizen = db.relationship("Citizen", back_populates="user", uselist=False,
                              cascade="all, delete-orphan")
    employee = db.relationship("Employee", back_populates="user", uselist=False,
                               cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user",
                                    cascade="all, delete-orphan",
                                    order_by="Notification.created_at.desc()")
    audit_logs = db.relationship("AuditLog", back_populates="user")

    # -- password handling --------------------------------------------------
    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    # -- convenience --------------------------------------------------------
    @property
    def is_citizen(self):
        return self.role == "citizen"

    @property
    def is_employee(self):
        return self.role == "employee"

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def display_name(self):
        if self.citizen:
            return f"{self.citizen.first_name} {self.citizen.last_name}"
        if self.employee:
            return self.employee.full_name
        return self.username

    @property
    def initials(self):
        parts = self.display_name.split()
        return "".join(p[0] for p in parts[:2]).upper() or "?"

    @property
    def unread_count(self):
        return sum(1 for n in self.notifications if not n.read)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class Citizen(db.Model):
    __tablename__ = "citizens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    national_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(60), nullable=False)
    last_name = db.Column(db.String(60), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    district = db.Column(db.String(40))
    verified = db.Column(db.Boolean, default=False)
    verified_on = db.Column(db.DateTime)
    verified_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="citizen")
    applications = db.relationship("Application", back_populates="citizen",
                                   cascade="all, delete-orphan",
                                   order_by="Application.submitted_at.desc()")
    documents = db.relationship("Document", back_populates="citizen",
                                cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="citizen",
                               cascade="all, delete-orphan")
    vehicles = db.relationship("Vehicle", back_populates="citizen",
                               cascade="all, delete-orphan")
    licences = db.relationship("DriverLicence", back_populates="citizen",
                               cascade="all, delete-orphan")
    passports = db.relationship("Passport", back_populates="citizen",
                                cascade="all, delete-orphan")
    police_records = db.relationship("PoliceRecord", back_populates="citizen",
                                     cascade="all, delete-orphan")
    pension_records = db.relationship("PensionRecord", back_populates="citizen",
                                      cascade="all, delete-orphan")
    finance_record = db.relationship("FinanceRecord", back_populates="citizen",
                                     uselist=False, cascade="all, delete-orphan")
    civil_records = db.relationship("CivilRecord", back_populates="citizen",
                                    cascade="all, delete-orphan")
    favourites = db.relationship("Favourite", back_populates="citizen",
                                 cascade="all, delete-orphan")

    @property
    def favourite_service_ids(self):
        return {f.service_id for f in self.favourites}

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def pension_eligible(self):
        """Old Age Pension: citizen aged 70 or over."""
        return self.age is not None and self.age >= 70

    def __repr__(self):
        return f"<Citizen {self.national_id} {self.full_name}>"


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(6), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    ministry = db.Column(db.String(120))
    description = db.Column(db.Text)
    contact_phone = db.Column(db.String(30))
    contact_email = db.Column(db.String(120))
    head_office = db.Column(db.String(120))

    employees = db.relationship("Employee", back_populates="department")
    services = db.relationship("Service", back_populates="department")
    applications = db.relationship("Application", back_populates="department")

    @property
    def colour(self):
        return DEPARTMENT_COLOURS.get(self.code, "#4A5A54")

    def __repr__(self):
        return f"<Department {self.code}>"


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    employee_no = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(80))
    office = db.Column(db.String(80))
    phone = db.Column(db.String(20))
    can_approve = db.Column(db.Boolean, default=False)
    is_manager = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="employee")
    department = db.relationship("Department", back_populates="employees")
    handled = db.relationship("Application", back_populates="officer",
                              foreign_keys="Application.officer_id")

    def __repr__(self):
        return f"<Employee {self.employee_no} {self.full_name}>"


# --------------------------------------------------------------------------
# Services and applications
# --------------------------------------------------------------------------

class Service(db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    code = db.Column(db.String(12), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    fee = db.Column(db.Float, default=0.0)
    processing_days = db.Column(db.Integer, default=14)
    required_documents = db.Column(db.Text)   # newline separated
    active = db.Column(db.Boolean, default=True)

    department = db.relationship("Department", back_populates="services")
    applications = db.relationship("Application", back_populates="service")
    reviews = db.relationship("Review", back_populates="service",
                              cascade="all, delete-orphan")

    @property
    def document_list(self):
        if not self.required_documents:
            return []
        return [d.strip() for d in self.required_documents.split("\n") if d.strip()]

    @property
    def average_rating(self):
        if not self.reviews:
            return None
        return round(sum(r.rating for r in self.reviews) / len(self.reviews), 1)

    @property
    def review_count(self):
        return len(self.reviews)

    def __repr__(self):
        return f"<Service {self.code} {self.name}>"


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False, index=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"))
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    officer_id = db.Column(db.Integer, db.ForeignKey("employees.id"))

    status = db.Column(db.String(30), default="Submitted", index=True)
    priority = db.Column(db.String(10), default="Normal")  # Normal | Urgent
    purpose = db.Column(db.Text)
    officer_notes = db.Column(db.Text)
    decision_reason = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    due_date = db.Column(db.Date)

    citizen = db.relationship("Citizen", back_populates="applications")
    service = db.relationship("Service", back_populates="applications")
    department = db.relationship("Department", back_populates="applications")
    officer = db.relationship("Employee", back_populates="handled",
                              foreign_keys=[officer_id])
    documents = db.relationship("Document", back_populates="application",
                                cascade="all, delete-orphan")
    payments = db.relationship("Payment", back_populates="application",
                               cascade="all, delete-orphan")
    history = db.relationship("StatusHistory", back_populates="application",
                              cascade="all, delete-orphan",
                              order_by="StatusHistory.changed_at")

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def new_for(citizen, service, purpose=None, priority="Normal"):
        app = Application(
            reference=reference_code("APP"),
            citizen=citizen,
            service=service,
            department=service.department,
            purpose=purpose,
            priority=priority,
            due_date=date.today() + timedelta(days=service.processing_days or 14),
        )
        return app

    @property
    def is_closed(self):
        return self.status in ("Approved", "Rejected", "Collected")

    @property
    def is_overdue(self):
        return (not self.is_closed and self.due_date and self.due_date < date.today())

    @property
    def amount_paid(self):
        return sum(p.amount for p in self.payments if p.status == "Paid")

    @property
    def balance(self):
        return round((self.service.fee if self.service else 0) - self.amount_paid, 2)

    @property
    def progress(self):
        """Rough completion percentage for the citizen-facing tracker."""
        table = {"Submitted": 20, "Under Review": 45, "Awaiting Payment": 55,
                 "Awaiting Documents": 55, "Approved": 85, "Collected": 100,
                 "Rejected": 100}
        return table.get(self.status, 10)

    def __repr__(self):
        return f"<Application {self.reference} {self.status}>"


class StatusHistory(db.Model):
    __tablename__ = "status_history"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"))
    from_status = db.Column(db.String(30))
    to_status = db.Column(db.String(30))
    changed_by = db.Column(db.String(120))
    note = db.Column(db.Text)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    application = db.relationship("Application", back_populates="history")


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"))
    doc_type = db.Column(db.String(80))
    original_name = db.Column(db.String(200))
    stored_name = db.Column(db.String(200))
    size_kb = db.Column(db.Integer)
    verified = db.Column(db.Boolean, default=False)
    verified_by = db.Column(db.String(120))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    citizen = db.relationship("Citizen", back_populates="documents")
    application = db.relationship("Application", back_populates="documents")


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True, nullable=False)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"))
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(30))  # M-Pesa | EcoCash | Bank Transfer | Cash
    status = db.Column(db.String(20), default="Pending")  # Pending|Paid|Reversed
    description = db.Column(db.String(200))
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    citizen = db.relationship("Citizen", back_populates="payments")
    application = db.relationship("Application", back_populates="payments")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    title = db.Column(db.String(140))
    message = db.Column(db.Text)
    link = db.Column(db.String(200))
    category = db.Column(db.String(20), default="info")
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="notifications")

    @staticmethod
    def send(user, title, message, link=None, category="info"):
        if user is None:
            return None
        n = Notification(user=user, title=title, message=message,
                         link=link, category=category)
        db.session.add(n)
        return n


# --------------------------------------------------------------------------
# Departmental record tables
# --------------------------------------------------------------------------

class CivilRecord(db.Model):
    """Home Affairs: birth, death and marriage registration."""
    __tablename__ = "civil_records"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    record_type = db.Column(db.String(20))  # Birth|Marriage|Death
    reference = db.Column(db.String(30), unique=True)
    event_date = db.Column(db.Date)
    place = db.Column(db.String(120))
    details = db.Column(db.Text)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow)

    citizen = db.relationship("Citizen", back_populates="civil_records")


class Vehicle(db.Model):
    """Traffic & Transport: vehicle registration."""
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    registration_no = db.Column(db.String(20), unique=True, index=True)
    make = db.Column(db.String(40))
    model = db.Column(db.String(40))
    year = db.Column(db.Integer)
    colour = db.Column(db.String(30))
    engine_no = db.Column(db.String(40))
    chassis_no = db.Column(db.String(40))
    licence_expiry = db.Column(db.Date)
    roadworthy_expiry = db.Column(db.Date)
    status = db.Column(db.String(20), default="Active")

    citizen = db.relationship("Citizen", back_populates="vehicles")

    @property
    def licence_valid(self):
        return self.licence_expiry and self.licence_expiry >= date.today()


class DriverLicence(db.Model):
    """Traffic & Transport: driver licensing."""
    __tablename__ = "driver_licences"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    licence_no = db.Column(db.String(20), unique=True, index=True)
    licence_class = db.Column(db.String(10))  # A, B, C, EC ...
    issue_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    restrictions = db.Column(db.String(120))
    status = db.Column(db.String(20), default="Valid")

    citizen = db.relationship("Citizen", back_populates="licences")

    @property
    def is_valid(self):
        return self.status == "Valid" and self.expiry_date and self.expiry_date >= date.today()


class Passport(db.Model):
    """Passport Services (Home Affairs)."""
    __tablename__ = "passports"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    passport_no = db.Column(db.String(20), unique=True, index=True)
    passport_type = db.Column(db.String(20), default="Ordinary")
    issue_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    issuing_office = db.Column(db.String(60))
    status = db.Column(db.String(20), default="Active")

    citizen = db.relationship("Citizen", back_populates="passports")

    @property
    def is_valid(self):
        return self.status == "Active" and self.expiry_date and self.expiry_date >= date.today()


class PoliceRecord(db.Model):
    """Lesotho Mounted Police Service: clearance certificates and cases."""
    __tablename__ = "police_records"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    case_number = db.Column(db.String(30), unique=True)
    record_type = db.Column(db.String(30), default="Clearance")
    clearance_status = db.Column(db.String(30), default="Pending")  # Clear|Pending|Flagged
    fingerprints_taken = db.Column(db.Boolean, default=False)
    remarks = db.Column(db.Text)
    issued_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date)
    station = db.Column(db.String(60))

    citizen = db.relationship("Citizen", back_populates="police_records")


class PensionRecord(db.Model):
    """Old Age Pension and related social grants."""
    __tablename__ = "pension_records"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    pension_no = db.Column(db.String(20), unique=True)
    grant_type = db.Column(db.String(40), default="Old Age Pension")
    monthly_amount = db.Column(db.Float, default=0.0)
    pay_point = db.Column(db.String(80))
    next_payment = db.Column(db.Date)
    status = db.Column(db.String(20), default="Active")
    registered_on = db.Column(db.Date)

    citizen = db.relationship("Citizen", back_populates="pension_records")


class FinanceRecord(db.Model):
    """Ministry of Finance: taxpayer account and running balance."""
    __tablename__ = "finance_records"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"), unique=True)
    tax_number = db.Column(db.String(20), unique=True)
    tax_status = db.Column(db.String(30), default="Compliant")
    outstanding_balance = db.Column(db.Float, default=0.0)
    last_filed = db.Column(db.Date)

    citizen = db.relationship("Citizen", back_populates="finance_record")


# --------------------------------------------------------------------------
# Security and oversight
# --------------------------------------------------------------------------

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    actor = db.Column(db.String(120))
    department = db.Column(db.String(60))
    action = db.Column(db.String(60), index=True)
    entity = db.Column(db.String(60))
    entity_ref = db.Column(db.String(60))
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship("User", back_populates="audit_logs")


class AccessRequest(db.Model):
    """Cross-department data sharing request, reviewed by the owning department."""
    __tablename__ = "access_requests"

    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(20), unique=True)
    requesting_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    owning_department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"))
    requested_by = db.Column(db.String(120))
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default="Pending")  # Pending|Granted|Denied
    decided_by = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    decided_at = db.Column(db.DateTime)

    requesting_department = db.relationship("Department",
                                            foreign_keys=[requesting_department_id])
    owning_department = db.relationship("Department",
                                        foreign_keys=[owning_department_id])
    citizen = db.relationship("Citizen")


# --------------------------------------------------------------------------
# Engagement: favourites and reviews
# --------------------------------------------------------------------------

class Favourite(db.Model):
    """A citizen starring a service for quick access from the catalogue."""
    __tablename__ = "favourites"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    citizen = db.relationship("Citizen", back_populates="favourites")
    service = db.relationship("Service")

    __table_args__ = (db.UniqueConstraint("citizen_id", "service_id",
                                          name="uq_favourite_citizen_service"),)


class Review(db.Model):
    """A citizen's rating and comment on a service, left after it is decided."""
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    citizen_id = db.Column(db.Integer, db.ForeignKey("citizens.id"), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey("services.id"), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"))
    rating = db.Column(db.Integer, nullable=False)  # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    citizen = db.relationship("Citizen")
    service = db.relationship("Service", back_populates="reviews")
    application = db.relationship("Application")
