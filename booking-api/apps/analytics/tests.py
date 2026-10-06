import jwt
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.doctors.models import Doctor

SECRET = "metabase-test-secret-0123456789abcdef0123456789abcdef"


def client_for(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@override_settings(METABASE_SECRET_KEY=SECRET, METABASE_ADMIN_DASHBOARD_ID=1, METABASE_DOCTOR_DASHBOARD_ID=2,
                   METABASE_SITE_URL="http://mb.local")
class EmbedTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("a@x.com", "pw", first_name="A", last_name="A", role=Role.ADMIN)
        doc_user = User.objects.create_user("d@x.com", "pw", first_name="D", last_name="D", role=Role.DOCTOR)
        self.doctor = Doctor.objects.create(user=doc_user)
        self.patient = User.objects.create_user("p@x.com", "pw", first_name="P", last_name="P")

    def claims(self, response):
        token = response.data["url"].split("/embed/dashboard/")[1].split("#")[0]
        return jwt.decode(token, SECRET, algorithms=["HS256"])

    def test_admin_gets_unfiltered_dashboard(self):
        r = client_for(self.admin).get("/api/analytics/embed/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["url"].startswith("http://mb.local/embed/dashboard/"))
        self.assertEqual(self.claims(r), {"resource": {"dashboard": 1}, "params": {}, "exp": r.data["expires_at"]})

    def test_doctor_is_locked_to_own_id(self):
        r = client_for(self.doctor.user).get("/api/analytics/embed/")
        c = self.claims(r)
        self.assertEqual(c["resource"], {"dashboard": 2})
        self.assertEqual(c["params"], {"doctor_id": self.doctor.pk})

    def test_patient_forbidden(self):
        self.assertEqual(client_for(self.patient).get("/api/analytics/embed/").status_code, 403)

    @override_settings(METABASE_SECRET_KEY="")
    def test_not_configured(self):
        self.assertEqual(client_for(self.admin).get("/api/analytics/embed/").status_code, 503)
