"""
Walk every page as every role and report any that fail.

    python smoke_test.py
"""
import warnings
warnings.filterwarnings("ignore")

from app import create_app
from extensions import db
from models import Citizen, Application, Service, Payment, Document, User

app = create_app()
failures = []
checked = 0


def sign_in(client, username, password):
    return client.post("/auth/login",
                       data={"identifier": username, "password": password},
                       follow_redirects=True)


def visit(client, path, label):
    global checked
    checked += 1
    r = client.get(path, follow_redirects=True)
    if r.status_code != 200:
        failures.append(f"{label:12} {path:48} -> HTTP {r.status_code}")
        return None
    body = r.get_data(as_text=True)
    for marker in ("Traceback", "jinja2.exceptions", "UndefinedError",
                   "not cleared for this record", "could not complete that request"):
        if marker in body:
            failures.append(f"{label:12} {path:48} -> page rendered '{marker}'")
            return None
    return body


with app.app_context():
    cid = db.session.query(Citizen).filter_by(national_id="4208119112").first().id
    any_cid = db.session.query(Citizen).first().id
    app_id = db.session.query(Application).first().id
    svc = db.session.query(Service).filter_by(code="PAS-NEW").first().code
    doc_id = db.session.query(Document).first().id

    # a demo citizen's own application, for the citizen-side detail page
    demo_app = db.session.query(Application).filter_by(citizen_id=cid).first()
    demo_app_id = demo_app.id if demo_app else None
    demo_pay = db.session.query(Payment).filter_by(citizen_id=cid).first()
    demo_pay_id = demo_pay.id if demo_pay else None

# ---------------------------------------------------------------- public
with app.test_client() as c:
    for path in ["/", "/services", "/services?department=HA", f"/services/{svc}",
                 "/track", "/help", "/auth/login", "/auth/register"]:
        visit(c, path, "public")

    for path in ["/static/media/how-it-works.mp4", "/static/media/announcement.mp3"]:
        r = c.get(path)
        if r.status_code != 200:
            failures.append(f"public       {path} -> HTTP {r.status_code}")
        checked += 1

    if c.get("/no-such-page").status_code != 404:
        failures.append("public       /no-such-page should return 404")
    checked += 1

    r = c.post("/track", data={"reference": "APP-NOPE"}, follow_redirects=True)
    if r.status_code != 200:
        failures.append(f"public       POST /track -> HTTP {r.status_code}")

# ---------------------------------------------------------------- citizen
with app.test_client() as c:
    sign_in(c, "thabo", "Citizen@2026")
    paths = ["/citizen/", "/citizen/profile", "/citizen/records",
             "/citizen/apply", "/citizen/apply?department=PAS",
             f"/citizen/apply/{svc}", "/citizen/applications",
             "/citizen/applications?status=Approved", "/citizen/documents",
             "/citizen/payments", "/citizen/notifications",
             "/citizen/notifications/count", "/auth/password", "/go",
             "/citizen/favourites", "/citizen/settings",
             "/api/v1/notifications", "/api/v1/notifications/count",
             "/api/v1/services", "/api/v1/services?q=passport"]
    if demo_app_id:
        paths.append(f"/citizen/applications/{demo_app_id}")
    if demo_pay_id:
        paths.append(f"/citizen/payments/{demo_pay_id}/receipt")
    for p in paths:
        visit(c, p, "citizen")

    # A citizen must not reach staff areas
    for p in ["/staff/", "/admin/", "/departments/police"]:
        r = c.get(p, follow_redirects=True)
        if "Work queue" in r.get_data(as_text=True) or "System overview" in r.get_data(as_text=True):
            failures.append(f"citizen      {p} -> citizen reached a staff page")

# ------------------------------------------------------------- each officer
officer_modules = {
    "ha.officer":  ["/departments/home-affairs", "/departments/passport"],
    "pol.officer": ["/departments/police"],
    "trf.officer": ["/departments/traffic"],
    "fin.officer": ["/departments/finance"],
    "pen.officer": ["/departments/pensions"],
    "pas.officer": ["/departments/passport"],
}

DEPT_CODE = {"ha.officer": "HA", "pol.officer": "POL", "trf.officer": "TRF",
             "fin.officer": "FIN", "pen.officer": "PEN", "pas.officer": "PAS"}

for username, modules in officer_modules.items():
    with app.app_context():
        from models import Department
        d = db.session.query(Department).filter_by(code=DEPT_CODE[username]).first()
        own = db.session.query(Application).filter_by(department_id=d.id).first()
        own_id = own.id if own else None
    with app.test_client() as c:
        sign_in(c, username, "Staff@2026")
        common = ["/staff/", "/staff/queue", "/staff/queue?scope=unassigned",
                  "/staff/queue?status=Under+Review", "/staff/search",
                  "/staff/search?q=Mokoena", f"/staff/citizens/{any_cid}",
                  f"/staff/citizens/{cid}", "/staff/verify", "/staff/reports",
                  "/staff/activity", "/staff/access-requests",
                  "/staff/queue/board", "/staff/settings",
                  "/api/v1/stats", "/go"]
        if own_id:
            common.append(f"/staff/applications/{own_id}")
        for p in common + modules:
            visit(c, p, username.split(".")[0])

        r = c.post("/staff/verify", data={"national_id": "4208119112"},
                   follow_redirects=True)
        if "Match found" not in r.get_data(as_text=True):
            failures.append(f"{username} POST /staff/verify -> no match returned")

# ------------------------------------------------------------------- admin
with app.test_client() as c:
    sign_in(c, "admin", "Admin@2026")
    for p in ["/admin/", "/admin/users", "/admin/users?role=employee",
              "/admin/users/new", "/admin/departments", "/admin/services",
              "/admin/permissions", "/admin/audit", "/admin/audit?action=LOGIN",
              "/admin/settings", "/staff/queue", f"/staff/citizens/{cid}",
              "/staff/reports", "/go"]:
        visit(c, p, "admin")

# -------------------------------------------------------- write operations
with app.test_client() as c:
    sign_in(c, "thabo", "Citizen@2026")
    r = c.post(f"/citizen/apply/{svc}",
               data={"purpose": "Smoke test application", "priority": "Normal"},
               follow_redirects=True)
    if "reference is" not in r.get_data(as_text=True):
        failures.append("citizen      POST apply -> application was not created")
    checked += 1

    r = c.post("/citizen/profile",
               data={"phone": "+266 5822 4417", "email": "thabo@example.co.ls",
                     "address": "17 Ha Thetsane", "district": "Maseru"},
               follow_redirects=True)
    if "saved" not in r.get_data(as_text=True):
        failures.append("citizen      POST profile -> details were not saved")
    checked += 1

    # Favourite toggle via the API
    with app.app_context():
        svc_row = db.session.query(Service).filter_by(code=svc).first()
        svc_id = svc_row.id
    r = c.post(f"/api/v1/favourites/{svc_id}")
    d = r.get_json()
    if not (d and d.get("favourited") is True):
        failures.append("citizen      POST favourite -> did not toggle on")
    r2 = c.post(f"/api/v1/favourites/{svc_id}")
    d2 = r2.get_json()
    if not (d2 and d2.get("favourited") is False):
        failures.append("citizen      POST favourite -> did not toggle off")
    checked += 2

    # Review submission on a closed application
    with app.app_context():
        closed = (db.session.query(Application)
                 .filter_by(citizen_id=cid).filter(Application.status.in_(
                     ["Approved", "Collected"])).first())
        closed_id = closed.id if closed else None
    if closed_id:
        r = c.post("/api/v1/reviews", json={"application_id": closed_id, "rating": 5,
                                            "comment": "Smoke test review"})
        d = r.get_json()
        if not (d and d.get("ok")):
            failures.append("citizen      POST review -> was not accepted")
        checked += 1

with app.test_client() as c:
    sign_in(c, "ha.officer", "Staff@2026")
    with app.app_context():
        unv = db.session.query(Citizen).filter_by(verified=False).first()
        unv_id = unv.id if unv else None
    if unv_id:
        r = c.post(f"/staff/citizens/{unv_id}/verify", follow_redirects=True)
        if "verified" not in r.get_data(as_text=True).lower():
            failures.append("ha.officer   POST verify citizen -> did not verify")
        checked += 1

with app.test_client() as c:
    sign_in(c, "pen.officer", "Staff@2026")
    # Enrolling someone too young must be refused by the business rule
    with app.app_context():
        young = db.session.query(Citizen).filter(Citizen.verified == True).all()
        young = [x for x in young if x.age and x.age < 70]
        young_id = young[0].id if young else None
    if young_id:
        r = c.post("/departments/pensions/enrol",
                   data={"citizen_id": young_id, "grant_type": "Old Age Pension",
                         "monthly_amount": 850, "pay_point": "Maseru Post Office"},
                   follow_redirects=True)
        if "starts at 70" not in r.get_data(as_text=True):
            failures.append("pen.officer  age rule did not block an underage enrolment")
        checked += 1

# ------------------------------------------------- permission boundary check
with app.test_client() as c:
    sign_in(c, "trf.officer", "Staff@2026")
    body = c.get(f"/staff/citizens/{cid}", follow_redirects=True).get_data(as_text=True)
    if "Tax account" in body:
        failures.append("trf.officer  saw Finance records it is not cleared for")
    if "Police clearance" in body:
        failures.append("trf.officer  saw Police records it is not cleared for")
    if "Driver licence" not in body:
        failures.append("trf.officer  could not see its own Driver licence area")
    checked += 1

    with app.app_context():
        from models import Department
        fin = db.session.query(Department).filter_by(code="FIN").first()
        other = db.session.query(Application).filter_by(department_id=fin.id).first()
    if other and c.get(f"/staff/applications/{other.id}").status_code != 403:
        failures.append("trf.officer  opened a Finance case file it does not own")
    checked += 1

    r = c.get("/departments/finance", follow_redirects=True)
    if "Revenue by department" in r.get_data(as_text=True):
        failures.append("trf.officer  reached the Finance module")
    checked += 1

# ---------------------------------------------------------- kanban board
with app.test_client() as c:
    sign_in(c, "trf.officer", "Staff@2026")
    with app.app_context():
        from models import Department
        trf = db.session.query(Department).filter_by(code="TRF").first()
        own_app = (db.session.query(Application)
                  .filter_by(department_id=trf.id)
                  .filter(Application.status.notin_(["Rejected", "Collected"])).first())
        own_app_id, current_status = (own_app.id, own_app.status) if own_app else (None, None)
    if own_app_id:
        next_status = "Under Review" if current_status != "Under Review" else "Awaiting Payment"
        r = c.post("/api/v1/queue/status",
                   json={"application_id": own_app_id, "status": next_status})
        d = r.get_json()
        if not (d and d.get("ok")):
            failures.append("trf.officer  kanban status update was rejected")
        checked += 1

# -------------------------------------------------------------------- report
print(f"\n{checked} checks run.")
if failures:
    print(f"\n{len(failures)} FAILURES:\n")
    for f in failures:
        print("  " + f)
else:
    print("All routes render, all role boundaries hold, all business rules fire.")
