from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core import api
from apps.core.decorators import role_required
from apps.core.views import STATUSES, analytics_page, appointment_action, availability_page, reschedule

admin_only = role_required("ADMIN")
AUDIT_ACTIONS = ["LOGIN", "LOGOUT", "USER_REGISTERED", "PASSWORD_RESET", "APPOINTMENT_CREATED", "APPOINTMENT_CONFIRMED",
                 "APPOINTMENT_CANCELLED", "APPOINTMENT_RESCHEDULED", "APPOINTMENT_COMPLETED", "APPOINTMENT_NO_SHOW",
                 "DOCTOR_CREATED", "DOCTOR_UPDATED", "PATIENT_UPDATED", "SCHEDULE_CREATED", "SCHEDULE_UPDATED",
                 "SCHEDULE_DELETED"]
DOCTOR_FIELDS = ("first_name", "last_name", "email", "phone_number", "specialization", "department", "qualification",
                 "experience_years", "consultation_fee", "license_number", "city", "consultation_duration", "bio")


@admin_only
def dashboard(request):
    return render(request, "admin/dashboard.html", {"d": api.get(request, "/dashboard/")})


# ---- Doctors ----

@admin_only
def doctors(request):
    params = {k: request.GET.get(k) for k in ("q", "department", "is_active")}
    results, pager = api.paged(request, "/doctors/", params)
    return render(request, "admin/doctors.html", {"doctors": results, "pager": pager, "f": params,
                                                  "departments": api.get(request, "/departments/", {"all": 1})})


@admin_only
def doctor_form(request, pk=None):
    doctor = api.get(request, f"/doctors/{pk}/") if pk else {}
    errors = {}
    if request.method == "POST":
        data = {k: request.POST.get(k, "") for k in DOCTOR_FIELDS}
        data["department"] = data["department"] or None
        data["is_active"] = bool(request.POST.get("is_active"))
        data["is_available"] = bool(request.POST.get("is_available"))
        if request.POST.get("password"):
            data["password"] = request.POST["password"]
        try:
            files = api.upload_files(request, "profile_image")
            if files:  # multipart can't carry None/bools
                data = {k: ("true" if v is True else "false" if v is False else v) for k, v in data.items() if v is not None}
            if pk:
                api.patch(request, f"/doctors/{pk}/", data, files=files)
                messages.success(request, "Doctor updated.")
            else:
                created = api.post(request, "/doctors/", data, files=files)
                messages.success(request, f"Doctor created with code {created['doctor_code']}.")
            return redirect("/admin/doctors/")
        except api.APIError as e:
            errors = e.errors
            messages.error(request, "Please fix the highlighted fields.")
        doctor = {**doctor, **request.POST.dict(), "is_active": data["is_active"], "is_available": data["is_available"]}
    return render(request, "admin/doctor_form.html", {
        "doctor": doctor, "pk": pk, "errors": errors, "departments": api.get(request, "/departments/", {"all": 1}),
    })


@admin_only
@require_POST
def doctor_toggle(request, pk):
    active = request.POST.get("is_active") == "1"
    api.patch(request, f"/doctors/{pk}/", {"is_active": active})
    messages.success(request, "Doctor approved/activated." if active else "Doctor deactivated.")
    return redirect(request.POST.get("next") or "/admin/doctors/")


# ---- Patients ----

@admin_only
def patients(request):
    params = {k: request.GET.get(k) for k in ("q", "is_active")}
    results, pager = api.paged(request, "/patients/", params)
    return render(request, "admin/patients.html", {"patients": results, "pager": pager, "f": params})


@admin_only
@require_POST
def patient_toggle(request, pk):
    active = request.POST.get("is_active") == "1"
    api.patch(request, f"/patients/{pk}/", {"is_active": active})
    messages.success(request, f"Patient {'activated' if active else 'deactivated'}.")
    return redirect("/admin/patients/")


# ---- Departments ----

@admin_only
def departments(request):
    if request.method == "POST":
        op, pk = request.POST.get("op"), request.POST.get("id")
        data = {k: request.POST.get(k, "") for k in ("name", "code", "description")}
        data["is_active"] = bool(request.POST.get("is_active"))
        try:
            if op == "delete":
                api.delete(request, f"/departments/{pk}/")
                messages.success(request, "Department deleted.")
            elif pk:
                api.patch(request, f"/departments/{pk}/", data)
                messages.success(request, "Department updated.")
            else:
                api.post(request, "/departments/", data)
                messages.success(request, "Department added.")
        except api.APIError as e:
            messages.error(request, e.message)
        return redirect("/admin/departments/")
    results, pager = api.paged(request, "/departments/", {"q": request.GET.get("q")})
    return render(request, "admin/departments.html", {"departments": results, "pager": pager})


# ---- Appointments ----

@admin_only
def appointments(request):
    params = {k: request.GET.get(k) for k in ("q", "status", "date", "doctor", "patient")}
    results, pager = api.paged(request, "/appointments/", params)
    return render(request, "admin/appointments.html", {"appointments": results, "pager": pager, "f": params,
                                                       "statuses": STATUSES})


@admin_only
def appointment_detail(request, pk):
    return render(request, "admin/appointment_detail.html",
                  {"appt": api.get(request, f"/appointments/{pk}/"), "base": "/admin/appointments/"})


@admin_only
@require_POST
def appointment_action_view(request, pk, name):
    return appointment_action(request, pk, name, f"/admin/appointments/{pk}/")


@admin_only
def appointment_reschedule(request, pk):
    return reschedule(request, pk, "/admin/appointments/")


# ---- Schedules / audit ----

@admin_only
def schedules(request):
    doctor_id = request.GET.get("doctor")
    doctors_list = api.get(request, "/doctors/", {"is_active": 1, "page_size": 100})["results"]
    extra = {"doctors": doctors_list, "selected_doctor": doctor_id, "admin_mode": True}
    if not doctor_id:
        return render(request, "doctor/availability.html", {**extra, "week": None})
    return availability_page(request, doctor_id=doctor_id, extra=extra)


@admin_only
def audit_logs(request):
    params = {k: request.GET.get(k) for k in ("q", "action")}
    results, pager = api.paged(request, "/audit-logs/", params)
    return render(request, "admin/audit_logs.html", {"logs": results, "pager": pager, "f": params,
                                                     "actions": AUDIT_ACTIONS})


@admin_only
def analytics(request):
    return analytics_page(request)
