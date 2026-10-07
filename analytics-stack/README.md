# Analytics stack: PostgreSQL → PeerDB (CDC) → ClickHouse

High-performance reporting for MediBook. Bookings stay in PostgreSQL. **PeerDB** streams every change into **ClickHouse** a few seconds later, and ClickHouse keeps pre-joined `reporting.*` tables. The in-app **Reports** page (booking-web `/reports/`) queries those tables through booking-api. Users see them through their normal MediBook login, so there are no tokens in URLs and nothing is exposed to the browser.

```
PostgreSQL (BookingManagement)          Docker (this folder)
  publication peerdb_booking ──CDC──► PeerDB ──► ClickHouse  booking.*   (raw replicated tables)
  (no password column)                 :3001 UI      │        reporting.* (flat tables, refreshed every 30s)
                                                      ▼
booking-web :8001 ──cookie──► booking-api :8002 ──report_reader (read-only)──► ClickHouse :8123 (localhost only)
```

Freshness: about 10 s of CDC sync plus up to 30 s of refresh, so roughly 40 s from a booking to the report.

## Daily use

```bat
cd analytics-stack
docker compose -f peerdb/docker-compose.yml -f docker-compose.clickhouse.yml up -d     :: start
docker compose -f peerdb/docker-compose.yml -f docker-compose.clickhouse.yml ps        :: status
docker compose -f peerdb/docker-compose.yml -f docker-compose.clickhouse.yml stop      :: stop (keeps data)
```

- **PeerDB UI:** http://localhost:3001 (mirror `booking_cdc` status, lag and errors)
- **ClickHouse SQL as admin:** `docker exec -it clickhouse clickhouse-client --user ch_admin --password ChAdmin@123`

## One-time setup (already done on this machine)

1. **PostgreSQL**
   - Run `ALTER SYSTEM SET wal_level = 'logical';`, then restart the `postgresql-x64-17` service from an Administrator PowerShell.
   - Run [postgres/cdc_setup.sql](postgres/cdc_setup.sql) as `postgres`. It creates the `peerdb_replicator` login (replication plus SELECT on 7 tables) and the `peerdb_booking` publication, whose `accounts_user` column list leaves out `password`.
2. **Line endings:** after cloning PeerDB on Windows, run `git -C peerdb config core.autocrlf false`, then `git -C peerdb rm --cached -r -q .` and `git -C peerdb reset --hard`. Otherwise its shell scripts get CRLF line endings and the containers can't run them.
3. **Start the stack.** On a fresh volume, ClickHouse runs [clickhouse/init/01_security.sql](clickhouse/init/01_security.sql) automatically. It creates the `report_reader` user (readonly=2, max 10 s, row and memory caps, SELECT on `reporting.*` only).
4. **Create the mirror:** run `psql -h localhost -p 9900 -U peerdb` and execute [postgres/peerdb_mirror.sql](postgres/peerdb_mirror.sql). This creates the `pg_booking` and `ch_booking` peers and the `booking_cdc` mirror (`exclude: [password]`).
5. **Build the reporting layer:** once the initial copy is done, pipe [clickhouse/reporting.sql](clickhouse/reporting.sql) into `clickhouse-client --multiquery` as `ch_admin`.
6. **booking-api `.env`:** set `CLICKHOUSE_HOST=localhost`, `CLICKHOUSE_REPORT_USER=report_reader` and `CLICKHOUSE_REPORT_PASSWORD=...`. Then run `pip install clickhouse-connect`, `python manage.py migrate` and `python manage.py seed_reports`.

## Security layers

| Layer | What it enforces |
|---|---|
| PostgreSQL | CDC login reads only 7 tables; `password` isn't in the publication and is excluded by the mirror |
| Network | ClickHouse ports are bound to `127.0.0.1`; only booking-api connects. Browsers never reach ClickHouse |
| ClickHouse user | `report_reader`: SELECT on `reporting.*` only. Raw `booking.*` tables, writes and table functions (`url`, `file`, `s3`, `postgresql` …) are all denied |
| ClickHouse profile | readonly=2; `max_execution_time` ≤ 10 s, `max_result_rows` and `max_memory_usage` capped, and these can't be raised from SQL |
| booking-api | Admin-only SQL authoring; single SELECT/WITH; `:doctor_id` bound server-side for doctors; every run audited |
| booking-web | Role check (admin or doctor); data reaches the page only through the cookie-authenticated web → API path |

## Performance (measured on this machine)

10 million synthetic appointments take 140 MB on disk. Report-style aggregations take 0.01–0.16 s:
- per-day by status: 0.16 s
- 500-doctor scorecard: 0.09 s
- one doctor's 90-day trend: 0.01 s
- revenue by month × department: 0.13 s

## Before production

- Change every password here (`ChAdmin@123`, `ReportRead@123`, `CdcReplicator@123`, PeerDB's `NEXTAUTH_SECRET`), ideally loaded from a secrets store.
- Enable TLS between booking-api and ClickHouse (`CLICKHOUSE_SECURE=1`).
- Put the PeerDB UI behind authentication or keep it off the public network.
- Back up ClickHouse volumes and watch replication-slot lag in PostgreSQL (`pg_replication_slots`).

