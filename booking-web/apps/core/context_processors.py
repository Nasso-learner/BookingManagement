from django.conf import settings

NAV = {
    "PATIENT": [
        ("Dashboard", "/patient/", "bi-grid-1x2"),
        ("Find Doctors", "/patient/doctors/", "bi-search-heart"),
        ("My Appointments", "/patient/appointments/", "bi-calendar2-check"),
        ("My Profile", "/patient/profile/", "bi-person-circle"),
    ],
    "DOCTOR": [
        ("Dashboard", "/doctor/", "bi-grid-1x2"),
        ("Appointments", "/doctor/appointments/", "bi-calendar2-check"),
        ("Analytics", "/doctor/analytics/", "bi-bar-chart-line"),
        ("Reports", "/reports/", "bi-graph-up-arrow"),
        ("Availability", "/doctor/availability/", "bi-clock-history"),
        ("My Patients", "/doctor/patients/", "bi-people"),
        ("My Profile", "/doctor/profile/", "bi-person-badge"),
    ],
    "ADMIN": [
        ("Dashboard", "/admin/", "bi-grid-1x2"),
        ("Analytics", "/admin/analytics/", "bi-bar-chart-line"),
        ("Reports", "/reports/", "bi-graph-up-arrow"),
        ("Doctors", "/admin/doctors/", "bi-heart-pulse"),
        ("Patients", "/admin/patients/", "bi-people"),
        ("Departments", "/admin/departments/", "bi-diagram-3"),
        ("Appointments", "/admin/appointments/", "bi-calendar2-check"),
        ("Schedules", "/admin/schedules/", "bi-calendar-week"),
        ("Audit Logs", "/admin/audit-logs/", "bi-shield-check"),
    ],
}


def ui(request):
    me = getattr(request, "jwt_user", None)
    nav = []
    if me:
        for label, url, icon in NAV.get(me.role, []):
            active = request.path == url or (url != me.dashboard and request.path.startswith(url))
            nav.append({"label": label, "url": url, "icon": icon, "active": active})
    return {"me": me, "nav": nav, "CURRENCY": settings.CURRENCY_SYMBOL}
