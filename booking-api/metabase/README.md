# Metabase analytics (local, no Docker)

Metabase reads the database through a **read-only** login that can only see the `reporting` views. Its dashboards appear inside booking-web (Admin → Analytics, Doctor → Analytics) as static embeds. booking-api signs every embed URL with `METABASE_SECRET_KEY`, and a doctor's URL always has their own `doctor_id` locked in.

```
browser ── booking-web :8001 ── booking-api :8002 ── PostgreSQL
   └──── iframe ── Metabase :3000 ── (metabase_reader, reporting.*) ──┘
```

## 1. Database access (already applied to your local DB)

Run [setup.sql](setup.sql) once as `postgres` (pgAdmin → Query Tool). It's safe to re-run. It creates:

- **The `reporting` schema**, with four views:
  - `appointments`
  - `doctor_capacity`
  - `patients`
  - `audit_activity`
- **The `metabase_reader` login** (password `MetabaseRead@123`), which can read only those views. It can't see password hashes or tokens, and it can't write.

Change the password with `ALTER ROLE metabase_reader PASSWORD '...';` if you like.

## 2. Install Java and run Metabase (Anaconda Prompt)

```bat
conda create -n metabase -c conda-forge openjdk=21 -y
conda activate metabase
mkdir C:\metabase
cd C:\metabase
curl -L -o metabase.jar https://downloads.metabase.com/latest/metabase.jar

set MB_JETTY_PORT=3000
set MB_DB_FILE=C:\metabase\metabase.db
java -jar metabase.jar
```

Wait for `Metabase Initialization COMPLETE` (the first start takes a minute or two), then open http://localhost:3000. Keep this window open. Next time you only need:

```bat
conda activate metabase
cd C:\metabase
set MB_JETTY_PORT=3000
java -jar metabase.jar
```

## 3. First-time setup in Metabase

1. **Create your Metabase admin account.** This is separate from your app login.
2. **Add the database:**
   - Type: PostgreSQL
   - Display name: `BookingManagement (reporting)`
   - Host: `localhost`, port: `5432`, database: `BookingManagement`
   - Username: `metabase_reader`, password: `MetabaseRead@123`
   - Schemas: *Only these…* → `reporting`
3. **Set the time zone:** Admin settings → Localization → Report time zone → `Asia/Kolkata`.

## 4. Create the questions

For each block in [questions.sql](questions.sql):

1. Go to **+ New → SQL query** and choose the database.
2. Paste the block and run it.
3. In the variables panel on the right, set **doctor_id → Variable type: Number**. Leave "Required" off.
4. Pick the chart type named in the block's comment, and save with the block's title.

## 5. Build the two dashboards

**Clinic analytics (Admin):** add questions 1–14. Add **no** Doctor filter.

**My analytics (Doctor):**
1. Add questions 1–6 and 9–12.
2. Add a filter: **Filter → Number → Equal to**, labelled exactly **`Doctor ID`**. Its slug becomes `doctor_id`, which booking-api relies on.
3. Connect it to the `doctor_id` variable on **every** card, then save.

Each dashboard's ID is the number in its URL. For example, `/dashboard/2-my-analytics` has ID **2**.

## 6. Turn on static embedding

1. **Admin settings → Embedding → Static embedding → Enable.** Copy the **Embedding secret key**.
2. Publish the admin dashboard: open it → **Share icon → Embed → Static embedding → Publish**.
3. Publish the doctor dashboard the same way, but first set the **Doctor ID** parameter to **Locked**, then publish.

## 7. Connect booking-api

In `booking-api/.env`:

```
METABASE_SITE_URL=http://localhost:3000
METABASE_SECRET_KEY=<embedding secret key from step 6>
METABASE_ADMIN_DASHBOARD_ID=<admin dashboard id>
METABASE_DOCTOR_DASHBOARD_ID=<doctor dashboard id>
METABASE_EMBED_MINUTES=60
```

Restart the API window (Ctrl+C, then `python manage.py runserver 8002`). Then sign in at http://localhost:8001:

- `nausheen.sayyed@rxcs.in` → **Analytics** shows the clinic-wide dashboard.
- `doctor@test.com` → **Analytics** shows only Dr. Sarah Khan's numbers.

## Troubleshooting

| What you see in the iframe | Fix |
|---|---|
| "Message seems corrupt or manipulated" | `METABASE_SECRET_KEY` doesn't match Metabase's key, or the API wasn't restarted after editing `.env` |
| "Embedding is not enabled" | Step 6.1 |
| "This dashboard is not published" or similar | Publish the dashboard (step 6.2 or 6.3) |
| Doctor sees an error about `doctor_id` | The doctor dashboard's parameter isn't **Locked**, or its slug isn't `doctor_id` (re-label it `Doctor ID`) |
| Doctor sees clinic-wide numbers on a card | That card isn't connected to the Doctor ID filter |
| Page says "Analytics isn't available yet" | `METABASE_SECRET_KEY` or a dashboard ID is empty in `booking-api/.env` |
| Data looks stale after you add appointments | Metabase caches results briefly; use the iframe's refresh or the **Refresh** button |
