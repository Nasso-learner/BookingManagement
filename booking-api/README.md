# booking-api

The REST backend for MediBook, built with Django REST Framework and PostgreSQL. It holds all the models, the business logic and JWT authentication. The UI lives in the separate **booking-web** project, which calls this API over HTTP.

## Run locally

```bash
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                # set POSTGRES_* and JWT_SIGNING_KEY
python manage.py migrate
python manage.py seed_demo                          # demo departments, doctors, schedules, users
python manage.py runserver 8000
```

Docker: `docker compose up --build` starts PostgreSQL and the API on port 8000.

If you don't have Postgres, set `USE_SQLITE=1` to use SQLite instead. This is for local work only.

Demo logins (password in brackets):
- `admin@medibook.local` (Admin@12345)
- `sarah.khan@medibook.local` (Doctor@12345)
- `patient@medibook.local` (Patient@12345)

## Tests

```bash
USE_SQLITE=1 python manage.py test apps
```

## Layout

| App | Responsibility |
|---|---|
| `accounts` | Custom `User` (email login, roles ADMIN/DOCTOR/PATIENT), JWT login/refresh/logout, registration, password reset, role permissions |
| `departments` | Department CRUD (admin write, everyone read) |
| `doctors` | `Doctor`, `DoctorAvailability` (overlap-checked), search, free slots and dates |
| `patients` | `Patient` profiles (admin manage, doctors see their own patients, `me` for patients) |
| `appointments` | `Appointment`, **`services/booking_service.py`** (the booking engine), role dashboards |
| `notifications` | In-app notifications, plus the `send_reminders` command (run it daily from cron) |
| `audit_logs` | `AuditLog` and the `audit()` helper (logins, logouts, every appointment/doctor/patient change) |
| `reports` | Plotly report engine: saved SQL reports, run read-only as `report_reader` (setup: `apps/reports/setup_reports.sql`, starters: `python manage.py seed_reports`). Doctors only see shared reports, with `:doctor_id` bound to themselves |
| `analytics` | Signed Metabase static-embed URLs (`/api/analytics/embed/`). Setup steps are in [metabase/README.md](metabase/README.md) |

Each app has its own `urls.py`. `config/urls.py` only mounts them under `/api/`.

## How double booking is prevented

1. **Service checks** in `booking_service._book()`, all inside `transaction.atomic()`:
   - the doctor exists and is active
   - the date and time are not in the past
   - the time matches a slot in the doctor's availability
   - the doctor has no overlapping appointment
   - the patient has no overlapping appointment
2. **Row lock**: the doctor row is locked with `select_for_update()`, so two bookings for the same doctor can't run at the same time.
3. **Database constraints**: partial unique constraints allow only one active (PENDING/CONFIRMED) appointment per doctor per slot, and one per patient per slot.

Cancelling or rescheduling never deletes a row:
- A cancelled appointment keeps its reason, who cancelled it and when.
- A reschedule marks the old appointment `RESCHEDULED` and creates a new one that links back to it through `rescheduled_from`.

## Main endpoints

```
POST /api/auth/login/ | refresh/ | logout/ | register/ | forgot-password/ | reset-password/
GET  /api/auth/me/
GET  /api/dashboard/
     /api/departments/            /api/doctors/  (+ /me/, /{id}/slots/?date=, /{id}/dates/, /filters/)
     /api/availability/           /api/patients/ (+ /me/)
     /api/appointments/           (+ /{id}/confirm|complete|no_show|cancel|reschedule/)
     /api/notifications/          (+ /{id}/read/, /read_all/)
     /api/audit-logs/
```
