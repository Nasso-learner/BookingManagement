-- Runs once on first ClickHouse start (as ch_admin).
-- `booking`   : raw tables replicated from PostgreSQL by PeerDB (CDC)
-- `reporting` : flat, pre-joined tables that reports query (built by reporting.sql)
CREATE DATABASE IF NOT EXISTS booking;
CREATE DATABASE IF NOT EXISTS reporting;

-- Server-enforced limits for report queries. readonly=2: no writes/DDL; settings may only be lowered.
CREATE SETTINGS PROFILE IF NOT EXISTS report_profile SETTINGS
    readonly = 2,
    max_execution_time = 10 MAX 10,
    max_result_rows = 100000 MAX 100000,
    max_memory_usage = 4000000000 MAX 4000000000;

-- booking-api's report login: can read ONLY the reporting database.
CREATE USER IF NOT EXISTS report_reader IDENTIFIED WITH sha256_password BY 'ReportRead@123'
    SETTINGS PROFILE 'report_profile';
GRANT SELECT ON reporting.* TO report_reader;
