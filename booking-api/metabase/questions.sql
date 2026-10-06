-- Metabase questions (New > SQL query, database "BookingManagement (reporting)").
-- Each block = one saved question. Name it as in the title, pick the chart type shown.
--
-- Every query has an OPTIONAL filter: [[AND doctor_id = {{doctor_id}}]]
--   * In the query editor's variable panel set doctor_id -> Variable type: Number.
--   * Admin dashboard: don't connect the filter -> clinic-wide numbers.
--   * Doctor dashboard: add a "Doctor ID" filter wired to {{doctor_id}} on every card; in the embed
--     settings mark it LOCKED. booking-api fills it with the logged-in doctor's id in the signed token.

-- ============================================================
-- 1. Appointments (last 30 days)                    -> Number
-- ============================================================
SELECT COUNT(*) AS appointments
FROM reporting.appointments
WHERE appointment_date >= CURRENT_DATE - 30
  [[AND doctor_id = {{doctor_id}}]];

-- ============================================================
-- 2. Completion rate % (last 90 days)              -> Number (suffix %)
-- ============================================================
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'COMPLETED')
             / NULLIF(COUNT(*) FILTER (WHERE status IN ('COMPLETED', 'NO_SHOW', 'CANCELLED')), 0), 1) AS completion_rate
FROM reporting.appointments
WHERE appointment_date BETWEEN CURRENT_DATE - 90 AND CURRENT_DATE
  [[AND doctor_id = {{doctor_id}}]];

-- ============================================================
-- 3. No-show rate % (last 90 days)                 -> Number (suffix %)
-- ============================================================
SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'NO_SHOW')
             / NULLIF(COUNT(*) FILTER (WHERE status IN ('COMPLETED', 'NO_SHOW')), 0), 1) AS no_show_rate
FROM reporting.appointments
WHERE appointment_date BETWEEN CURRENT_DATE - 90 AND CURRENT_DATE
  [[AND doctor_id = {{doctor_id}}]];

-- ============================================================
-- 4. Estimated revenue (last 30 days)              -> Number (prefix ₹)
-- ============================================================
SELECT COALESCE(SUM(consultation_fee), 0) AS revenue
FROM reporting.appointments
WHERE status = 'COMPLETED' AND appointment_date >= CURRENT_DATE - 30
  [[AND doctor_id = {{doctor_id}}]];

-- ============================================================
-- 5. Appointments per day by status (90 days)      -> Bar, stacked (x: day, series: status)
-- ============================================================
SELECT appointment_date AS day, status, COUNT(*) AS appointments
FROM reporting.appointments
WHERE appointment_date >= CURRENT_DATE - 90
  [[AND doctor_id = {{doctor_id}}]]
GROUP BY 1, 2
ORDER BY 1;

-- ============================================================
-- 6. Status breakdown (90 days)                    -> Row chart
-- ============================================================
SELECT status, COUNT(*) AS appointments
FROM reporting.appointments
WHERE appointment_date >= CURRENT_DATE - 90
  [[AND doctor_id = {{doctor_id}}]]
GROUP BY 1
ORDER BY 2 DESC;

-- ============================================================
-- 7. Appointments by department (90 days)          -> Row chart   (admin dashboard)
-- ============================================================
SELECT department_name, COUNT(*) AS appointments
FROM reporting.appointments
WHERE appointment_date >= CURRENT_DATE - 90
  [[AND doctor_id = {{doctor_id}}]]
GROUP BY 1
ORDER BY 2 DESC;

-- ============================================================
-- 8. Doctor performance (90 days)                  -> Table   (admin dashboard)
-- ============================================================
SELECT doctor_name,
       department_name,
       COUNT(*)                                          AS total,
       COUNT(*) FILTER (WHERE status = 'COMPLETED')      AS completed,
       COUNT(*) FILTER (WHERE status = 'CANCELLED')      AS cancelled,
       COUNT(*) FILTER (WHERE status = 'NO_SHOW')        AS no_shows,
       ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'NO_SHOW')
             / NULLIF(COUNT(*) FILTER (WHERE status IN ('COMPLETED', 'NO_SHOW')), 0), 1) AS no_show_pct,
       COALESCE(SUM(consultation_fee) FILTER (WHERE status = 'COMPLETED'), 0) AS revenue
FROM reporting.appointments
WHERE appointment_date >= CURRENT_DATE - 90
  [[AND doctor_id = {{doctor_id}}]]
GROUP BY doctor_name, department_name
ORDER BY total DESC;

-- ============================================================
-- 9. Slot utilisation, next 14 days                -> Table or Row chart (x: doctor, y: utilisation_pct)
-- ============================================================
SELECT c.doctor_name,
       c.weekly_slots * 2                                       AS published_slots,
       COUNT(a.id)                                              AS booked_slots,
       ROUND(100.0 * COUNT(a.id) / NULLIF(c.weekly_slots * 2, 0), 1) AS utilisation_pct
FROM reporting.doctor_capacity c
LEFT JOIN reporting.appointments a
       ON a.doctor_id = c.doctor_id
      AND a.status IN ('PENDING', 'CONFIRMED')
      AND a.appointment_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 13
WHERE c.doctor_active
  [[AND c.doctor_id = {{doctor_id}}]]
GROUP BY c.doctor_name, c.weekly_slots
ORDER BY utilisation_pct DESC NULLS LAST;

-- ============================================================
-- 10. Busiest hours (weekday x hour, 90 days)      -> Pivot table (rows: weekday, columns: start_hour)
-- ============================================================
SELECT weekday_num, weekday, start_hour, COUNT(*) AS appointments
FROM reporting.appointments
WHERE appointment_date >= CURRENT_DATE - 90
  [[AND doctor_id = {{doctor_id}}]]
GROUP BY 1, 2, 3
ORDER BY 1, 3;

-- ============================================================
-- 11. Revenue by month                             -> Bar (x: month)
-- ============================================================
SELECT DATE_TRUNC('month', appointment_date)::date AS month,
       SUM(consultation_fee)                       AS revenue,
       COUNT(*)                                    AS completed_visits
FROM reporting.appointments
WHERE status = 'COMPLETED'
  [[AND doctor_id = {{doctor_id}}]]
GROUP BY 1
ORDER BY 1;

-- ============================================================
-- 12. Average booking lead time (days)             -> Number
-- ============================================================
SELECT ROUND(AVG(lead_days), 1) AS avg_lead_days
FROM reporting.appointments
WHERE created_at >= NOW() - INTERVAL '90 days' AND lead_days >= 0  -- ignore back-dated records
  [[AND doctor_id = {{doctor_id}}]];

-- ============================================================
-- 13. New patients per month                       -> Line   (admin dashboard only; no doctor filter)
-- ============================================================
SELECT DATE_TRUNC('month', created_at)::date AS month, COUNT(*) AS new_patients
FROM reporting.patients
GROUP BY 1
ORDER BY 1;

-- ============================================================
-- 14. Security activity per day (30 days)          -> Bar, stacked by action   (admin dashboard only)
-- ============================================================
SELECT created_at::date AS day, action, COUNT(*) AS events
FROM reporting.audit_activity
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 1;
