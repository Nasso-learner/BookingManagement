from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.appointments.models import Appointment
from apps.appointments.services import booking_service as svc
from apps.departments.models import Department
from apps.doctors.models import Doctor, DoctorAvailability
from apps.patients.models import Patient

ADMIN = ("nausheen.sayyed@rxcs.in", "Admin@123", "Nausheen", "Sayyed")
DOCTOR_PASSWORD = "Doctor@123"
PATIENT_PASSWORD = "Patient@123"

DEPARTMENTS = [
    ("Cardiology", "CARD", "Heart and blood vessel care."),
    ("Dermatology", "DERM", "Skin, hair and nail conditions."),
    ("Neurology", "NEUR", "Brain, spine and nervous system."),
    ("Orthopedics", "ORTH", "Bones, joints and muscles."),
    ("Pediatrics", "PEDS", "Care for infants, children and teens."),
    ("General Medicine", "GMED", "Primary and preventive care."),
]
# email, first, last, dept, specialization, qualification, years, fee, city
DOCTORS = [
    ("doctor@test.com", "Sarah", "Khan", "CARD", "Cardiologist", "MBBS, MD, DM (Cardiology)", 12, 800, "Mumbai"),
    ("john.smith@test.com", "John", "Smith", "CARD", "Interventional Cardiologist", "MBBS, MD", 9, 1000, "Pune"),
    ("priya.nair@test.com", "Priya", "Nair", "DERM", "Dermatologist", "MBBS, MD (Dermatology)", 7, 600, "Mumbai"),
    ("arjun.mehta@test.com", "Arjun", "Mehta", "NEUR", "Neurologist", "MBBS, DM (Neurology)", 15, 1200, "Bengaluru"),
    ("emily.clark@test.com", "Emily", "Clark", "ORTH", "Orthopedic Surgeon", "MBBS, MS (Ortho)", 10, 900, "Pune"),
    ("rahul.verma@test.com", "Rahul", "Verma", "PEDS", "Pediatrician", "MBBS, MD (Pediatrics)", 8, 500, "Mumbai"),
    ("anita.desai@test.com", "Anita", "Desai", "GMED", "General Physician", "MBBS", 5, 400, "Bengaluru"),
]
# email, first, last, gender, blood, city
PATIENTS = [
    ("patient@test.com", "Aisha", "Patel", Patient.Gender.FEMALE, "O+", "Mumbai"),
    ("patient2@test.com", "Rohan", "Gupta", Patient.Gender.MALE, "B+", "Pune"),
]


class Command(BaseCommand):
    help = "Seed departments, an admin, doctors with schedules, patients and sample appointments. Safe to re-run."

    @transaction.atomic
    def handle(self, *args, **opts):
        depts = {code: Department.objects.get_or_create(code=code, defaults={"name": name, "description": desc})[0]
                 for name, code, desc in DEPARTMENTS}

        email, pw, first, last = ADMIN
        if not User.objects.filter(email=email).exists():
            User.objects.create_superuser(email, pw, first_name=first, last_name=last)  # role=ADMIN + Django admin access

        doctors = []
        for i, (email, first, last, code, spec, qual, exp, fee, city) in enumerate(DOCTORS):
            doctor = Doctor.objects.filter(user__email=email).first()
            if doctor is None:
                user = User.objects.create_user(email, DOCTOR_PASSWORD, first_name=first, last_name=last,
                                                role=Role.DOCTOR, phone_number=f"+91 98200 1{i:04d}")
                doctor = Doctor.objects.create(
                    user=user, department=depts[code], specialization=spec, qualification=qual,
                    experience_years=exp, consultation_fee=fee, city=city, license_number=f"MCI-{10000 + i}",
                    bio=f"Dr. {first} {last} is a {spec.lower()} with {exp} years of experience, focused on "
                        f"evidence-based, compassionate care.",
                )
                for day in range(5):  # Mon-Fri, morning + afternoon, 30-min slots
                    DoctorAvailability.objects.create(doctor=doctor, day_of_week=day, start_time=time(9), end_time=time(13))
                    DoctorAvailability.objects.create(doctor=doctor, day_of_week=day, start_time=time(14), end_time=time(18))
                if i % 2 == 0:
                    DoctorAvailability.objects.create(doctor=doctor, day_of_week=5, start_time=time(10), end_time=time(13))
            doctors.append(doctor)

        # A self-registered doctor waiting for admin approval (cannot log in until approved).
        if not User.objects.filter(email="pending.doctor@test.com").exists():
            user = User.objects.create_user("pending.doctor@test.com", DOCTOR_PASSWORD, first_name="Meera",
                                            last_name="Iyer", role=Role.DOCTOR, is_active=False)
            Doctor.objects.create(user=user, specialization="Dermatologist")

        patients = []
        for i, (email, first, last, gender, blood, city) in enumerate(PATIENTS):
            patient = Patient.objects.filter(user__email=email).first()
            if patient is None:
                user = User.objects.create_user(email, PATIENT_PASSWORD, first_name=first, last_name=last,
                                                phone_number=f"+91 98200 5{i:04d}")
                patient = Patient.objects.create(user=user, gender=gender, blood_group=blood, city=city,
                                                 emergency_contact_name="Family Contact",
                                                 emergency_contact_phone="+91 98200 99999")
            patients.append(patient)

        if not Appointment.objects.exists():
            self._sample_appointments(doctors, patients)

        self.stdout.write(self.style.SUCCESS("\nSeeded. Log in at booking-web with:"))
        for role, login, password in [
            ("ADMIN  ", ADMIN[0], ADMIN[1]),
            ("DOCTOR ", "doctor@test.com", DOCTOR_PASSWORD),
            ("PATIENT", "patient@test.com", PATIENT_PASSWORD),
            ("PATIENT", "patient2@test.com", PATIENT_PASSWORD),
            ("PENDING", "pending.doctor@test.com", f"{DOCTOR_PASSWORD} (approve in Admin > Doctors first)"),
        ]:
            self.stdout.write(f"  {role}  {login:<28} {password}")
        self.stdout.write(f"  Other doctors: <name>@test.com / {DOCTOR_PASSWORD}")

    def _sample_appointments(self, doctors, patients):
        sarah, aisha, rohan = doctors[0], patients[0], patients[1]
        admin = User.objects.get(email=ADMIN[0])
        today = timezone.localdate()

        def weekday(offset):
            d = today + timedelta(days=offset)
            while d.weekday() >= 5:
                d += timedelta(days=1 if offset >= 0 else -1)
            return d

        # Past history (created directly: the booking engine rightly refuses past dates).
        past = [(aisha, weekday(-14), time(10), "COMPLETED", "Routine heart check-up", "BP normal. Continue current medication."),
                (aisha, weekday(-7), time(11), "CANCELLED", "Follow-up on ECG report", ""),
                (rohan, weekday(-5), time(9, 30), "NO_SHOW", "Chest discomfort", ""),
                (rohan, weekday(-3), time(15), "COMPLETED", "Palpitations", "Advised Holter monitoring.")]
        for n, (patient, day, start, status, reason, notes) in enumerate(past, 1):
            end = (datetime.combine(day, start) + timedelta(minutes=30)).time()
            Appointment.objects.create(
                appointment_number=f"APT-{day:%Y%m%d}-9{n:04d}", patient=patient, doctor=sarah,
                department=sarah.department, appointment_date=day, start_time=start, end_time=end, status=status,
                reason=reason, doctor_notes=notes,
                cancellation_reason="Travelling out of town" if status == "CANCELLED" else "",
                cancelled_by=patient.user if status == "CANCELLED" else None,
                cancelled_at=timezone.now() if status == "CANCELLED" else None,
                completed_at=timezone.now() if status == "COMPLETED" else None,
            )

        # Upcoming bookings through the real engine (creates notifications + audit logs too).
        def book(patient, doctor, offset, reason, actor=None):
            day = weekday(offset)
            slots = svc.available_slots(doctor, day)
            return svc.create_appointment(actor=actor or patient.user, patient=patient, doctor_id=doctor.pk,
                                          appointment_date=day, start_time=slots[0][0], reason=reason)

        first = book(aisha, sarah, 2, "Shortness of breath while climbing stairs")
        svc.confirm_appointment(first, actor=sarah.user)
        book(aisha, doctors[2], 4, "Skin rash on forearm")
        book(rohan, sarah, 3, "Review Holter monitor results")
        book(rohan, doctors[6], 1, "Fever and body ache for 3 days", actor=admin)  # booked by admin (source ADMIN)
