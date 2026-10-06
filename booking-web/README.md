# booking-web

The MediBook web UI, built with Django templates, Bootstrap 5 and vanilla JavaScript. It has **no models, no database and no migrations**. All data comes from **booking-api** over HTTP.

## Run locally

Start booking-api first, then:

```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env          # JWT_SIGNING_KEY must match booking-api's
python manage.py runserver 8001
```

Docker: `docker compose up --build` serves the UI on port 8001. It expects the API at `host.docker.internal:8000`.

## How authentication works

1. The login form posts to this app. The view calls `POST /api/auth/login/`.
2. The returned access and refresh tokens are stored in **HttpOnly cookies** (`access_token`, `refresh_token`):
   - `SameSite=Lax`
   - `Secure` whenever `DEBUG=0` or `COOKIE_SECURE=1`
   - Tokens are never put in `localStorage`.
3. `apps/core/middleware.py` runs on every request:
   - It verifies the access token with the shared `JWT_SIGNING_KEY`.
   - If the access token has expired, it refreshes it through the API and sets a new cookie.
   - It exposes `request.jwt_user`.
4. If the API returns 401, the user is sent back to the login page and the cookies are cleared.
5. Logout blacklists the refresh token in the API and clears both cookies.
6. `@login_required` and `@role_required("PATIENT" | "DOCTOR" | "ADMIN")` in `apps/core/decorators.py` protect the views. The wrong role gets a 403 page.

The browser never calls the API directly. In-page JavaScript (slot loading, notifications) goes through small JSON views under `/ajax/`.

## Layout

| Path | What's there |
|---|---|
| `apps/core` | API client, JWT cookie middleware, decorators, context processor, template filters, AJAX and error views, appointment/schedule handlers shared by doctor and admin |
| `apps/accounts` | `/login/`, `/register/`, `/forgot-password/`, `/reset-password/`, `/logout/` |
| `apps/patients` | `/patient/…`: dashboard, doctor search and profile, 6-step booking, appointments, reschedule, cancel, profile |
| `apps/doctors` | `/doctor/…`: dashboard, appointments (confirm/complete/cancel/no-show), availability, patients, profile |
| `apps/administration` | `/admin/…`: dashboard, doctors (create/approve/edit), patients, departments, appointments, schedules, audit logs |
| `apps/reports` | `/reports/`: report list, viewer with a "view as" chart switch, and the admin SQL builder with live preview. `charts.py` builds the Plotly figures |
| `templates/` | `base/`, `auth/`, `patient/`, `doctor/`, `admin/`, `errors/`, plus shared `partials/` |
| `static/` | `css/` (design tokens in `style.css`), `js/` |

Each app keeps its routes in its own `urls.py`.
