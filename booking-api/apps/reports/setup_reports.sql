-- Read-only login for the Plotly report engine (booking-api REPORTS_DB_USER).
-- Run as postgres AFTER metabase/setup.sql (which creates the `reporting` views). Safe to re-run.
-- report_reader can only SELECT from reporting.* views: no raw tables, no password hashes, no writes.

DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'report_reader') THEN
    CREATE ROLE report_reader LOGIN PASSWORD 'ReportRead@123';
  END IF;
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO report_reader', current_database());
END $$;

ALTER ROLE report_reader SET default_transaction_read_only = on;
ALTER ROLE report_reader SET statement_timeout = '10s';
GRANT USAGE ON SCHEMA reporting TO report_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO report_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA reporting GRANT SELECT ON TABLES TO report_reader;
