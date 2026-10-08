from django.http import JsonResponse
from django.shortcuts import render

from apps.core import api
from apps.core.decorators import role_required

staff_only = role_required("ADMIN", "DOCTOR")
FILTER_KEYS = ("date_from", "date_to", "department", "doctor", "status")


@staff_only
def dashboard(request):
    return render(request, "insights/dashboard.html")


@staff_only
def data(request):
    """Same-origin JSON for the dashboard JS. booking-api re-checks the role and pins doctors to themselves."""
    params = {k: request.GET[k] for k in FILTER_KEYS if request.GET.get(k)}
    try:
        return JsonResponse(api.get(request, "/insights/clinic/", params))
    except api.APIError as e:
        return JsonResponse({"detail": e.message, "errors": e.errors}, status=e.status if e.status < 500 else 503)
