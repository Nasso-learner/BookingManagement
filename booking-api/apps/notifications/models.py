from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        APPOINTMENT_BOOKED = "APPOINTMENT_BOOKED"
        APPOINTMENT_CONFIRMED = "APPOINTMENT_CONFIRMED"
        APPOINTMENT_CANCELLED = "APPOINTMENT_CANCELLED"
        APPOINTMENT_RESCHEDULED = "APPOINTMENT_RESCHEDULED"
        APPOINTMENT_COMPLETED = "APPOINTMENT_COMPLETED"
        APPOINTMENT_REMINDER = "APPOINTMENT_REMINDER"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    appointment = models.ForeignKey(
        "appointments.Appointment", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications"
    )
    notification_type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


def notify(user, notification_type, title, message, appointment=None):
    return Notification.objects.create(
        user=user, appointment=appointment, notification_type=notification_type, title=title, message=message
    )
