from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core import api
from apps.core.decorators import role_required
from apps.core.views import appointment_action, reschedule

patient_only = role_required("PATIENT")
PROFILE_FIELDS = ("first_name", "last_name", "phone_number", "date_of_birth", "gender", "blood_group", "address",
                  "city", "emergency_contact_name", "emergency_contact_phone")


@patient_only
def dashboard(request):
    return render(request, "patient/dashboard.html", {"d": api.get(request, "/dashboard/")})


@patient_only
def profile(request):
    errors = {}
    if request.method == "POST":
        data = {k: request.POST.get(k, "") for k in PROFILE_FIELDS}
        data["date_of_birth"] = data["date_of_birth"] or None
        files = api.upload_files(request, "profile_image")
        if files:
            data = {k: v for k, v in data.items() if v is not None}
        try:
            api.patch(request, "/patients/me/", data, files=files)
            messages.success(request, "Profile updated.")
            return redirect("/patient/profile/")
        except api.APIError as e:
            errors = e.errors
            messages.error(request, "Please fix the highlighted fields.")
    return render(request, "patient/profile.html", {
        "p": api.get(request, "/patients/me/"), "errors": errors,
        "genders": [("MALE", "Male"), ("FEMALE", "Female"), ("OTHER", "Other")],
        "blood_groups": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    })


@patient_only
def doctors(request):
    g = request.GET
    params = {k: g.get(k) for k in ("q", "specialization", "department", "city", "min_fee", "max_fee", "available")}
    results, pager = api.paged(request, "/doctors/", params)
    return render(request, "patient/doctors.html", {
        "doctors": results, "pager": pager, "f": params,
        "departments": api.get(request, "/departments/", {"all": 1}),
        "options": api.get(request, "/doctors/filters/"),
    })


@patient_only
def doctor_detail(request, pk):
    return render(request, "patient/doctor_detail.html", {
        "doctor": api.get(request, f"/doctors/{pk}/"),
        "dates": api.get(request, f"/doctors/{pk}/dates/", {"days": 14}),
    })


@patient_only
def book(request, pk):
    doctor = api.get(request, f"/doctors/{pk}/")
    errors = {}
    if request.method == "POST":
        data = {k: request.POST.get(k, "") for k in ("appointment_date", "start_time", "reason", "patient_notes")}
        try:
            appt = api.post(request, "/appointments/", {**data, "doctor": pk})
            return redirect(f"/patient/appointments/{appt['id']}/?booked=1")
        except api.APIError as e:
            errors = e.errors
            messages.error(request, e.message)
    return render(request, "patient/book_appointment.html", {
        "doctor": doctor, "dates": api.get(request, f"/doctors/{pk}/dates/", {"days": 21}),
        "errors": errors, "form": request.POST or {  # prefill from a slot picked on the doctor profile
            "appointment_date": request.GET.get("date", ""), "start_time": request.GET.get("time", "")},
    })


@patient_only
def book_start(request):
    messages.info(request, "Step 1: choose a doctor to book with.")
    return redirect("/patient/doctors/")


TABS = {"upcoming": {"upcoming": 1, "status": "PENDING,CONFIRMED"},
        "past": {"status": "COMPLETED,NO_SHOW"},
        "cancelled": {"status": "CANCELLED,RESCHEDULED"},
        "all": {}}


@patient_only
def appointments(request):
    tab = request.GET.get("tab") if request.GET.get("tab") in TABS else "upcoming"
    results, pager = api.paged(request, "/appointments/", {**TABS[tab], "q": request.GET.get("q")})
    return render(request, "patient/appointments.html", {"appointments": results, "pager": pager, "tab": tab,
                                                         "tabs": TABS})


@patient_only
def appointment_detail(request, pk):
    return render(request, "patient/appointment_detail.html", {
        "appt": api.get(request, f"/appointments/{pk}/"), "booked": request.GET.get("booked") == "1",
        "base": "/patient/appointments/",
    })


@patient_only
@require_POST
def cancel(request, pk):
    return appointment_action(request, pk, "cancel", f"/patient/appointments/{pk}/")


@patient_only
def reschedule_view(request, pk):
    return reschedule(request, pk, "/patient/appointments/")
