from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.notifications.models import Notification, notify


class Command(BaseCommand):
    help = "Create APPOINTMENT_REMINDER notifications for tomorrow's active appointments. Run daily via cron."

    def handle(self, *args, **opts):
        tomorrow = timezone.localdate() + timedelta(days=1)
        due = Appointment.objects.filter(appointment_date=tomorrow, status__in=Appointment.ACTIVE).exclude(
            notifications__notification_type=Notification.Type.APPOINTMENT_REMINDER
        ).select_related("patient__user", "doctor__user")
        for appt in due:
            notify(appt.patient.user, Notification.Type.APPOINTMENT_REMINDER, "Appointment tomorrow",
                   f"Reminder: {appt.appointment_number} with {appt.doctor} tomorrow at {appt.start_time:%I:%M %p}.", appt)
        self.stdout.write(f"Sent {len(due)} reminders.")
