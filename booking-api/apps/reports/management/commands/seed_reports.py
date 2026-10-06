from django.core.management.base import BaseCommand

from apps.accounts.models import Role, User
from apps.reports.models import Report

SCOPE = "(:doctor_id IS NULL OR doctor_id = :doctor_id)"  # admins: all rows, doctors: their own

# title, description, chart, x, y, series, doctor_access, sql
STARTERS = [
    ("Appointments per day", "Last 90 days, split by status", "STACKED_BAR", "day", "appointments", "status", True,
     f"SELECT appointment_date AS day, status, COUNT(*) AS appointments FROM reporting.appointments "
     f"WHERE appointment_date >= CURRENT_DATE - 90 AND {SCOPE} GROUP BY 1, 2 ORDER BY 1"),
    ("Status breakdown", "Last 90 days", "PIE", "status", "appointments", "", True,
     f"SELECT status, COUNT(*) AS appointments FROM reporting.appointments "
     f"WHERE appointment_date >= CURRENT_DATE - 90 AND {SCOPE} GROUP BY 1 ORDER BY 2 DESC"),
    ("Completion rate %", "Completed vs completed + no-show + cancelled, last 90 days", "NUMBER", "", "completion_rate", "", True,
     f"SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE status = 'COMPLETED') / NULLIF(COUNT(*) FILTER "
     f"(WHERE status IN ('COMPLETED','NO_SHOW','CANCELLED')), 0), 1) AS completion_rate FROM reporting.appointments "
     f"WHERE appointment_date BETWEEN CURRENT_DATE - 90 AND CURRENT_DATE AND {SCOPE}"),
    ("Revenue by month", "Completed visits x consultation fee", "BAR", "month", "revenue", "", True,
     f"SELECT TO_CHAR(DATE_TRUNC('month', appointment_date), 'Mon YYYY') AS month, SUM(consultation_fee) AS revenue "
     f"FROM reporting.appointments WHERE status = 'COMPLETED' AND {SCOPE} "
     f"GROUP BY DATE_TRUNC('month', appointment_date) ORDER BY DATE_TRUNC('month', appointment_date)"),
    ("Busiest hours", "Appointments by start hour, last 90 days", "BAR", "hour", "appointments", "", True,
     f"SELECT LPAD(start_hour::text, 2, '0') || ':00' AS hour, COUNT(*) AS appointments FROM reporting.appointments "
     f"WHERE appointment_date >= CURRENT_DATE - 90 AND {SCOPE} GROUP BY start_hour ORDER BY start_hour"),
    ("Appointments by department", "Last 90 days", "HBAR", "department_name", "appointments", "", False,
     "SELECT department_name, COUNT(*) AS appointments FROM reporting.appointments "
     "WHERE appointment_date >= CURRENT_DATE - 90 GROUP BY 1 ORDER BY 2"),
    ("Doctor performance", "Last 90 days", "TABLE", "", "", "", False,
     "SELECT doctor_name, department_name, COUNT(*) AS total, "
     "COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed, COUNT(*) FILTER (WHERE status = 'CANCELLED') AS cancelled, "
     "COUNT(*) FILTER (WHERE status = 'NO_SHOW') AS no_shows, "
     "COALESCE(SUM(consultation_fee) FILTER (WHERE status = 'COMPLETED'), 0) AS revenue "
     "FROM reporting.appointments WHERE appointment_date >= CURRENT_DATE - 90 "
     "GROUP BY doctor_name, department_name ORDER BY total DESC"),
    ("New patients per month", "Patient registrations", "LINE", "month", "new_patients", "", False,
     "SELECT TO_CHAR(DATE_TRUNC('month', created_at), 'Mon YYYY') AS month, COUNT(*) AS new_patients "
     "FROM reporting.patients GROUP BY DATE_TRUNC('month', created_at) ORDER BY DATE_TRUNC('month', created_at)"),
]


class Command(BaseCommand):
    help = "Create starter Plotly reports (skips titles that already exist)."

    def handle(self, *args, **opts):
        admin = User.objects.filter(role=Role.ADMIN).first()
        created = 0
        for title, desc, chart, x, y, series, doctor_access, sql in STARTERS:
            _, new = Report.objects.get_or_create(title=title, defaults=dict(
                description=desc, chart_type=chart, x_column=x, y_columns=y, series_column=series,
                doctor_access=doctor_access, sql=sql, created_by=admin))
            created += new
        self.stdout.write(self.style.SUCCESS(f"{created} report(s) created, {len(STARTERS) - created} already existed."))
