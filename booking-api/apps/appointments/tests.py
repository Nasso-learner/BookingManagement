from datetime import time, timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.appointments.models import Appointment
from apps.doctors.models import Doctor, DoctorAvailability
from apps.notifications.models import Notification
from apps.audit_logs.models import AuditLog
from apps.patients.models import Patient


def next_monday():
    today = timezone.localdate()
    return today + timedelta(days=7 - today.weekday())


class BookingTests(TestCase):
    def setUp(self):
        self.doc_user = User.objects.create_user("doc@x.com", "pw-Strong-123", first_name="Sarah", last_name="Khan", role=Role.DOCTOR)
        self.doctor = Doctor.objects.create(user=self.doc_user, specialization="Cardiology")
        DoctorAvailability.objects.create(doctor=self.doctor, day_of_week=0, start_time=time(9), end_time=time(11))
        self.p1 = self._patient("p1@x.com")
        self.p2 = self._patient("p2@x.com")
        self.day = next_monday()

    def _patient(self, email):
        return Patient.objects.create(user=User.objects.create_user(email, "pw-Strong-123", first_name="P", last_name="X"))

    def client_for(self, user):
        c = APIClient()
        r = c.post("/api/auth/login/", {"email": user.email, "password": "pw-Strong-123"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["user"]["role"], user.role)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return c

    def book(self, client, start="09:00", day=None):
        return client.post("/api/appointments/", {"doctor": self.doctor.pk, "appointment_date": str(day or self.day),
                                                  "start_time": start, "reason": "Checkup"}, format="json")

    def test_book_and_prevent_double_booking(self):
        r = self.book(self.client_for(self.p1.user))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertRegex(r.data["appointment_number"], rf"^APT-{self.day:%Y%m%d}-\d{{5}}$")
        self.assertEqual(r.data["end_time"], "09:30:00")
        self.assertEqual(self.book(self.client_for(self.p2.user)).status_code, 400)
        self.assertTrue(AuditLog.objects.filter(action="APPOINTMENT_CREATED").exists())
        self.assertEqual(Notification.objects.filter(notification_type="APPOINTMENT_BOOKED").count(), 2)
        # slot no longer offered
        slots = self.client_for(self.p2.user).get(f"/api/doctors/{self.doctor.pk}/slots/?date={self.day}").data["slots"]
        self.assertNotIn("09:00", [s["start"] for s in slots])
        self.assertEqual(len(slots), 3)

    def test_rejects_outside_availability_past_and_off_grid(self):
        c = self.client_for(self.p1.user)
        self.assertEqual(self.book(c, "12:00").status_code, 400)
        self.assertEqual(self.book(c, "09:15").status_code, 400)
        self.assertEqual(self.book(c, day=self.day - timedelta(days=7 * 52)).status_code, 400)

    def test_db_constraint_blocks_duplicate_active_slot(self):
        kw = dict(doctor=self.doctor, appointment_date=self.day, start_time=time(9), end_time=time(9, 30), reason="r")
        Appointment.objects.create(appointment_number="A1", patient=self.p1, **kw)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.create(appointment_number="A2", patient=self.p2, **kw)
        # a cancelled appointment does not hold the slot
        Appointment.objects.filter(appointment_number="A1").update(status="CANCELLED")
        Appointment.objects.create(appointment_number="A3", patient=self.p2, **kw)

    def test_reschedule_keeps_history_and_frees_slot(self):
        c = self.client_for(self.p1.user)
        old = self.book(c).data
        r = c.post(f"/api/appointments/{old['id']}/reschedule/",
                   {"appointment_date": str(self.day), "start_time": "10:00", "reason": "Clash"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["rescheduled_from"], old["id"])
        self.assertEqual(Appointment.objects.get(pk=old["id"]).status, "RESCHEDULED")
        self.assertEqual(self.book(self.client_for(self.p2.user)).status_code, 201)  # 09:00 free again

    def test_failed_reschedule_rolls_back(self):
        c = self.client_for(self.p1.user)
        old = self.book(c).data
        r = c.post(f"/api/appointments/{old['id']}/reschedule/",
                   {"appointment_date": str(self.day), "start_time": "15:00", "reason": "x"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Appointment.objects.get(pk=old["id"]).status, "PENDING")

    def test_cancel_requires_reason_and_role_rules(self):
        pc = self.client_for(self.p1.user)
        appt = self.book(pc).data
        self.assertEqual(pc.post(f"/api/appointments/{appt['id']}/cancel/", {}, format="json").status_code, 400)
        self.assertEqual(pc.post(f"/api/appointments/{appt['id']}/confirm/").status_code, 403)
        self.assertEqual(self.client_for(self.p2.user).get(f"/api/appointments/{appt['id']}/").status_code, 404)
        dc = self.client_for(self.doc_user)
        self.assertEqual(dc.post(f"/api/appointments/{appt['id']}/confirm/").data["status"], "CONFIRMED")
        self.assertEqual(dc.post(f"/api/appointments/{appt['id']}/complete/").status_code, 400)  # future
        r = pc.post(f"/api/appointments/{appt['id']}/cancel/", {"reason": "Travel"}, format="json")
        self.assertEqual(r.data["status"], "CANCELLED")
        self.assertEqual(r.data["cancelled_by_name"], "P X")

    def test_role_endpoints_and_registration(self):
        pc = self.client_for(self.p1.user)
        self.assertEqual(pc.get("/api/audit-logs/").status_code, 403)
        self.assertEqual(pc.get("/api/patients/").status_code, 403)
        self.assertEqual(pc.get("/api/availability/").status_code, 403)
        r = APIClient().post("/api/auth/register/", {"first_name": "A", "last_name": "B", "email": "new@x.com",
                                                      "password": "pw-Strong-123", "confirm_password": "pw-Strong-123",
                                                      "role": "ADMIN"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_availability_overlap_rejected(self):
        dc = self.client_for(self.doc_user)
        r = dc.post("/api/availability/", {"day_of_week": 0, "start_time": "10:30", "end_time": "12:00",
                                           "slot_duration": 30}, format="json")
        self.assertEqual(r.status_code, 400)
        r = dc.post("/api/availability/", {"day_of_week": 0, "start_time": "11:00", "end_time": "12:00",
                                           "slot_duration": 30}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
