from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Appointment(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED = "CONFIRMED", "Confirmed"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        RESCHEDULED = "RESCHEDULED", "Rescheduled"
        NO_SHOW = "NO_SHOW", "No show"

    class Source(models.TextChoices):
        WEB = "WEB", "Web"
        ADMIN = "ADMIN", "Admin"

    ACTIVE = [Status.PENDING, Status.CONFIRMED]

    appointment_number = models.CharField(max_length=32, unique=True)
    patient = models.ForeignKey("patients.Patient", on_delete=models.PROTECT, related_name="appointments")
    doctor = models.ForeignKey("doctors.Doctor", on_delete=models.PROTECT, related_name="appointments")
    department = models.ForeignKey(
        "departments.Department", on_delete=models.PROTECT, null=True, blank=True, related_name="appointments"
    )
    appointment_date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    booking_source = models.CharField(max_length=10, choices=Source.choices, default=Source.WEB)
    reason = models.TextField()
    patient_notes = models.TextField(blank=True)
    doctor_notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    rescheduled_from = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="rescheduled_to"
    )
    reschedule_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-appointment_date", "-start_time"]
        constraints = [
            # DB-level double-booking guard: only one active appointment per doctor/patient per slot start.
            models.UniqueConstraint(
                fields=["doctor", "appointment_date", "start_time"],
                condition=Q(status__in=["PENDING", "CONFIRMED"]),
                name="uniq_active_doctor_slot",
            ),
            models.UniqueConstraint(
                fields=["patient", "appointment_date", "start_time"],
                condition=Q(status__in=["PENDING", "CONFIRMED"]),
                name="uniq_active_patient_slot",
            ),
            models.CheckConstraint(condition=Q(end_time__gt=F("start_time")), name="appointment_end_after_start"),
        ]

    def __str__(self):
        return self.appointment_number
