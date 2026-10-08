"""Insights: one request -> every dashboard visual, computed in ClickHouse in parallel and cached briefly."""
import hashlib
import json
import math
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsAdminOrDoctor
from apps.reports.engine import _clickhouse_client

from . import queries as q

STATUSES = ["COMPLETED", "CONFIRMED", "PENDING", "NO_SHOW", "RESCHEDULED", "CANCELLED"]  # stack order
LEAD_BUCKETS = ["Same day", "1–3 days", "4–7 days", "8–14 days", "15+ days"]
CACHE_SECONDS = 30  # matches the ClickHouse reporting refresh interval
MAX_SPAN_DAYS = 3 * 366


class InsightsUnavailable(APIException):
    status_code = 503
    default_detail = "Insights needs ClickHouse. Start the analytics stack and set CLICKHOUSE_HOST in booking-api/.env."


class Filters(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    department = serializers.CharField(required=False, allow_blank=True, max_length=100)
    doctor = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(choices=STATUSES, required=False, allow_blank=True)

    def validate(self, attrs):
        today = timezone.localdate()
        attrs["date_to"] = attrs.get("date_to") or today
        attrs["date_from"] = attrs.get("date_from") or attrs["date_to"] - timedelta(days=89)
        if attrs["date_from"] > attrs["date_to"]:
            raise ValidationError({"date_from": "Start date must be on or before the end date."})
        if (attrs["date_to"] - attrs["date_from"]).days > MAX_SPAN_DAYS:
            raise ValidationError({"date_from": "Date range can be at most 3 years."})
        return attrs


def _granularity(d_from: date, d_to: date):
    span = (d_to - d_from).days
    return "day" if span <= 45 else "week" if span <= 400 else "month"  # keeps bars readable (<= ~58 buckets)


def _buckets(d_from, d_to, grain):
    if grain == "day":
        start, step = d_from, lambda d: d + timedelta(days=1)
    elif grain == "week":
        start, step = d_from - timedelta(days=d_from.weekday()), lambda d: d + timedelta(days=7)
    else:
        start = d_from.replace(day=1)
        step = lambda d: (d.replace(day=28) + timedelta(days=4)).replace(day=1)  # noqa: E731
    out, cur = [], start
    while cur <= d_to:
        out.append(cur)
        cur = step(cur)
    return out


def _run_all(params, grain, is_admin):
    named = {
        "kpis": q.KPIS, "trend": q.TREND.replace("{bucket}", q.BUCKET[grain]), "status_mix": q.STATUS_MIX,
        "departments": q.DEPARTMENTS, "heatmap": q.HEATMAP, "lead_time": q.LEAD_TIME, "source_mix": q.SOURCE_MIX,
        "gender_mix": q.GENDER_MIX, "utilisation": q.UTILISATION, "department_options": q.DEPARTMENT_OPTIONS,
    }
    if is_admin:
        named.update(doctors=q.DOCTORS, doctor_options=q.DOCTOR_OPTIONS)
    client = _clickhouse_client()
    ch_settings = {"max_execution_time": max(1, settings.REPORTS_TIMEOUT_MS // 1000)}

    def run(item):
        name, sql = item
        res = client.query(sql, parameters=params, settings=ch_settings)
        return name, [dict(zip(res.column_names, row)) for row in res.result_rows]

    with ThreadPoolExecutor(max_workers=6) as pool:  # independent queries -> run concurrently
        return dict(pool.map(run, named.items()))


def _num(v):
    """Decimal -> float, NaN (avg of no rows) -> None, ints untouched."""
    if v is None or isinstance(v, int):
        return v
    v = float(v)
    return None if math.isnan(v) else v


def _shape(raw, f, grain):
    """Turn query rows into chart-ready structures (aligned buckets, fixed status order)."""
    buckets = _buckets(f["date_from"], f["date_to"], grain)
    index = {b: i for i, b in enumerate(buckets)}
    by_status = {s: [0] * len(buckets) for s in STATUSES}
    revenue = [0.0] * len(buckets)
    for r in raw["trend"]:
        i = index.get(r["bucket"])
        if i is None:
            continue
        if r["status"] in by_status:
            by_status[r["status"]][i] = r["n"]
        revenue[i] += float(r["revenue"] or 0)
    lead = {r["bucket"]: r["n"] for r in raw["lead_time"]}
    k = raw["kpis"][0] if raw["kpis"] else {}
    return {
        "kpis": {key: _num(v) for key, v in k.items()},
        "trend": {"buckets": buckets, "series": {s: v for s, v in by_status.items() if any(v)}, "revenue": revenue},
        "status_mix": raw["status_mix"],
        "departments": raw["departments"],
        "doctors": raw.get("doctors"),
        "heatmap": [[r["start_hour"], r["weekday_num"] - 1, r["n"]] for r in raw["heatmap"]],
        "lead_time": [{"bucket": label, "n": lead.get(i, 0)} for i, label in enumerate(LEAD_BUCKETS)],
        "source_mix": raw["source_mix"],
        "gender_mix": raw["gender_mix"],
        "utilisation": raw["utilisation"],
        "options": {
            "departments": [r["department_name"] for r in raw["department_options"]],
            "doctors": raw.get("doctor_options"),
            "statuses": STATUSES,
        },
    }


@api_view(["GET"])
@permission_classes([IsAdminOrDoctor])
def clinic(request):
    if not settings.CLICKHOUSE_HOST:
        raise InsightsUnavailable()
    s = Filters(data=request.query_params)
    s.is_valid(raise_exception=True)
    f = s.validated_data
    is_admin = request.user.role == Role.ADMIN
    doctor_id = f.get("doctor") if is_admin else request.user.doctor.pk  # doctors are always pinned to themselves
    span = (f["date_to"] - f["date_from"]).days + 1
    params = {
        "date_from": f["date_from"], "date_to": f["date_to"],
        "prev_from": f["date_from"] - timedelta(days=span), "doctor_id": doctor_id,
        "department": f.get("department") or None, "status": f.get("status") or None,
    }
    grain = _granularity(f["date_from"], f["date_to"])

    key = "insights:" + hashlib.sha256(json.dumps([is_admin, params], default=str, sort_keys=True).encode()).hexdigest()
    payload = cache.get(key)
    cached = payload is not None
    started = time.perf_counter()
    if not cached:
        from clickhouse_connect.driver.exceptions import Error as ClickHouseDriverError

        try:
            payload = _shape(_run_all(params, grain, is_admin), f, grain)
        except ClickHouseDriverError as e:  # ClickHouse down / query error -> clean 503 instead of a 500
            raise InsightsUnavailable(f"ClickHouse error: {str(e).strip().splitlines()[0][:200]}")
        cache.set(key, payload, CACHE_SECONDS)
    return Response({
        **payload,
        "filters": {"date_from": f["date_from"], "date_to": f["date_to"], "department": params["department"],
                    "doctor": doctor_id, "status": params["status"]},
        "scope": "clinic" if is_admin else "doctor",
        "granularity": grain,
        "period_days": span,
        "query_ms": round((time.perf_counter() - started) * 1000),
        "cached": cached,
    })
