-- Metabase reporting access for BookingManagement.
-- Run as the postgres superuser (pgAdmin Query Tool or psql). Safe to re-run.
-- Metabase connects as metabase_reader and can ONLY read the views in the `reporting` schema:
-- no password hashes, no tokens, no write access.

CREATE SCHEMA IF NOT EXISTS reporting;

-- One row per appointment, with doctor/department/patient context (no contact details).
CREATE OR REPLACE VIEW reporting.appointments AS
SELECT a.id,
       a.appointment_number,
       a.appointment_date,
       a.start_time,
       a.end_time,
       EXTRACT(ISODOW FROM a.appointment_date)::int      AS weekday_num,   -- 1 = Monday
       TO_CHAR(a.appointment_date, 'Dy')                 AS weekday,
       EXTRACT(HOUR FROM a.start_time)::int              AS start_hour,
       a.status,
       a.booking_source,
       a.rescheduled_from_id IS NOT NULL                 AS is_reschedule,
       a.created_at,
       a.cancelled_at,
       a.completed_at,
       a.appointment_date - (a.created_at AT TIME ZONE 'Asia/Kolkata')::date AS lead_days,
       a.doctor_id,
       d.doctor_code,
       du.first_name || ' ' || du.last_name              AS doctor_name,
       d.specialization,
       d.consultation_fee,
       a.department_id,
       COALESCE(dep.name, 'Unassigned')                  AS department_name,
       a.patient_id,
       p.patient_code,
       NULLIF(p.gender, '')                              AS patient_gender,
       NULLIF(p.city, '')                                AS patient_city
FROM appointments_appointment a
JOIN doctors_doctor d          ON d.id = a.doctor_id
JOIN accounts_user du          ON du.id = d.user_id
JOIN patients_patient p        ON p.id = a.patient_id
LEFT JOIN departments_department dep ON dep.id = a.department_id;

-- Published bookable slots per doctor per week (for utilisation).
CREATE OR REPLACE VIEW reporting.doctor_capacity AS
SELECT d.id                                    AS doctor_id,
       d.doctor_code,
       du.first_name || ' ' || du.last_name    AS doctor_name,
       COALESCE(dep.name, 'Unassigned')        AS department_name,
       du.is_active                            AS doctor_active,
       d.is_available,
       COALESCE(SUM(FLOOR(EXTRACT(EPOCH FROM (av.end_time - av.start_time)) / 60 / av.slot_duration))
                FILTER (WHERE av.is_active), 0)::int AS weekly_slots
FROM doctors_doctor d
JOIN accounts_user du ON du.id = d.user_id
LEFT JOIN departments_department dep ON dep.id = d.department_id
LEFT JOIN doctors_doctoravailability av ON av.doctor_id = d.id
GROUP BY d.id, d.doctor_code, du.first_name, du.last_name, dep.name, du.is_active, d.is_available;

-- Patient registrations (no names or contact details).
CREATE OR REPLACE VIEW reporting.patients AS
SELECT p.id AS patient_id, p.patient_code, NULLIF(p.gender, '') AS gender, NULLIF(p.blood_group, '') AS blood_group,
       NULLIF(p.city, '') AS city, u.is_active, p.created_at
FROM patients_patient p
JOIN accounts_user u ON u.id = p.user_id;

-- Audit activity (who did what, when) for the admin security panel.
CREATE OR REPLACE VIEW reporting.audit_activity AS
SELECT l.id, l.action, l.model_name, l.created_at, u.role AS user_role, u.email AS user_email, l.ip_address
FROM audit_logs_auditlog l
LEFT JOIN accounts_user u ON u.id = l.user_id;

-- Read-only login for Metabase. Change the password, then use the same one in Metabase.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'metabase_reader') THEN
    CREATE ROLE metabase_reader LOGIN PASSWORD 'MetabaseRead@123';
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO metabase_reader', current_database());
END $$;

GRANT USAGE ON SCHEMA reporting TO metabase_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO metabase_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reporting GRANT SELECT ON TABLES TO metabase_reader;
