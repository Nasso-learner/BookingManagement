from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.doctors.models import Doctor
from apps.reports import engine
from apps.reports.models import Report

SCOPED = "SELECT d.id AS doctor_id FROM doctors_doctor d WHERE (:doctor_id IS NULL OR d.id = :doctor_id)"


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@override_settings(REPORTS_DB_ALIAS="default")
class ReportApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("a@x.com", "pw", first_name="A", last_name="A", role=Role.ADMIN)
        self.docs = [Doctor.objects.create(user=User.objects.create_user(f"d{i}@x.com", "pw", first_name="D",
                                                                         last_name=str(i), role=Role.DOCTOR))
                     for i in range(2)]
        self.patient = User.objects.create_user("p@x.com", "pw", first_name="P", last_name="P")
        self.shared = Report.objects.create(title="Shared", sql=SCOPED, doctor_access=True)
        self.private = Report.objects.create(title="Admin only", sql="SELECT 1 AS one")

    def test_doctor_scoped_to_own_rows_and_cannot_see_sql_or_private(self):
        c = client_for(self.docs[0].user)
        listing = c.get("/api/reports/").data
        self.assertEqual([r["title"] for r in listing], ["Shared"])
        self.assertNotIn("sql", listing[0])
        self.assertEqual(c.get(f"/api/reports/{self.shared.pk}/run/").data["rows"], [[self.docs[0].pk]])
        self.assertEqual(c.get(f"/api/reports/{self.private.pk}/run/").status_code, 404)
        self.assertEqual(c.post("/api/reports/", {"title": "x", "sql": "SELECT 1"}).status_code, 403)

    def test_admin_runs_unscoped(self):
        rows = client_for(self.admin).get(f"/api/reports/{self.shared.pk}/run/").data["rows"]
        self.assertEqual(sorted(r[0] for r in rows), sorted(d.pk for d in self.docs))

    def test_patient_forbidden(self):
        self.assertEqual(client_for(self.patient).get("/api/reports/").status_code, 403)

    def test_validation(self):
        c = client_for(self.admin)
        bad = [("DELETE FROM doctors_doctor", "Only SELECT"), ("SELECT 1; DROP TABLE x", "one statement"),
               ("SELECT 1", "must filter with :doctor_id")]
        for sql, msg in bad:
            r = c.post("/api/reports/", {"title": "t", "sql": sql, "doctor_access": True, "chart_type": "BAR"})
            self.assertEqual(r.status_code, 400)
            self.assertIn(msg, str(r.data))

    def test_percent_and_casts_survive(self):
        out = engine.run("SELECT 'a%' AS pct, now()::date AS d WHERE 'x' LIKE '%'")
        self.assertEqual(out["columns"], ["pct", "d"])
        self.assertEqual(out["rows"][0][0], "a%")

    def test_preview_as_doctor(self):
        r = client_for(self.admin).post("/api/reports/preview/", {"sql": SCOPED, "doctor_id": self.docs[1].pk})
        self.assertEqual(r.data["rows"], [[self.docs[1].pk]])


@override_settings(REPORTS_DB_ALIAS="default")
class ReadOnlyTests(TransactionTestCase):
    def test_data_modifying_cte_is_blocked(self):
        with self.assertRaises(ValidationError):
            engine.run("WITH d AS (DELETE FROM departments_department RETURNING id) SELECT count(*) FROM d")
