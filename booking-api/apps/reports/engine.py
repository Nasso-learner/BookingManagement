"""Runs report SQL safely against PostgreSQL or ClickHouse.

Layers of protection (both sources):
1. validate_sql(): exactly one SELECT/WITH statement.
2. A dedicated read-only login that can only see the reporting views/tables
   (Postgres: report_reader on `reporting` schema; ClickHouse: report_reader on `reporting` db, readonly=2 profile).
3. Server-side time limit + row cap (Postgres: READ ONLY txn + statement_timeout; ClickHouse: settings profile).
4. :doctor_id is always a bound parameter (never string-formatted); doctors get their own id forced in.
"""
import re
import time
from functools import lru_cache

from django.conf import settings
from django.db import DatabaseError, connections, transaction
from rest_framework.exceptions import ValidationError

_PLACEHOLDER = re.compile(r"(?<!:):doctor_id\b")
POSTGRES, CLICKHOUSE = "POSTGRES", "CLICKHOUSE"


def validate_sql(sql, doctor_access=False):
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise ValidationError({"sql": "SQL is required."})
    if ";" in sql:
        raise ValidationError({"sql": "Only one statement is allowed (remove extra ';')."})
    if not re.match(r"(?is)^(select|with)\b", sql):
        raise ValidationError({"sql": "Only SELECT queries are allowed (may start with WITH)."})
    if doctor_access and not _PLACEHOLDER.search(sql):
        raise ValidationError({"sql": "Reports visible to doctors must filter with :doctor_id, e.g. "
                                      "WHERE (:doctor_id IS NULL OR doctor_id = :doctor_id)"})
    return sql


def run(sql, doctor_id=None, source=POSTGRES):
    """Returns {columns, rows, truncated, elapsed_ms, source}. doctor_id=None means unscoped (admin)."""
    sql = validate_sql(sql)
    started = time.perf_counter()
    columns, rows = (_run_clickhouse if source == CLICKHOUSE else _run_postgres)(sql, doctor_id)
    limit = settings.REPORTS_MAX_ROWS
    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:limit]],
        "truncated": len(rows) > limit,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
        "source": source,
    }


def _run_postgres(sql, doctor_id):
    alias = settings.REPORTS_DB_ALIAS
    query = _PLACEHOLDER.sub("%(doctor_id)s", sql.replace("%", "%%"))
    conn = connections[alias]
    try:
        outermost = not conn.in_atomic_block
        with transaction.atomic(using=alias), conn.cursor() as cur:
            if outermost:  # can only be set at the start of a transaction
                cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(f"SET LOCAL statement_timeout = {int(settings.REPORTS_TIMEOUT_MS)}")
            cur.execute(query, {"doctor_id": doctor_id})
            return [c[0] for c in cur.description], cur.fetchmany(settings.REPORTS_MAX_ROWS + 1)
    except DatabaseError as e:
        raise ValidationError({"sql": str(e).strip().splitlines()[0]})


@lru_cache(maxsize=1)
def _clickhouse_client():
    import clickhouse_connect  # imported lazily: only needed when ClickHouse reports exist

    return clickhouse_connect.get_client(
        host=settings.CLICKHOUSE_HOST, port=settings.CLICKHOUSE_PORT, secure=settings.CLICKHOUSE_SECURE,
        username=settings.CLICKHOUSE_REPORT_USER, password=settings.CLICKHOUSE_REPORT_PASSWORD,
        database="reporting", autogenerate_session_id=False,  # stateless -> safe to share across threads
    )


def _run_clickhouse(sql, doctor_id):
    if not settings.CLICKHOUSE_HOST:
        raise ValidationError({"source": "ClickHouse is not configured (set CLICKHOUSE_HOST in booking-api/.env)."})
    from clickhouse_connect.driver.exceptions import ClickHouseError

    has_param = bool(_PLACEHOLDER.search(sql))
    query = _PLACEHOLDER.sub("{doctor_id:Nullable(Int64)}", sql)  # server-side bound parameter
    try:
        result = _clickhouse_client().query(
            query,
            parameters={"doctor_id": doctor_id} if has_param else None,
            settings={"max_execution_time": max(1, settings.REPORTS_TIMEOUT_MS // 1000),
                      "max_result_rows": settings.REPORTS_MAX_ROWS + 1, "result_overflow_mode": "break"},
        )
    except ClickHouseError as e:
        message = str(e).strip().splitlines()[0]
        raise ValidationError({"sql": re.sub(r"^.*?Code: ", "Code: ", message)[:400]})
    return list(result.column_names), result.result_rows
