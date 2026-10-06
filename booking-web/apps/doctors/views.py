from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core import api
from apps.core.decorators import role_required
from apps.core.views import STATUSES, analytics_page, appointment_action, availability_page

doctor_only = role_required("DOCTOR")
PROFILE_FIELDS = ("first_name", "last_name", "phone_number", "specialization", "qualification", "experience_years",
                  "consultation_fee", "consultation_duration", "city", "bio")


@doctor_only
def dashboard(request):
    return render(request, "doctor/dashboard.html", {"d": api.get(request, "/dashboard/")})


@doctor_only
def profile(request):
    errors = {}
    if request.method == "POST":
        data = {k: request.POST.get(k, "") for k in PROFILE_FIELDS}
        data["is_available"] = "true" if request.POST.get("is_available") else "false"
        try:
            api.patch(request, "/doctors/me/", data, files=api.upload_files(request, "profile_image"))
            messages.success(request, "Profile updated.")
            return redirect("/doctor/profile/")
        except api.APIError as e:
            errors = e.errors
            messages.error(request, "Please fix the highlighted fields.")
    return render(request, "doctor/profile.html", {"doc": api.get(request, "/doctors/me/"), "errors": errors})


@doctor_only
def availability(request):
    return availability_page(request)


@doctor_only
def appointments(request):
    g = request.GET
    params = {k: g.get(k) for k in ("status", "date", "q")}
    if g.get("view", "upcoming") == "upcoming" and not params["date"]:
        params["upcoming"] = 1
    results, pager = api.paged(request, "/appointments/", params)
    return render(request, "doctor/appointments.html", {"appointments": results, "pager": pager, "f": params,
                                                        "view": g.get("view", "upcoming"), "statuses": STATUSES})


@doctor_only
def appointment_detail(request, pk):
    return render(request, "doctor/appointment_detail.html",
                  {"appt": api.get(request, f"/appointments/{pk}/"), "base": "/doctor/appointments/"})


@doctor_only
@require_POST
def action(request, pk, name):
    return appointment_action(request, pk, name, f"/doctor/appointments/{pk}/")


@doctor_only
def patients(request):
    results, pager = api.paged(request, "/patients/", {"q": request.GET.get("q")})
    return render(request, "doctor/patients.html", {"patients": results, "pager": pager})


@doctor_only
def analytics(request):
    return analytics_page(request)
