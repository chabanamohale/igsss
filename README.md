# Integrated Government Services System (IGSS)

A working Flask prototype of the system described in the Software Design / HCI
documentation: one verified citizen profile, anchored by Home Affairs and reused by
Police, Traffic and Transport, Finance, Pensions and Passport Services.

---

## Running it in Visual Studio Code

Open the `igss` folder in VS Code, then in the integrated terminal:

```bash
# 1. Create and activate a virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 2. Install the dependencies
pip install -r requirements.txt

# 3. Build the database and load demonstration data
python seed.py

# 4. Start the server
python run.py
```

Then open **http://127.0.0.1:5000**.

Press `F5` in VS Code to run it under the debugger instead — a launch configuration is
included in `.vscode/launch.json`.

### Sign-in details after seeding

| Role | Username | Password |
|---|---|---|
| System administrator | `admin` | `Admin@2026` |
| Home Affairs officer | `ha.officer` | `Staff@2026` |
| Home Affairs registrar | `ha.manager` | `Staff@2026` |
| Police officer | `pol.officer` | `Staff@2026` |
| Traffic officer | `trf.officer` | `Staff@2026` |
| Finance officer | `fin.officer` | `Staff@2026` |
| Pensions officer | `pen.officer` | `Staff@2026` |
| Passport officer | `pas.officer` | `Staff@2026` |
| Citizen | `thabo` | `Citizen@2026` |

Sign in as different officers to see the access matrix in action: the same citizen
profile shows different record areas depending on which department you are in.

---

## Project structure

```
igss/
├── run.py                     Entry point — python run.py
├── app.py                     Application factory, error handlers, Jinja filters
├── config.py                  Development and production configuration classes
├── extensions.py              SQLAlchemy, Flask-Login, Bcrypt instances
├── models.py                  All 17 entities from the ERD
├── seed.py                    Demonstration data
├── smoke_test.py              Walks every route as every role
├── requirements.txt
│
├── blueprints/                APPLICATION LAYER
│   ├── main.py                Public pages, service catalogue, status lookup
│   ├── auth.py                Registration, sign-in, password management
│   ├── citizen.py             Citizen portal
│   ├── employee.py            Staff workspace, queue, citizen lookup, reports
│   ├── departments.py         The six departmental modules
│   └── admin.py               Accounts, catalogue, access matrix, audit log
│
├── utils/
│   ├── security.py            ACCESS_MATRIX and the role/area decorators
│   └── helpers.py             Audit writing, uploads, status transitions
│
├── templates/                 PRESENTATION LAYER
│   ├── base.html              Signed-in shell with sidebar
│   ├── public.html            Public shell
│   ├── partials/              nav.html, macros.html
│   ├── main/ auth/ citizen/ employee/ departments/ admin/ errors/
│
├── static/
│   ├── css/style.css          Design tokens and every component
│   ├── js/main.js             Progressive enhancement only
│   └── uploads/               Uploaded supporting documents
│
└── instance/igss.db           DATA LAYER — SQLite, created by seed.py
```

This is the three-tier architecture from section 4.1 of the documentation:
presentation in `templates/` and `static/`, application logic in `blueprints/` and
`utils/`, data in `models.py` and `instance/igss.db`.

---

## Interface features

On top of the core workflow, the interface layer includes:

- **Dark / light mode** — a toggle in the top bar and on the Settings page, saved
  per-device in `localStorage`. Every colour in `style.css` is a CSS custom property, so
  the whole interface — including the department stripe colours — repaints instantly.
- **Motion** — scroll-triggered reveals, hover lift and tilt on cards, animated
  counters on the homepage, button ripple feedback, and page-fade transitions.
  Everything respects `prefers-reduced-motion`, and none of it depends on JavaScript
  being enabled: content is visible immediately without it, and only animates on top
  when a script can run (see `html.js-reveal` in `style.css` / `main.js`).
- **Toasts, modals and dropdowns** — flash messages are promoted into dismissable
  toast notifications; destructive actions (`data-confirm` on a form) open a modal
  instead of a browser `confirm()`; the notification bell is a live dropdown fetched
  from `/api/v1/notifications`.
- **Carousels, galleries and a lightbox** — the homepage department strip and the
  service catalogue both scroll natively with snap points; document thumbnails open in
  a lightbox.
- **Video and audio** — the Help page embeds a short placeholder walkthrough video and
  an audio announcement (`static/media/`), demonstrating `<video>`/`<audio>` support.
  Swap in real recordings for a production version.
- **An interactive map** — Help also shows every district office on a Leaflet map
  with OpenStreetMap tiles (loaded from a CDN — needs internet access; nothing to
  configure).
- **Search, filter and sort** — the service catalogue supports a live text search,
  a department filter, and sorting by name, fee or processing time, all as ordinary
  GET query parameters so the URL is shareable and works without JavaScript.
- **Favourites and reviews** — citizens can star a service from the catalogue and see
  their favourites at `/citizen/favourites`; after a service is Approved or Collected
  they can leave a star rating and comment, which shows as an average rating on the
  public service page.
- **A drag-and-drop queue board** — `/staff/queue/board` shows each department's open
  cases as a kanban board. Dragging a card to another column calls
  `POST /api/v1/queue/status`, which re-checks the department ownership rule before
  saving, so the visual board can't be used to bypass the access model.
- **Charts** — the admin dashboard and staff reports page fetch `/api/v1/stats` and
  draw a trend line and a department breakdown with Chart.js (also CDN-loaded). The
  original dependency-free CSS bar charts stay in place underneath as a fallback that
  works with no internet access and no JavaScript.
- **Settings pages** — every role has a Settings screen for notification preferences
  (email/SMS, stored on the user) and the theme toggle.

### A note on the CDN-loaded pieces

Leaflet (the map) and Chart.js (the charts) load from `cdnjs.cloudflare.com` at
runtime, and the map tiles load from OpenStreetMap. Everything else in the project —
including every animation, the theme system, toasts, modals, the kanban board, and the
favourites/reviews system — is self-contained and needs no internet access once
installed. If you are marking or demonstrating this offline, everything works except
those two panels; the rest of each page around them still renders normally.

---

## What the system does

### Citizens
Register with a national ID, then wait for Home Affairs to verify it. Once verified:
browse and apply for any of 18 services, reuse verified documents from the document
wallet instead of re-uploading them, pay fees and print receipts, track each
application through its full status history, see every record the six departments hold,
star favourite services, leave reviews after a decision, and receive a notification on
each status change.

### Government employees
A departmental dashboard with queue counts, a 14-day intake sparkline and a status
breakdown. A filterable work queue with claim and reassign, plus a visual kanban board
for quick drag-and-drop status changes. Citizen lookup and counter-side identity
verification. A case file with documents, internal notes, status transitions and a
decision record. Cross-department data-sharing requests. Performance reporting by
status, service, district and month, with charts.

### The six departmental modules
- **Home Affairs** — verification queue and civil registration (birth, marriage, death)
- **Passport Services** — passport register, application queue, issuance with a ten-year expiry
- **Police** — clearance files, fingerprint tracking, clear/flag decisions with six-month validity
- **Traffic and Transport** — driver licensing by class, vehicle registration and annual renewal
- **Finance** — revenue by department, transaction ledger, reversals, taxpayer accounts
- **Pensions** — beneficiary register, payroll total, and an eligibility list built by comparing
  dates of birth in the civil register against the age-70 condition

### System administration
Account creation and role changes, suspension and password reset, department and
service catalogue management, a read-only view of the access matrix, the full audit
log with filters, and a system-wide dashboard with charts.

---

## Security model


Three things are worth pointing out in a demonstration:

**The access matrix.** `ACCESS_MATRIX` in `utils/security.py` maps each department code
to the record areas it may read. Routes are guarded with `@area_required` and
`@department_required`; templates check `can_access()` before rendering an area. Because
both read the same dictionary, the interface and the routes can never disagree.

**The audit trail.** `record_audit()` is called on every citizen search, profile view,
document open, status change and payment. Each entry stores the officer's name,
department, IP address and timestamp. Officers see their own trail under *My activity*;
administrators see everything.

**Business rules enforced server-side, not just in the form.** A passport cannot be
issued against an unverified identity. An application cannot be approved while a fee is
outstanding. An Old Age Pension enrolment is refused if the date of birth in the civil
register puts the applicant under 70. A rejection requires a written reason.

Passwords are hashed with bcrypt. Sessions are HttpOnly, SameSite=Lax, and use
Flask-Login's strong session protection. Uploads are capped at 8 MB, extension-filtered,
and stored under timestamped names so a malicious filename cannot overwrite anything.

---

## Checking that it works

```bash
python smoke_test.py
```

This signs in as every role, visits every page (166 checks in total), checks the write
operations succeed — including the favourites toggle, review submission and the kanban
drag-and-drop status API — and asserts the permission boundaries hold, for example that
a Traffic officer opening a citizen profile sees the driver licence area but not the tax
account or police records, and is refused a Finance case file outright on the kanban
board just as in the case-file view.

---

## Notes for the report

- Technologies match section 4.2 exactly: Python, Flask, SQLite, HTML5, CSS3,
  JavaScript, Git.
- The interface is built on custom CSS rather than stock Bootstrap. If the marking
  criteria specifically require Bootstrap, add the CDN link in `templates/base.html`;
  the class names used here do not collide with Bootstrap's.
- The department key colours and the 4px record stripe are a deliberate usability
  decision, not decoration: a clerk scanning a long queue reads record ownership before
  reading any text.
- JavaScript is progressive enhancement only. Every page, form and workflow functions
  with JavaScript disabled, which matters for the accessibility requirement in
  section 2.5.

This is a student prototype for coursework, not a live government service.
