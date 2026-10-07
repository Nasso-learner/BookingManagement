-- Run against the PeerDB server (psql -h localhost -p 9900 -U peerdb). Creates the CDC pipeline.
CREATE PEER pg_booking FROM POSTGRES WITH (
  host = 'host.docker.internal', port = '5432', user = 'peerdb_replicator',
  password = 'CdcReplicator@123', database = 'BookingManagement'
);

CREATE PEER ch_booking FROM CLICKHOUSE WITH (
  host = 'clickhouse', port = 9000, user = 'ch_admin', password = 'ChAdmin@123',
  database = 'booking', disable_tls = true
);

CREATE MIRROR booking_cdc FROM pg_booking TO ch_booking WITH TABLE MAPPING (
  {from: public.appointments_appointment, to: appointments_appointment},
  {from: public.doctors_doctor, to: doctors_doctor},
  {from: public.doctors_doctoravailability, to: doctors_doctoravailability},
  {from: public.departments_department, to: departments_department},
  {from: public.patients_patient, to: patients_patient},
  {from: public.audit_logs_auditlog, to: audit_logs_auditlog},
  {from: public.accounts_user, to: accounts_user, exclude: [password]}
) WITH (
  do_initial_copy = true,
  publication_name = 'peerdb_booking',
  sync_interval = 10
);
