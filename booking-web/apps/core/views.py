from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import api
from .decorators import login_required

STATUSES = [("PENDING", "Pending"), ("CONFIRMED", "Confirmed"), ("COMPLETED", "Completed"),
            ("CANCELLED", "Cancelled"), ("RESCHEDULED", "Rescheduled"), ("NO_SHOW", "No show")]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def safe_next(request, fallback):
    nxt = request.POST.get("next") or request.GET.get("next")
    return nxt if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}) else fallback


def home(request):
    return redirect(request.jwt_user.dashboard if request.jwt_user else "/login/")


# ---- JSON endpoints for in-page JS (browser never talks to the API directly) ----

def _json(fn):
    try:
        return JsonResponse(fn())
    except api.APIError as e:
        return JsonResponse({"detail": e.message}, status=e.status if e.status < 500 else 502)


@login_required
def notifications_json(request):
    def load():
        data = api.get(request, "/notifications/")
        return {"results": data["results"][:8], "unread_count": data["unread_count"]}
    return _json(load)


@login_required
@require_POST
def notification_read(request, pk):
    return _json(lambda: api.post(request, f"/notifications/{pk}/read/"))


@login_required
@require_POST
def notifications_read_all(request):
    return _json(lambda: api.post(request, "/notifications/read_all/"))


@login_required
def doctor_slots_json(request, pk):
    return _json(lambda: api.get(request, f"/doctors/{pk}/slots/", {"date": request.GET.get("date", "")}))


# ---- Analytics (Metabase static embed; booking-api signs the URL) ----

def analytics_page(request):
    try:
        embed, error = api.get(request, "/analytics/embed/"), None
    except api.APIError as e:
        embed, error = None, e.message
    return render(request, "analytics/dashboard.html", {"embed": embed, "error": error})


# ---- Error pages ----

def _error(code):
    def view(request, exception=None):
        return render(request, f"errors/{code}.html", status=code)
    return view


bad_request, permission_denied, page_not_found, server_error = (_error(c) for c in (400, 403, 404, 500))


# ---- Shared appointment handling (patient / doctor / admin) ----

ACTION_LABELS = {"confirm": "confirmed", "complete": "marked as completed", "cancel": "cancelled",
                 "no_show": "marked as no-show"}


def appointment_action(request, pk, action, detail_url):
    if action not in ACTION_LABELS:
        raise Http404
    payload = {"reason": request.POST.get("reason", ""), "doctor_notes": request.POST.get("doctor_notes", "")}
    try:
        appt = api.post(request, f"/appointments/{pk}/{action}/", payload)
        messages.success(request, f"Appointment {appt['appointment_number']} {ACTION_LABELS[action]}.")
    except api.APIError as e:
        messages.error(request, e.message)
    return redirect(safe_next(request, detail_url))


def reschedule(request, pk, detail_url_prefix):
    appt = api.get(request, f"/appointments/{pk}/")
    errors = {}
    if request.method == "POST":
        try:
            new = api.post(request, f"/appointments/{pk}/reschedule/",
                           {k: request.POST.get(k, "") for k in ("appointment_date", "start_time", "reason")})
            messages.success(request, f"Rescheduled. New appointment number: {new['appointment_number']}.")
            return redirect(f"{detail_url_prefix}{new['id']}/")
        except api.APIError as e:
            errors = e.errors
            messages.error(request, e.message)
    dates = api.get(request, f"/doctors/{appt['doctor']['id']}/dates/", {"days": 21})
    return render(request, "patient/reschedule.html", {
        "appt": appt, "dates": dates, "errors": errors, "form": request.POST,
        "back_url": f"{detail_url_prefix}{pk}/",
    })


def availability_page(request, doctor_id=None, extra=None):
    """Doctor's own schedule (doctor_id=None) or an admin managing any doctor's schedule."""
    if request.method == "POST":
        op, sid = request.POST.get("op"), request.POST.get("id")
        fields = {k: request.POST.get(k) for k in ("start_time", "end_time", "slot_duration")}
        try:
            if op == "create":
                days = request.POST.getlist("days")
                if not days:
                    raise api.APIError(400, {"detail": "Select at least one day."})
                for day in days:
                    owner = {"doctor": doctor_id} if doctor_id else {}  # doctors: API assigns their own profile
                    api.post(request, "/availability/", {**fields, "day_of_week": day, **owner})
                messages.success(request, f"Schedule added for {len(days)} day(s).")
            elif op == "update":
                api.patch(request, f"/availability/{sid}/", {**fields, "day_of_week": request.POST.get("day_of_week")})
                messages.success(request, "Schedule updated.")
            elif op == "toggle":
                active = request.POST.get("is_active") == "1"
                api.patch(request, f"/availability/{sid}/", {"is_active": active})
                messages.success(request, f"Schedule {'enabled' if active else 'disabled'}.")
            elif op == "delete":
                api.delete(request, f"/availability/{sid}/")
                messages.success(request, "Schedule deleted.")
        except api.APIError as e:
            messages.error(request, e.message)
        return redirect(request.get_full_path())

    items = api.get(request, "/availability/", {"doctor": doctor_id} if doctor_id else None)
    week = [{"value": i, "name": name, "items": [s for s in items if s["day_of_week"] == i]} for i, name in enumerate(DAYS)]
    return render(request, "doctor/availability.html", {"week": week, "days": DAYS, **(extra or {})})
