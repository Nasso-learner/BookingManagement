"""Appointment booking engine. All state changes to appointments go through here."""
from datetime import date, time
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role
from apps.appointments.models import Appointment
from apps.audit_logs.models import audit
from apps.doctors.models import Doctor
from apps.notifications.models import Notification, notify

Status = Appointment.Status
NType = Notification.Type


def _when(appt):
    return f"{appt.appointment_date:%d %b %Y} at {appt.start_time:%I:%M %p}"


def _notify_both(appt, ntype, title, message):
    notify(appt.patient.user, ntype, title, message, appt)
    notify(appt.doctor.user, ntype, title, message, appt)


def _is_past(day: date, start: time):
    now = timezone.localtime()
    return day < now.date() or (day == now.date() and start <= now.time())


def available_slots(doctor: Doctor, day: date):
    """Free (start, end) slots for a doctor on a date."""
    if not doctor.is_available or day < timezone.localdate():
        return []
    booked = list(
        doctor.appointments.filter(appointment_date=day, status__in=Appointment.ACTIVE).values_list(
            "start_time", "end_time"
        )
    )
    return [
        (s, e)
        for s, e in doctor.slots_for(day)
        if not _is_past(day, s) and not any(bs < e and be > s for bs, be in booked)
    ]


def _book(*, patient, doctor_id, day, start_time, reason, source, patient_notes="",
          rescheduled_from=None, reschedule_reason=""):
    # 1-2. Doctor exists and is active. Row lock serialises concurrent bookings for this doctor.
    doctor = Doctor.objects.select_for_update().filter(pk=doctor_id).first()
    if doctor is None:
        raise ValidationError({"doctor": "Doctor not found."})
    if not (doctor.is_available and doctor.user.is_active):
        raise ValidationError({"doctor": "This doctor is not accepting appointments."})
    # 3. Not in the past.
    if _is_past(day, start_time):
        raise ValidationError({"appointment_date": "Appointment date/time cannot be in the past."})
    # 4. Within availability (must match a slot boundary).
    slot = next(((s, e) for s, e in doctor.slots_for(day) if s == start_time), None)
    if slot is None:
        raise ValidationError({"start_time": "Selected time is outside the doctor's availability."})
    end_time = slot[1]
    overlapping = Appointment.objects.filter(
        appointment_date=day, status__in=Appointment.ACTIVE, start_time__lt=end_time, end_time__gt=start_time
    )
    # 5. Slot free.
    if overlapping.filter(doctor=doctor).exists():
        raise ValidationError({"start_time": "This slot is already booked. Please choose another time."})
    # 6. Patient has no conflicting appointment.
    # ponytail: cross-doctor patient overlap with *different* start times can race; the DB constraint covers same-start.
    if overlapping.filter(patient=patient).exists():
        raise ValidationError({"start_time": "The patient already has an appointment at this time."})
    # 7. Create (savepoint so a constraint violation doesn't poison the outer transaction).
    try:
        with transaction.atomic():
            appt = Appointment.objects.create(
                appointment_number=uuid4().hex,
                patient=patient,
                doctor=doctor,
                department=doctor.department,
                appointment_date=day,
                start_time=start_time,
                end_time=end_time,
                booking_source=source,
                reason=reason,
                patient_notes=patient_notes,
                rescheduled_from=rescheduled_from,
                reschedule_reason=reschedule_reason,
            )
    except IntegrityError:
        raise ValidationError({"start_time": "This slot was just booked. Please choose another time."})
    # 8. Unique, human-readable number derived from the PK.
    appt.appointment_number = f"APT-{day:%Y%m%d}-{appt.pk:05d}"
    appt.save(update_fields=["appointment_number"])
    return appt


def _source_for(actor):
    return Appointment.Source.ADMIN if actor.role == Role.ADMIN else Appointment.Source.WEB


@transaction.atomic
def create_appointment(*, actor, patient, doctor_id, appointment_date, start_time, reason, patient_notes="", request=None):
    appt = _book(
        patient=patient, doctor_id=doctor_id, day=appointment_date, start_time=start_time,
        reason=reason, patient_notes=patient_notes, source=_source_for(actor),
    )
    audit(actor, "APPOINTMENT_CREATED", appt, f"Booked {appt.appointment_number} for {_when(appt)}", request)  # 9
    _notify_both(appt, NType.APPOINTMENT_BOOKED, "Appointment booked",  # 10
                 f"{appt.appointment_number} with {appt.doctor} on {_when(appt)}.")
    return appt


def _lock(appt, allowed, verb):
    appt = Appointment.objects.select_for_update().get(pk=appt.pk)
    if appt.status not in allowed:
        raise ValidationError({"status": f"Cannot {verb} an appointment that is {appt.get_status_display().lower()}."})
    return appt


def _require_started(appt, verb):
    if appt.appointment_date > timezone.localdate():
        raise ValidationError({"appointment_date": f"Cannot {verb} a future appointment."})


@transaction.atomic
def confirm_appointment(appt, *, actor, request=None):
    appt = _lock(appt, [Status.PENDING], "confirm")
    appt.status = Status.CONFIRMED
    appt.save(update_fields=["status", "updated_at"])
    audit(actor, "APPOINTMENT_CONFIRMED", appt, appt.appointment_number, request)
    notify(appt.patient.user, NType.APPOINTMENT_CONFIRMED, "Appointment confirmed",
           f"{appt.appointment_number} with {appt.doctor} on {_when(appt)} is confirmed.", appt)
    return appt


@transaction.atomic
def complete_appointment(appt, *, actor, doctor_notes="", request=None):
    appt = _lock(appt, Appointment.ACTIVE, "complete")
    _require_started(appt, "complete")
    appt.status = Status.COMPLETED
    appt.completed_at = timezone.now()
    if doctor_notes:
        appt.doctor_notes = doctor_notes
    appt.save(update_fields=["status", "completed_at", "doctor_notes", "updated_at"])
    audit(actor, "APPOINTMENT_COMPLETED", appt, appt.appointment_number, request)
    notify(appt.patient.user, NType.APPOINTMENT_COMPLETED, "Appointment completed",
           f"Your visit {appt.appointment_number} with {appt.doctor} is complete.", appt)
    return appt


@transaction.atomic
def mark_no_show(appt, *, actor, request=None):
    appt = _lock(appt, Appointment.ACTIVE, "mark as no-show")
    _require_started(appt, "mark as no-show")
    appt.status = Status.NO_SHOW
    appt.save(update_fields=["status", "updated_at"])
    audit(actor, "APPOINTMENT_NO_SHOW", appt, appt.appointment_number, request)
    return appt


@transaction.atomic
def cancel_appointment(appt, *, actor, reason, request=None):
    if not (reason or "").strip():
        raise ValidationError({"reason": "A cancellation reason is required."})
    appt = _lock(appt, Appointment.ACTIVE, "cancel")
    appt.status = Status.CANCELLED
    appt.cancellation_reason = reason.strip()
    appt.cancelled_by = actor
    appt.cancelled_at = timezone.now()
    appt.save(update_fields=["status", "cancellation_reason", "cancelled_by", "cancelled_at", "updated_at"])
    audit(actor, "APPOINTMENT_CANCELLED", appt, f"{appt.appointment_number}: {appt.cancellation_reason}", request)
    _notify_both(appt, NType.APPOINTMENT_CANCELLED, "Appointment cancelled",
                 f"{appt.appointment_number} on {_when(appt)} was cancelled. Reason: {appt.cancellation_reason}")
    return appt


@transaction.atomic
def reschedule_appointment(appt, *, actor, appointment_date, start_time, reason, request=None):
    """Keeps the old record (status RESCHEDULED) and books a new one linked via rescheduled_from."""
    if not (reason or "").strip():
        raise ValidationError({"reason": "A reschedule reason is required."})
    old = _lock(appt, Appointment.ACTIVE, "reschedule")
    old.status = Status.RESCHEDULED  # frees the old slot for the conflict checks; rolled back if booking fails
    old.save(update_fields=["status", "updated_at"])
    new = _book(
        patient=old.patient, doctor_id=old.doctor_id, day=appointment_date, start_time=start_time,
        reason=old.reason, patient_notes=old.patient_notes, source=_source_for(actor),
        rescheduled_from=old, reschedule_reason=reason.strip(),
    )
    audit(actor, "APPOINTMENT_RESCHEDULED", new,
          f"{old.appointment_number} ({_when(old)}) -> {new.appointment_number} ({_when(new)}): {reason}", request)
    _notify_both(new, NType.APPOINTMENT_RESCHEDULED, "Appointment rescheduled",
                 f"{old.appointment_number} moved to {_when(new)} as {new.appointment_number}.")
    return new
