import json

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core import api
from apps.core.decorators import role_required

from . import charts

admin_only = role_required("ADMIN")
staff_only = role_required("ADMIN", "DOCTOR")
SOURCES = [("CLICKHOUSE", "ClickHouse (high performance)"), ("POSTGRES", "PostgreSQL")]
FIELDS = ("title", "description", "source", "sql", "chart_type", "x_column", "y_columns", "series_column")


@staff_only
def report_list(request):
    return render(request, "reports/list.html", {"reports": api.get(request, "/reports/"), "chart_types": dict(charts.CHART_TYPES)})


@staff_only
def report_view(request, pk):
    report = api.get(request, f"/reports/{pk}/")
    chart = request.GET.get("chart") if request.GET.get("chart") in dict(charts.CHART_TYPES) else report["chart_type"]
    result, output, error = None, None, None
    try:
        result = api.get(request, f"/reports/{pk}/run/")
        output = charts.build(report, result, chart)
    except (api.APIError, charts.ChartError) as e:
        error = getattr(e, "message", None) or str(e)
    return render(request, "reports/view.html", {"report": report, "result": result, "output": output, "error": error,
                                                 "chart": chart, "chart_types": charts.CHART_TYPES})


@admin_only
def report_form(request, pk=None):
    report = api.get(request, f"/reports/{pk}/") if pk else {"chart_type": "BAR", "is_active": True, "source": "CLICKHOUSE"}
    errors = {}
    if request.method == "POST":
        data = {k: request.POST.get(k, "") for k in FIELDS}
        data.update(doctor_access=bool(request.POST.get("doctor_access")), is_active=bool(request.POST.get("is_active")))
        try:
            saved = api.patch(request, f"/reports/{pk}/", data) if pk else api.post(request, "/reports/", data)
            messages.success(request, f"Report “{saved['title']}” saved.")
            return redirect(f"/reports/{saved['id']}/")
        except api.APIError as e:
            errors = e.errors
            messages.error(request, e.message)
            report = {**report, **data}
    doctors = api.get(request, "/doctors/", {"is_active": 1, "page_size": 100})["results"]
    return render(request, "reports/form.html", {"report": report, "pk": pk, "errors": errors, "doctors": doctors,
                                                 "chart_types": charts.CHART_TYPES, "sources": SOURCES})


@admin_only
@require_POST
def report_delete(request, pk):
    api.delete(request, f"/reports/{pk}/")
    messages.success(request, "Report deleted.")
    return redirect("/reports/")


@admin_only
@require_POST
def report_preview(request):
    """Builder live preview: run unsaved SQL (optionally as a doctor) and return figure + rows."""
    cfg = json.loads(request.body or "{}")
    try:
        result = api.post(request, "/reports/preview/", {"sql": cfg.get("sql", ""), "doctor_id": cfg.get("doctor_id") or None,
                                                         "source": cfg.get("source") or "POSTGRES"})
        return JsonResponse({**result, "output": charts.build(cfg, result)})
    except (api.APIError, charts.ChartError) as e:
        return JsonResponse({"error": getattr(e, "message", None) or str(e)}, status=400)
