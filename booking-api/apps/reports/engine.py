"""Runs report SQL safely.

Layers of protection:
1. validate_sql(): exactly one SELECT/WITH statement.
2. Executed on the `reporting` DB alias (read-only role that can only see the reporting.* views).
3. READ ONLY transaction + statement timeout + row cap.
4. :doctor_id is always a bound parameter (never string-formatted); doctors get their own id forced in.
"""
import re
import time

from django.conf import settings
from django.db import DatabaseError, connections, transaction
from rest_framework.exceptions import ValidationError

_PLACEHOLDER = re.compile(r"(?<!:):doctor_id\b")


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


def run(sql, doctor_id=None):
    """Returns {columns, rows, truncated, elapsed_ms}. doctor_id=None means unscoped (admin)."""
    alias = settings.REPORTS_DB_ALIAS
    query = _PLACEHOLDER.sub("%(doctor_id)s", validate_sql(sql).replace("%", "%%"))
    conn = connections[alias]
    started = time.perf_counter()
    try:
        outermost = not conn.in_atomic_block
        with transaction.atomic(using=alias), conn.cursor() as cur:
            if outermost:  # can only be set at the start of a transaction
                cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(f"SET LOCAL statement_timeout = {int(settings.REPORTS_TIMEOUT_MS)}")
            cur.execute(query, {"doctor_id": doctor_id})
            columns = [c[0] for c in cur.description]
            rows = cur.fetchmany(settings.REPORTS_MAX_ROWS + 1)
    except DatabaseError as e:
        raise ValidationError({"sql": str(e).strip().splitlines()[0]})
    return {
        "columns": columns,
        "rows": [list(r) for r in rows[: settings.REPORTS_MAX_ROWS]],
        "truncated": len(rows) > settings.REPORTS_MAX_ROWS,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    }
