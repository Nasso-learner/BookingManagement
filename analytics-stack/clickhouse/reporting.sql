-- ClickHouse reporting layer (run as ch_admin AFTER the PeerDB mirror has done its initial copy).
--   booking.*   = raw CDC tables (ReplacingMergeTree; FINAL + _peerdb_is_deleted = 0 gives current rows)
--   reporting.* = flat, pre-joined tables rebuilt every 30s -> report queries never join at read time.
-- Column names match PostgreSQL's reporting.* views, so most report SQL works on both sources.
-- PeerDB stores SQL NULL as 0 / '' / 1970-01-01 in non-Nullable columns; we turn those back into NULLs here.
-- Re-run safe: drops and recreates the views (data is rebuilt on the next refresh).

DROP VIEW IF EXISTS reporting.appointments;
CREATE MATERIALIZED VIEW reporting.appointments
REFRESH EVERY 30 SECOND
ENGINE = MergeTree ORDER BY (appointment_date, doctor_id, id)
AS
WITH
    a   AS (SELECT * FROM booking.appointments_appointment FINAL WHERE _peerdb_is_deleted = 0),
    d   AS (SELECT * FROM booking.doctors_doctor FINAL WHERE _peerdb_is_deleted = 0),
    u   AS (SELECT * FROM booking.accounts_user FINAL WHERE _peerdb_is_deleted = 0),
    p   AS (SELECT * FROM booking.patients_patient FINAL WHERE _peerdb_is_deleted = 0),
    dep AS (SELECT * FROM booking.departments_department FINAL WHERE _peerdb_is_deleted = 0)
SELECT
    a.id                                                        AS id,
    a.appointment_number                                        AS appointment_number,
    toDate(a.appointment_date)                                  AS appointment_date,
    formatDateTime(a.start_time, '%H:%i')                       AS start_time,
    formatDateTime(a.end_time, '%H:%i')                         AS end_time,
    toDayOfWeek(a.appointment_date)                             AS weekday_num,   -- 1 = Monday
    formatDateTime(a.appointment_date, '%a')                    AS weekday,
    toHour(a.start_time)                                        AS start_hour,
    a.status                                                    AS status,
    a.booking_source                                            AS booking_source,
    a.rescheduled_from_id != 0                                  AS is_reschedule,
    a.created_at                                                AS created_at,
    if(a.cancelled_at < '1971-01-01', NULL, a.cancelled_at)     AS cancelled_at,
    if(a.completed_at < '1971-01-01', NULL, a.completed_at)     AS completed_at,
    dateDiff('day', toDate(a.created_at, 'Asia/Kolkata'), toDate(a.appointment_date)) AS lead_days,
    a.doctor_id                                                 AS doctor_id,
    d.doctor_code                                               AS doctor_code,
    concat(u.first_name, ' ', u.last_name)                      AS doctor_name,
    d.specialization                                            AS specialization,
    d.consultation_fee                                          AS consultation_fee,
    nullIf(a.department_id, 0)                                  AS department_id,
    if(dep.name = '', 'Unassigned', dep.name)                   AS department_name,
    a.patient_id                                                AS patient_id,
    p.patient_code                                              AS patient_code,
    nullIf(p.gender, '')                                        AS patient_gender,
    nullIf(p.city, '')                                          AS patient_city
FROM a
INNER JOIN d ON d.id = a.doctor_id
INNER JOIN u ON u.id = d.user_id
INNER JOIN p ON p.id = a.patient_id
LEFT JOIN dep ON dep.id = a.department_id;

DROP VIEW IF EXISTS reporting.doctor_capacity;
CREATE MATERIALIZED VIEW reporting.doctor_capacity
REFRESH EVERY 30 SECOND
ENGINE = MergeTree ORDER BY doctor_id
AS
WITH
    d   AS (SELECT * FROM booking.doctors_doctor FINAL WHERE _peerdb_is_deleted = 0),
    u   AS (SELECT * FROM booking.accounts_user FINAL WHERE _peerdb_is_deleted = 0),
    dep AS (SELECT * FROM booking.departments_department FINAL WHERE _peerdb_is_deleted = 0),
    av  AS (SELECT * FROM booking.doctors_doctoravailability FINAL WHERE _peerdb_is_deleted = 0)
SELECT
    d.id                                          AS doctor_id,
    any(d.doctor_code)                            AS doctor_code,
    any(concat(u.first_name, ' ', u.last_name))   AS doctor_name,
    any(if(dep.name = '', 'Unassigned', dep.name)) AS department_name,
    any(u.is_active)                              AS doctor_active,
    any(d.is_available)                           AS is_available,
    toInt32(sumIf(intDivOrZero(dateDiff('minute', av.start_time, av.end_time), av.slot_duration), av.is_active)) AS weekly_slots
FROM d
INNER JOIN u ON u.id = d.user_id
LEFT JOIN dep ON dep.id = d.department_id
LEFT JOIN av ON av.doctor_id = d.id
GROUP BY d.id;

DROP VIEW IF EXISTS reporting.patients;
CREATE MATERIALIZED VIEW reporting.patients
REFRESH EVERY 30 SECOND
ENGINE = MergeTree ORDER BY patient_id
AS
SELECT p.id AS patient_id, p.patient_code AS patient_code, nullIf(p.gender, '') AS gender,
       nullIf(p.blood_group, '') AS blood_group, nullIf(p.city, '') AS city, u.is_active AS is_active,
       p.created_at AS created_at
FROM (SELECT * FROM booking.patients_patient FINAL WHERE _peerdb_is_deleted = 0) AS p
INNER JOIN (SELECT * FROM booking.accounts_user FINAL WHERE _peerdb_is_deleted = 0) AS u ON u.id = p.user_id;

DROP VIEW IF EXISTS reporting.audit_activity;
CREATE MATERIALIZED VIEW reporting.audit_activity
REFRESH EVERY 30 SECOND
ENGINE = MergeTree ORDER BY (created_at, id)
AS
SELECT l.id AS id, l.action AS action, l.model_name AS model_name, l.created_at AS created_at,
       nullIf(u.role, '') AS user_role, nullIf(u.email, '') AS user_email, nullIf(l.ip_address, '') AS ip_address
FROM (SELECT * FROM booking.audit_logs_auditlog FINAL WHERE _peerdb_is_deleted = 0) AS l
LEFT JOIN (SELECT * FROM booking.accounts_user FINAL WHERE _peerdb_is_deleted = 0) AS u ON u.id = l.user_id;
