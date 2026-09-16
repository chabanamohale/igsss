"""
Populate the system with realistic demonstration data.

    python seed.py

Wipes and rebuilds the database, then prints the sign-in details.
"""
import random
from datetime import datetime, date, timedelta

from extensions import db
from models import (User, Citizen, Employee, Department, Service, Application,
                    StatusHistory, Document, Payment, Notification, CivilRecord,
                    Vehicle, DriverLicence, Passport, PoliceRecord, PensionRecord,
                    FinanceRecord, AuditLog, AccessRequest, Favourite, Review,
                    DISTRICTS, reference_code)

random.seed(2026)


DEPARTMENTS = [
    ("HA", "Home Affairs", "Ministry of Home Affairs",
     "Registers and affirms the identity and status of citizens, manages civil "
     "registration, migration and national identity documents.",
     "+266 2232 3771", "info@homeaffairs.gov.ls", "Maseru Head Office"),
    ("POL", "Police", "Lesotho Mounted Police Service",
     "Maintains law and order, investigates crime, and issues police clearance "
     "certificates for employment, travel and emigration.",
     "+266 2231 7262", "records@lmps.gov.ls", "Police Headquarters, Maseru"),
    ("TRF", "Traffic and Transport", "Ministry of Public Works and Transport",
     "Licenses drivers and vehicles, conducts roadworthiness testing, and issues "
     "transport permits.",
     "+266 2232 4567", "licensing@transport.gov.ls", "Maseru Testing Centre"),
    ("FIN", "Finance", "Ministry of Finance and Development Planning",
     "Collects government fees and taxes, and reconciles revenue against the "
     "services that generated it.",
     "+266 2231 1101", "revenue@finance.gov.ls", "Finance House, Maseru"),
    ("PEN", "Pensions", "Ministry of Social Development",
     "Administers the Old Age Pension and related social grants, including "
     "eligibility checks and the monthly payroll.",
     "+266 2232 6004", "grants@socdev.gov.ls", "Social Development Offices, Maseru"),
    ("PAS", "Passport Services", "Ministry of Home Affairs",
     "Issues ordinary, official and emergency travel documents through district "
     "passport offices.",
     "+266 2232 3771", "passports@homeaffairs.gov.ls", "Maseru Passport Office"),
]

SERVICES = [
    # code, name, dept, fee, days, description, documents
    ("HA-NID", "Apply for a national ID", "HA", 40, 10,
     "First registration or replacement of a national identity card, including "
     "biometric capture.",
     "Birth certificate\nProof of citizenship\nTwo passport photographs"),
    ("HA-BIR", "Register a birth", "HA", 0, 5,
     "Register a birth and obtain a birth certificate.",
     "Hospital notification of birth\nParents' national IDs\nMarriage certificate if applicable"),
    ("HA-MAR", "Register a marriage", "HA", 60, 7,
     "Record a marriage in the civil register and obtain a certificate.",
     "Both parties' national IDs\nWitness details\nProof of marital status"),
    ("PAS-NEW", "Apply for a passport", "PAS", 350, 21,
     "Ordinary ten-year passport for Lesotho citizens.",
     "Valid national ID\nTwo passport photographs\nProof of payment"),
    ("PAS-REN", "Renew a passport", "PAS", 300, 14,
     "Replace a passport that has expired or is close to expiry.",
     "Expiring passport\nValid national ID\nTwo passport photographs"),
    ("PAS-EMG", "Emergency travel document", "PAS", 180, 3,
     "Short-validity travel document for urgent or compassionate travel.",
     "Valid national ID\nProof of urgent travel\nOne passport photograph"),
    ("POL-PCC", "Police clearance certificate", "POL", 120, 21,
     "Certificate of no criminal record, used for employment, travel and emigration.",
     "Certified copy of ID\nFull set of fingerprints\nCover letter stating the purpose\nTwo passport photographs"),
    ("POL-FRM", "Firearm licence check", "POL", 200, 30,
     "Background check required before a firearm licence is considered.",
     "Valid national ID\nMotivation letter\nProof of secure storage"),
    ("TRF-DLN", "Apply for a driver licence", "TRF", 250, 14,
     "New driver licence following a passed theory and practical test.",
     "Valid national ID\nMedical certificate\nProof of passing both tests\nTwo passport photographs"),
    ("TRF-DLR", "Renew a driver licence", "TRF", 180, 7,
     "Renew a licence that has expired or is close to expiry.",
     "Expiring licence\nValid national ID\nMedical certificate for classes C and EC"),
    ("TRF-VRG", "Register a vehicle", "TRF", 400, 10,
     "First registration of a vehicle in Lesotho.",
     "Proof of ownership\nRoadworthiness certificate\nCustoms clearance if imported\nValid national ID"),
    ("TRF-VLR", "Renew a vehicle licence", "TRF", 220, 3,
     "Annual vehicle licence renewal.",
     "Current licence disc\nRoadworthiness certificate"),
    ("TRF-RWC", "Roadworthiness test", "TRF", 150, 2,
     "Fitness inspection and certification of a vehicle.",
     "Vehicle registration document\nValid national ID"),
    ("FIN-TAX", "Register as a taxpayer", "FIN", 0, 7,
     "Open a taxpayer account and receive a tax number.",
     "Valid national ID\nProof of income or business registration"),
    ("FIN-CLR", "Tax clearance certificate", "FIN", 100, 10,
     "Confirmation that your tax affairs are in order, often required for tenders.",
     "Valid national ID\nTax number\nLatest filed return"),
    ("PEN-OAP", "Apply for the Old Age Pension", "PEN", 0, 30,
     "Non-contributory monthly pension for citizens aged 70 and over.",
     "Valid national ID\nProof of residence\nBank or pay-point details"),
    ("PEN-DIS", "Apply for a disability grant", "PEN", 0, 30,
     "Monthly grant for citizens living with a qualifying disability.",
     "Valid national ID\nMedical assessment report\nProof of residence"),
    ("PEN-CHL", "Apply for a child grant", "PEN", 0, 21,
     "Support grant for the caregivers of qualifying children.",
     "Caregiver's national ID\nChild's birth certificate\nProof of residence"),
]

SESOTHO_FIRST = ["Thabo", "Mpho", "Lineo", "Teboho", "Palesa", "Lerato", "Katleho",
                 "Nthabiseng", "Refiloe", "Tumelo", "Bokang", "Rethabile",
                 "Mamello", "Neo", "Kabelo", "Realeboha", "Hlompho", "Puleng",
                 "Tshepo", "Mosa", "Retselisitsoe", "Limpho", "Sello", "Matseliso"]

SESOTHO_LAST = ["Mokoena", "Lebeko", "Ramokoatsi", "Thabane", "Letsie", "Mofokeng",
                "Sekhonyana", "Molapo", "Khoabane", "Rantso", "Maseribane",
                "Phakoe", "Nthunya", "Matete", "Sekese", "Ramaema", "Tlali",
                "Lekhanya", "Motsoahae", "Makhele"]

STAFF = [
    # username, name, dept, position, approve, manager
    ("ha.officer", "Mateboho Letsie", "HA", "Registration Officer", True, False),
    ("ha.manager", "Tsepo Ramaema", "HA", "District Registrar", True, True),
    ("pol.officer", "Sgt. Lebohang Phakoe", "POL", "Records Officer", True, False),
    ("trf.officer", "Nthabiseng Molapo", "TRF", "Licensing Officer", True, False),
    ("fin.officer", "Karabo Sekese", "FIN", "Revenue Officer", True, False),
    ("pen.officer", "Mamello Tlali", "PEN", "Grants Officer", True, False),
    ("pas.officer", "Relebohile Matete", "PAS", "Passport Officer", True, False),
]


def run_seed():
    print("Rebuilding the database...")
    db.drop_all()
    db.create_all()

    # ---------------------------------------------------------------- departments
    depts = {}
    for code, name, ministry, desc, phone, email, office in DEPARTMENTS:
        d = Department(code=code, name=name, ministry=ministry, description=desc,
                       contact_phone=phone, contact_email=email, head_office=office)
        db.session.add(d)
        depts[code] = d
    db.session.flush()

    # ------------------------------------------------------------------- services
    services = {}
    for code, name, dcode, fee, days, desc, docs in SERVICES:
        s = Service(code=code, name=name, department=depts[dcode], fee=fee,
                    processing_days=days, description=desc, required_documents=docs)
        db.session.add(s)
        services[code] = s
    db.session.flush()

    # ---------------------------------------------------------------------- admin
    admin = User(username="admin", email="admin@igss.gov.ls", role="admin")
    admin.set_password("Admin@2026")
    db.session.add(admin)

    # ---------------------------------------------------------------------- staff
    employees = []
    for i, (username, name, dcode, position, approve, manager) in enumerate(STAFF, 1):
        u = User(username=username, email=f"{username}@igss.gov.ls", role="employee")
        u.set_password("Staff@2026")
        e = Employee(user=u, employee_no=f"EMP{1000 + i}", full_name=name,
                     department=depts[dcode], position=position,
                     office=depts[dcode].head_office, phone="+266 5800 00" + str(10 + i),
                     can_approve=approve, is_manager=manager)
        db.session.add_all([u, e])
        employees.append(e)
    db.session.flush()

    # ------------------------------------------------------------------- citizens
    citizens = []
    used_ids = set()
    for i in range(26):
        first = random.choice(SESOTHO_FIRST)
        last = random.choice(SESOTHO_LAST)

        # A spread of ages, with a few over 70 so pension eligibility is visible
        if i < 4:
            age = random.randint(70, 86)
        elif i < 8:
            age = random.randint(55, 69)
        else:
            age = random.randint(19, 54)
        dob = date.today() - timedelta(days=age * 365 + random.randint(0, 364))

        nid = str(dob.year)[-2:] + f"{random.randint(10000000, 99999999)}"
        while nid in used_ids:
            nid = str(dob.year)[-2:] + f"{random.randint(10000000, 99999999)}"
        used_ids.add(nid)

        username = f"{first.lower()}.{last.lower()}{i}"
        u = User(username=username, email=f"{username}@example.co.ls", role="citizen")
        u.set_password("Citizen@2026")

        verified = i < 22  # a few left unverified so Home Affairs has a queue
        c = Citizen(
            user=u, national_id=nid, first_name=first, last_name=last,
            date_of_birth=dob, gender=random.choice(["Female", "Male"]),
            phone=f"+266 5{random.randint(1000000, 9999999)}",
            email=u.email, district=random.choice(DISTRICTS),
            address=f"{random.randint(1, 400)} {random.choice(['Ha Thetsane','Maseru West','Khubetsoana','Lithabaneng','Sea Point','Ha Hoohlo'])}",
            verified=verified,
            verified_on=datetime.utcnow() - timedelta(days=random.randint(1, 120)) if verified else None,
            verified_by="Mateboho Letsie" if verified else None,
            created_at=datetime.utcnow() - timedelta(days=random.randint(5, 400)),
        )
        db.session.add_all([u, c])
        citizens.append(c)
    db.session.flush()

    # --------------------------------------------------------- the demo citizen
    demo_user = User(username="thabo", email="thabo@example.co.ls", role="citizen")
    demo_user.set_password("Citizen@2026")
    demo = Citizen(
        user=demo_user, national_id="4208119112", first_name="Thabo",
        last_name="Mokoena", date_of_birth=date(1992, 3, 14), gender="Male",
        phone="+266 5822 4417", email="thabo@example.co.ls", district="Maseru",
        address="17 Ha Thetsane, Maseru", verified=True,
        verified_on=datetime.utcnow() - timedelta(days=90),
        verified_by="Mateboho Letsie",
        created_at=datetime.utcnow() - timedelta(days=120),
    )
    db.session.add_all([demo_user, demo])
    citizens.append(demo)
    db.session.flush()

    # ------------------------------------------------------ departmental records
    for c in citizens:
        # Civil registration: everyone has a birth record
        db.session.add(CivilRecord(
            citizen=c, record_type="Birth", reference=reference_code("CIV"),
            event_date=c.date_of_birth,
            place=random.choice(["Queen Mamohato Memorial Hospital, Maseru",
                                 "Motebang Hospital, Leribe",
                                 "Mafeteng Government Hospital",
                                 "Berea District Hospital"]),
            details="Registered at birth."))

        if c.verified and random.random() < 0.45:
            issue = date.today() - timedelta(days=random.randint(100, 2600))
            db.session.add(Passport(
                citizen=c, passport_no=f"LS{random.randint(100000, 999999)}",
                passport_type="Ordinary", issue_date=issue,
                expiry_date=issue + timedelta(days=3650),
                issuing_office="Maseru Head Office"))

        if c.verified and c.age and c.age >= 18 and random.random() < 0.5:
            issue = date.today() - timedelta(days=random.randint(60, 1700))
            db.session.add(DriverLicence(
                citizen=c, licence_no=f"DL{random.randint(100000, 999999)}",
                licence_class=random.choice(["A", "B", "B", "C", "EC"]),
                issue_date=issue, expiry_date=issue + timedelta(days=1825)))

        if c.verified and random.random() < 0.35:
            db.session.add(Vehicle(
                citizen=c,
                registration_no=f"{random.choice('ABCD')} {random.randint(1000, 9999)}",
                make=random.choice(["Toyota", "Nissan", "Ford", "Volkswagen", "Isuzu"]),
                model=random.choice(["Hilux", "NP200", "Ranger", "Polo", "KB250", "Corolla"]),
                year=random.randint(2005, 2024),
                colour=random.choice(["White", "Silver", "Blue", "Black", "Red"]),
                engine_no=f"ENG{random.randint(100000, 999999)}",
                chassis_no=f"CHS{random.randint(1000000, 9999999)}",
                licence_expiry=date.today() + timedelta(days=random.randint(-40, 330)),
                roadworthy_expiry=date.today() + timedelta(days=random.randint(-20, 340))))

        if random.random() < 0.3:
            status = random.choice(["Clear", "Clear", "Clear", "Pending", "Flagged"])
            issued = date.today() - timedelta(days=random.randint(5, 300))
            db.session.add(PoliceRecord(
                citizen=c, case_number=reference_code("PCC"),
                record_type=random.choice(["Clearance", "Employment", "Emigration"]),
                clearance_status=status, fingerprints_taken=status != "Pending",
                station="Police Headquarters, Maseru",
                issued_date=issued if status == "Clear" else None,
                expiry_date=issued + timedelta(days=180) if status == "Clear" else None,
                remarks="No adverse record found." if status == "Clear" else
                        ("Background check in progress." if status == "Pending"
                         else "Open matter — refer to the investigating officer.")))

        if c.verified and random.random() < 0.55:
            db.session.add(FinanceRecord(
                citizen=c, tax_number=reference_code("TAX"),
                tax_status=random.choice(["Compliant", "Compliant", "Return outstanding",
                                          "In arrears"]),
                outstanding_balance=round(random.choice([0, 0, 0, 450.0, 1280.50, 320.0]), 2),
                last_filed=date.today() - timedelta(days=random.randint(20, 500))))

        if c.pension_eligible and c.verified and random.random() < 0.7:
            db.session.add(PensionRecord(
                citizen=c, pension_no=reference_code("PEN"),
                grant_type="Old Age Pension", monthly_amount=850.0,
                pay_point=f"{c.district} Post Office",
                next_payment=date.today().replace(day=1) + timedelta(days=32),
                registered_on=date.today() - timedelta(days=random.randint(60, 900))))

    db.session.flush()

    # --------------------------------------------------------------- applications
    service_list = list(services.values())
    statuses = ["Submitted", "Under Review", "Under Review", "Awaiting Payment",
                "Awaiting Documents", "Approved", "Approved", "Collected", "Rejected"]

    for _ in range(64):
        c = random.choice([x for x in citizens if x.verified])
        s = random.choice(service_list)
        submitted = datetime.utcnow() - timedelta(days=random.randint(0, 45),
                                                  hours=random.randint(0, 23))
        status = random.choice(statuses)

        a = Application(
            reference=reference_code("APP"), citizen=c, service=s,
            department=s.department, status=status,
            priority=random.choice(["Normal"] * 6 + ["Urgent"]),
            purpose=random.choice([
                "Employment abroad.", "My current document expires soon.",
                "First application.", "Required by my employer.",
                "Travelling for a family funeral.", "Renewing after a lost document.",
            ]),
            submitted_at=submitted,
            updated_at=submitted + timedelta(days=random.randint(0, 12)),
            due_date=(submitted + timedelta(days=s.processing_days or 14)).date(),
        )
        if status != "Submitted":
            a.officer = random.choice([e for e in employees
                                       if e.department_id == s.department_id] or employees)
        if status == "Rejected":
            a.decision_reason = random.choice([
                "The medical certificate supplied has expired.",
                "The photographs do not meet the required specification.",
                "Supporting documents did not match the details on the national ID.",
            ])
        db.session.add(a)
        db.session.flush()

        # Status history
        db.session.add(StatusHistory(
            application=a, from_status=None, to_status="Submitted",
            changed_by=c.full_name, note="Application submitted.",
            changed_at=submitted))
        if status not in ("Submitted",):
            db.session.add(StatusHistory(
                application=a, from_status="Submitted", to_status=status,
                changed_by=a.officer.full_name if a.officer else "System",
                note=a.decision_reason or None,
                changed_at=a.updated_at))

        # Fee and payment
        if s.fee:
            paid = status not in ("Awaiting Payment", "Submitted")
            db.session.add(Payment(
                reference=reference_code("PAY"), citizen=c, application=a,
                amount=s.fee, method=random.choice(["M-Pesa", "EcoCash", "Bank Transfer"]),
                status="Paid" if paid else "Pending",
                description=f"Fee for {s.name}",
                paid_at=submitted + timedelta(hours=random.randint(1, 60)) if paid else None,
                created_at=submitted))

        # Notification to the applicant
        db.session.add(Notification(
            user=c.user, title=f"{s.name}: {status.lower()}",
            message=f"Reference {a.reference} is now “{status}”.",
            link=f"/citizen/applications/{a.id}",
            category="success" if status in ("Approved", "Collected")
                     else ("danger" if status == "Rejected" else "info"),
            read=random.random() < 0.6, created_at=a.updated_at))

    # --------------------------------------------------- documents for the demo
    for doc_type in ["Birth certificate", "Passport photograph", "Certified ID copy"]:
        db.session.add(Document(
            citizen=demo, doc_type=doc_type,
            original_name=f"{doc_type.lower().replace(' ', '_')}.pdf",
            stored_name=f"seed_{doc_type.lower().replace(' ', '_')}.pdf",
            size_kb=random.randint(80, 900), verified=True,
            verified_by="Mateboho Letsie",
            uploaded_at=datetime.utcnow() - timedelta(days=random.randint(10, 100))))

    db.session.add(Notification(
        user=demo_user, title="Welcome to the Integrated Government Services System",
        message="Your identity is verified, so you can apply for any connected service. "
                "Documents in your wallet are reused automatically.",
        link="/citizen/apply", category="info"))

    # -------------------------------------------------------- an access request
    db.session.add(AccessRequest(
        reference=reference_code("REQ"),
        requesting_department=depts["PEN"], owning_department=depts["HA"],
        citizen=citizens[0], requested_by="Mamello Tlali",
        reason="Confirming date of birth and civil status before enrolling this "
               "applicant for the Old Age Pension.",
        status="Pending"))

    # ------------------------------------------------------------- audit history
    sample_actions = [
        ("LOGIN", "User", "Signed in"),
        ("SEARCH", "Citizen", "Searched citizen register"),
        ("VIEW_CITIZEN", "Citizen", "Opened a citizen profile"),
        ("VERIFY_IDENTITY", "Citizen", "Identity verified against the civil register"),
        ("STATUS_CHANGE", "Application", "Under Review -> Approved"),
        ("PAYMENT", "Payment", "Fee received"),
        ("REPORT", "Report", "Generated departmental performance report"),
    ]
    for i in range(70):
        e = random.choice(employees)
        action, entity, desc = random.choice(sample_actions)
        db.session.add(AuditLog(
            user=e.user, actor=e.full_name, department=e.department.name,
            action=action, entity=entity, entity_ref=reference_code(entity[:3].upper()),
            description=desc, ip_address=f"10.20.{random.randint(1,6)}.{random.randint(2,250)}",
            timestamp=datetime.utcnow() - timedelta(days=random.randint(0, 20),
                                                    hours=random.randint(0, 23),
                                                    minutes=random.randint(0, 59))))

    # --------------------------------------------------------- favourites & reviews
    verified_citizens = [c for c in citizens if c.verified]
    comments = [
        "Straightforward once my documents were verified. Faster than I expected.",
        "The queue moved quickly, but I wish the office had told me about the fee upfront.",
        "Reused my documents from another department, which saved a trip into town.",
        "Took a bit longer than the stated processing time, but the notifications kept me informed.",
        "Friendly officer at the counter, no issues at all.",
        "",
    ]
    reviewed_pairs = set()
    for _ in range(28):
        c = random.choice(verified_citizens)
        closed_apps = [a for a in c.applications if a.status in ("Approved", "Collected")]
        if not closed_apps:
            continue
        app_ = random.choice(closed_apps)
        if app_.id in reviewed_pairs:
            continue
        reviewed_pairs.add(app_.id)
        db.session.add(Review(
            citizen=c, service=app_.service, application=app_,
            rating=random.choice([3, 4, 4, 5, 5, 5, 2]),
            comment=random.choice(comments),
            created_at=app_.updated_at + timedelta(days=random.randint(0, 5))))

    for c in random.sample([x for x in verified_citizens if x.id != demo.id],
                           min(10, len(verified_citizens) - 1)):
        for s in random.sample(service_list, random.randint(1, 3)):
            db.session.add(Favourite(citizen=c, service=s))

    # A few favourites and one review for the demo citizen, so the pages are never empty
    db.session.add(Favourite(citizen=demo, service=services["PAS-REN"]))
    db.session.add(Favourite(citizen=demo, service=services["TRF-VLR"]))

    db.session.commit()

    print(f"""
Database seeded.

  Departments   {Department.query.count()}
  Services      {Service.query.count()}
  Citizens      {Citizen.query.count()}
  Staff         {Employee.query.count()}
  Applications  {Application.query.count()}
  Payments      {Payment.query.count()}
  Audit entries {AuditLog.query.count()}

Sign in with any of these:

  Administrator   admin         / Admin@2026
  Home Affairs    ha.officer    / Staff@2026
  Police          pol.officer   / Staff@2026
  Traffic         trf.officer   / Staff@2026
  Finance         fin.officer   / Staff@2026
  Pensions        pen.officer   / Staff@2026
  Passport        pas.officer   / Staff@2026
  Citizen         thabo         / Citizen@2026
""")


if __name__ == "__main__":
    from app import create_app
    app = create_app()
    with app.app_context():
        run_seed()
