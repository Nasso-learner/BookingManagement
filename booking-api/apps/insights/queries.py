"""ClickHouse queries behind the Insights dashboard.

Every filter is a server-side bound parameter ({name:Type}); nothing user-supplied is formatted into SQL.
All queries read the pre-joined `reporting.*` tables as the read-only `report_reader` user.
"""

# Non-date filters shared by every visual. NULL = "all".
SCOPE = """({doctor_id:Nullable(Int64)} IS NULL OR doctor_id = {doctor_id:Nullable(Int64)})
  AND ({department:Nullable(String)} IS NULL OR department_name = {department:Nullable(String)})
  AND ({status:Nullable(String)} IS NULL OR status = {status:Nullable(String)})"""
PERIOD = "appointment_date BETWEEN {date_from:Date} AND {date_to:Date}"
WHERE = f"WHERE {PERIOD} AND {SCOPE}"

BUCKET = {
    "day": "appointment_date",
    "week": "toMonday(appointment_date)",
    "month": "toStartOfMonth(appointment_date)",
}

KPIS = f"""
SELECT
    countIf(cur)                                                    AS total,
    countIf(cur AND status = 'COMPLETED')                           AS completed,
    countIf(cur AND status = 'CANCELLED')                           AS cancelled,
    countIf(cur AND status = 'NO_SHOW')                             AS no_show,
    countIf(cur AND status IN ('PENDING', 'CONFIRMED'))             AS open,
    sumIf(consultation_fee, cur AND status = 'COMPLETED')           AS revenue,
    uniqExactIf(patient_id, cur)                                    AS patients,
    avgIf(lead_days, cur AND lead_days >= 0)                        AS avg_lead_days,
    countIf(NOT cur)                                                AS p_total,
    countIf(NOT cur AND status = 'COMPLETED')                       AS p_completed,
    countIf(NOT cur AND status = 'CANCELLED')                       AS p_cancelled,
    countIf(NOT cur AND status = 'NO_SHOW')                         AS p_no_show,
    sumIf(consultation_fee, NOT cur AND status = 'COMPLETED')       AS p_revenue,
    uniqExactIf(patient_id, NOT cur)                                AS p_patients,
    avgIf(lead_days, NOT cur AND lead_days >= 0)                    AS p_avg_lead_days
FROM (
    SELECT *, appointment_date >= {{date_from:Date}} AS cur
    FROM reporting.appointments
    WHERE appointment_date BETWEEN {{prev_from:Date}} AND {{date_to:Date}} AND {SCOPE}
)"""

TREND = """
SELECT {bucket} AS bucket, status, count() AS n,
       sumIf(consultation_fee, status = 'COMPLETED') AS revenue
FROM reporting.appointments
""" + WHERE + " GROUP BY bucket, status ORDER BY bucket"

STATUS_MIX = f"SELECT status, count() AS n FROM reporting.appointments {WHERE} GROUP BY status ORDER BY n DESC"

DEPARTMENTS = f"""
SELECT department_name, count() AS total, countIf(status = 'COMPLETED') AS completed,
       sumIf(consultation_fee, status = 'COMPLETED') AS revenue
FROM reporting.appointments {WHERE}
GROUP BY department_name ORDER BY total DESC"""

DOCTORS = f"""
SELECT doctor_id, any(doctor_name) AS doctor, any(department_name) AS department,  -- aliases must not shadow filtered columns
       count() AS total, countIf(status = 'COMPLETED') AS completed, countIf(status = 'CANCELLED') AS cancelled,
       countIf(status = 'NO_SHOW') AS no_show,
       round(100 * countIf(status = 'NO_SHOW') / nullIf(countIf(status IN ('COMPLETED', 'NO_SHOW')), 0), 1) AS no_show_pct,
       sumIf(consultation_fee, status = 'COMPLETED') AS revenue
FROM reporting.appointments {WHERE}
GROUP BY doctor_id ORDER BY total DESC LIMIT 25"""

HEATMAP = f"""
SELECT weekday_num, start_hour, count() AS n
FROM reporting.appointments {WHERE}
GROUP BY weekday_num, start_hour"""

LEAD_TIME = f"""
SELECT multiIf(lead_days = 0, 0, lead_days <= 3, 1, lead_days <= 7, 2, lead_days <= 14, 3, 4) AS bucket, count() AS n
FROM reporting.appointments {WHERE} AND lead_days >= 0
GROUP BY bucket ORDER BY bucket"""

SOURCE_MIX = f"SELECT booking_source, count() AS n FROM reporting.appointments {WHERE} GROUP BY booking_source ORDER BY n DESC"

GENDER_MIX = f"""
SELECT ifNull(patient_gender, 'UNKNOWN') AS gender, uniqExact(patient_id) AS n
FROM reporting.appointments {WHERE} GROUP BY gender ORDER BY n DESC"""

# Forward-looking: open bookings vs published slots over the next 14 days (not tied to the date filter).
UTILISATION = """
SELECT c.doctor_id AS doctor_id, c.doctor_name AS doctor_name, c.weekly_slots * 2 AS capacity, count(a.id) AS booked,
       round(100 * count(a.id) / nullIf(c.weekly_slots * 2, 0), 1) AS pct
FROM reporting.doctor_capacity AS c
LEFT JOIN (
    SELECT id, doctor_id FROM reporting.appointments
    WHERE status IN ('PENDING', 'CONFIRMED') AND appointment_date BETWEEN today() AND today() + 13
) AS a ON a.doctor_id = c.doctor_id
WHERE c.doctor_active AND c.weekly_slots > 0
  AND ({doctor_id:Nullable(Int64)} IS NULL OR c.doctor_id = {doctor_id:Nullable(Int64)})
  AND ({department:Nullable(String)} IS NULL OR c.department_name = {department:Nullable(String)})
GROUP BY c.doctor_id, c.doctor_name, c.weekly_slots
ORDER BY pct DESC LIMIT 15"""

DEPARTMENT_OPTIONS = "SELECT DISTINCT department_name FROM reporting.doctor_capacity ORDER BY department_name"
DOCTOR_OPTIONS = """SELECT doctor_id, doctor_name FROM reporting.doctor_capacity
WHERE doctor_active ORDER BY doctor_name"""
