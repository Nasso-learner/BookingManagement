from datetime import date
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.doctors.models import Doctor
from apps.insights import views


class FakeClickHouse:
    """Records every query; returns a KPI row with NaN averages and an empty result for the rest."""

    def __init__(self):
        self.calls = []

    def query(self, sql, parameters=None, settings=None):
        self.calls.append((sql, parameters))
        if "uniqExactIf" in sql:  # KPI query
            cols = ("total", "avg_lead_days", "p_avg_lead_days")
            return type("R", (), {"column_names": cols, "result_rows": [(3, float("nan"), 1.5)]})()
        return type("R", (), {"column_names": (), "result_rows": []})()


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@override_settings(CLICKHOUSE_HOST="ch.local")
class InsightsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = User.objects.create_user("a@x.com", "pw", first_name="A", last_name="A", role=Role.ADMIN)
        self.doctor = Doctor.objects.create(user=User.objects.create_user("d@x.com", "pw", first_name="D",
                                                                           last_name="D", role=Role.DOCTOR))
        self.patient = User.objects.create_user("p@x.com", "pw", first_name="P", last_name="P")
        self.fake = FakeClickHouse()
        patcher = mock.patch.object(views, "_clickhouse_client", return_value=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, user, qs=""):
        return client_for(user).get("/api/insights/clinic/" + qs)

    def test_doctor_is_pinned_to_self_and_gets_no_leaderboard(self):
        r = self.get(self.doctor.user, "?doctor=999")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["scope"], "doctor")
        self.assertTrue(all(p["doctor_id"] == self.doctor.pk for _, p in self.fake.calls))
        self.assertIsNone(r.data["doctors"])
        self.assertFalse(any("LIMIT 25" in sql for sql, _ in self.fake.calls))  # leaderboard query not even run

    def test_admin_filters_are_bound_parameters(self):
        r = self.get(self.admin, "?department=Cardiology&status=COMPLETED&doctor=4&date_from=2026-01-01&date_to=2026-01-31")
        self.assertEqual(r.status_code, 200)
        sql, params = self.fake.calls[0]
        self.assertEqual(params["department"], "Cardiology")
        self.assertEqual(params["doctor_id"], 4)
        self.assertEqual(params["prev_from"], date(2025, 12, 1))  # previous period of equal length
        self.assertNotIn("Cardiology", "".join(s for s, _ in self.fake.calls))  # never formatted into SQL
        self.assertEqual(r.data["granularity"], "day")
        self.assertEqual(len(r.data["trend"]["buckets"]), 31)

    def test_nan_becomes_null_and_response_is_cached(self):
        r = self.get(self.admin)
        self.assertIsNone(r.data["kpis"]["avg_lead_days"])
        self.assertEqual(r.data["kpis"]["p_avg_lead_days"], 1.5)
        calls = len(self.fake.calls)
        self.assertTrue(self.get(self.admin).data["cached"])
        self.assertEqual(len(self.fake.calls), calls)

    def test_rejects_bad_input_and_roles(self):
        self.assertEqual(self.get(self.patient).status_code, 403)
        self.assertEqual(self.get(self.admin, "?status=DROP").status_code, 400)
        self.assertEqual(self.get(self.admin, "?date_from=2026-02-01&date_to=2026-01-01").status_code, 400)
        self.assertEqual(self.get(self.admin, "?date_from=2019-01-01&date_to=2026-01-01").status_code, 400)

    @override_settings(CLICKHOUSE_HOST="")
    def test_unavailable_without_clickhouse(self):
        self.assertEqual(self.get(self.admin).status_code, 503)

    def test_granularity(self):
        self.assertEqual(views._granularity(date(2026, 1, 1), date(2026, 1, 31)), "day")
        self.assertEqual(views._granularity(date(2026, 1, 1), date(2026, 3, 31)), "week")
        self.assertEqual(views._granularity(date(2025, 1, 1), date(2026, 1, 1)), "week")
        self.assertEqual(views._granularity(date(2023, 1, 1), date(2026, 1, 1)), "month")
