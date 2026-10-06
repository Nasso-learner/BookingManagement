from datetime import date, datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Doctor(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="doctor")
    doctor_code = models.CharField(max_length=20, unique=True, editable=False)
    specialization = models.CharField(max_length=100, blank=True, db_index=True)
    department = models.ForeignKey(
        "departments.Department", on_delete=models.PROTECT, null=True, blank=True, related_name="doctors"
    )
    qualification = models.CharField(max_length=200, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bio = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to="doctors/", blank=True, null=True)
    license_number = models.CharField(max_length=50, blank=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    consultation_duration = models.PositiveSmallIntegerField(default=30, help_text="Minutes")
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__first_name"]

    def __str__(self):
        return f"Dr. {self.user.full_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.doctor_code:
            self.doctor_code = f"DOC-{self.pk:05d}"
            super().save(update_fields=["doctor_code"])

    def slots_for(self, day: date):
        """All (start, end) slot times for a date from active availability windows."""
        slots = []
        for window in self.availabilities.filter(is_active=True, day_of_week=day.weekday()).order_by("start_time"):
            step = timedelta(minutes=window.slot_duration)
            cur = datetime.combine(day, window.start_time)
            end = datetime.combine(day, window.end_time)
            while cur + step <= end:
                slots.append((cur.time(), (cur + step).time()))
                cur += step
        return slots


class DoctorAvailability(models.Model):
    class Day(models.IntegerChoices):
        MONDAY = 0
        TUESDAY = 1
        WEDNESDAY = 2
        THURSDAY = 3
        FRIDAY = 4
        SATURDAY = 5
        SUNDAY = 6

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="availabilities")
    day_of_week = models.PositiveSmallIntegerField(choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration = models.PositiveSmallIntegerField(default=30, help_text="Minutes")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_week", "start_time"]
        verbose_name_plural = "doctor availabilities"
        constraints = [
            models.CheckConstraint(condition=models.Q(end_time__gt=models.F("start_time")), name="availability_end_after_start"),
            models.CheckConstraint(condition=models.Q(slot_duration__gte=5), name="availability_min_slot"),
        ]

    def __str__(self):
        return f"{self.doctor} {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("End time must be after start time.")
        # ponytail: overlap checked in app code; a Postgres ExclusionConstraint (btree_gist) would make it DB-enforced
        overlapping = DoctorAvailability.objects.filter(
            doctor_id=self.doctor_id,
            day_of_week=self.day_of_week,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if overlapping.exists():
            raise ValidationError("This schedule overlaps an existing schedule for the same day.")
