-- PostgreSQL side of the CDC pipeline (run as postgres on BookingManagement). Safe to re-run.
-- Requires: wal_level = logical (ALTER SYSTEM SET wal_level='logical'; then restart the service).
-- PeerDB connects as peerdb_replicator: replication + SELECT on the reporting tables only.
-- accounts_user.password is NOT published and is excluded by the mirror, so it never reaches ClickHouse.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'peerdb_replicator') THEN
    CREATE ROLE peerdb_replicator LOGIN REPLICATION PASSWORD 'CdcReplicator@123';
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO peerdb_replicator', current_database());
END $$;

GRANT USAGE ON SCHEMA public TO peerdb_replicator;
GRANT SELECT ON appointments_appointment, doctors_doctor, doctors_doctoravailability, departments_department,
                patients_patient, audit_logs_auditlog TO peerdb_replicator;
-- PeerDB's initial snapshot reads accounts_user with SELECT *, so a column-level grant is not enough.
-- The password hash is still kept out of ClickHouse twice: the mirror's `exclude: [password]` (snapshot)
-- and the publication column list below (ongoing CDC).
GRANT SELECT ON accounts_user TO peerdb_replicator;

DROP PUBLICATION IF EXISTS peerdb_booking;
CREATE PUBLICATION peerdb_booking FOR TABLE
    appointments_appointment, doctors_doctor, doctors_doctoravailability, departments_department,
    patients_patient, audit_logs_auditlog,
    accounts_user (id, email, first_name, last_name, phone_number, role, is_active, is_staff, is_superuser,
                   date_joined, last_login, created_at, updated_at);
