from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.doctors.models import Doctor
from apps.patients.models import Patient

from .models import Appointment
from .serializers import AppointmentSerializer, BookSerializer, RescheduleSerializer
from .services import booking_service as svc

# Which roles may perform each state transition (ownership is enforced by get_queryset).
ACTION_ROLES = {
    "confirm": {Role.DOCTOR, Role.ADMIN},
    "complete": {Role.DOCTOR, Role.ADMIN},
    "no_show": {Role.DOCTOR, Role.ADMIN},
    "cancel": {Role.PATIENT, Role.DOCTOR, Role.ADMIN},
    "reschedule": {Role.PATIENT, Role.ADMIN},
}


def scoped_appointments(user):
    qs = Appointment.objects.select_related(
        "patient__user", "doctor__user", "department", "cancelled_by", "rescheduled_from", "rescheduled_to"
    )
    if user.role == Role.PATIENT:
        return qs.filter(patient__user=user)
    if user.role == Role.DOCTOR:
        return qs.filter(doctor__user=user)
    return qs


class AppointmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = AppointmentSerializer

    def get_queryset(self):
        qs = scoped_appointments(self.request.user)
        p = self.request.query_params
        if s := p.get("status"):
            qs = qs.filter(status__in=s.split(","))
        for param, lookup in [("date", "appointment_date"), ("date_from", "appointment_date__gte"),
                              ("date_to", "appointment_date__lte"), ("doctor", "doctor_id"),
                              ("patient", "patient_id")]:
            if value := p.get(param):
                qs = qs.filter(**{lookup: value})
        if q := p.get("q"):
            qs = qs.filter(Q(appointment_number__icontains=q) | Q(patient__patient_code__iexact=q) | Q(patient__user__first_name__icontains=q)
                           | Q(patient__user__last_name__icontains=q) | Q(doctor__user__first_name__icontains=q)
                           | Q(doctor__user__last_name__icontains=q) | Q(reason__icontains=q))
        if p.get("upcoming") == "1":
            qs = qs.filter(appointment_date__gte=timezone.localdate()).order_by("appointment_date", "start_time")
        return qs

    def create(self, request):
        if request.user.role == Role.DOCTOR:
            raise PermissionDenied("Doctors cannot book appointments.")
        s = BookSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        if request.user.role == Role.ADMIN:
            patient = Patient.objects.filter(pk=d.get("patient")).first()
            if patient is None:
                raise ValidationError({"patient": "Patient is required."})
        else:
            patient = request.user.patient
        appt = svc.create_appointment(
            actor=request.user, patient=patient, doctor_id=d["doctor"], appointment_date=d["appointment_date"],
            start_time=d["start_time"], reason=d["reason"], patient_notes=d.get("patient_notes", ""), request=request,
        )
        return Response(self.get_serializer(appt).data, status=status.HTTP_201_CREATED)

    def _transition(self, request, name, fn, **kwargs):
        if request.user.role not in ACTION_ROLES[name]:
            raise PermissionDenied()
        appt = fn(self.get_object(), actor=request.user, request=request, **kwargs)
        return Response(self.get_serializer(scoped_appointments(request.user).get(pk=appt.pk)).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._transition(request, "confirm", svc.confirm_appointment)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        return self._transition(request, "complete", svc.complete_appointment,
                                doctor_notes=request.data.get("doctor_notes", ""))

    @action(detail=True, methods=["post"])
    def no_show(self, request, pk=None):
        return self._transition(request, "no_show", svc.mark_no_show)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, "cancel", svc.cancel_appointment, reason=request.data.get("reason", ""))

    @action(detail=True, methods=["post"])
    def reschedule(self, request, pk=None):
        s = RescheduleSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._transition(request, "reschedule", svc.reschedule_appointment, **s.validated_data)


def _counts(qs):
    c = qs.aggregate(total=Count("id"), **{s.lower(): Count("id", filter=Q(status=s)) for s in Appointment.Status})
    return c


@api_view(["GET"])
def dashboard(request):
    user, today = request.user, timezone.localdate()
    qs = scoped_appointments(user)
    ser = lambda items: AppointmentSerializer(items, many=True).data  # noqa: E731
    data = {"counts": _counts(qs), "today_count": qs.filter(appointment_date=today).count()}
    upcoming = qs.filter(appointment_date__gte=today, status__in=Appointment.ACTIVE).order_by("appointment_date", "start_time")
    today_qs = qs.filter(appointment_date=today).order_by("start_time")

    if user.role == Role.PATIENT:
        nxt = upcoming.first()
        data.update(
            next_appointment=AppointmentSerializer(nxt).data if nxt else None,
            today_appointments=ser(today_qs),
            recent_appointments=ser(qs.order_by("-created_at")[:5]),
        )
    elif user.role == Role.DOCTOR:
        data.update(
            upcoming_count=upcoming.count(),
            total_patients=qs.values("patient").distinct().count(),
            today_schedule=ser(today_qs),
            upcoming_appointments=ser(upcoming.exclude(appointment_date=today)[:5]),
        )
    else:
        data.update(
            total_doctors=Doctor.objects.count(),
            active_doctors=Doctor.objects.filter(user__is_active=True).count(),
            pending_doctors=Doctor.objects.filter(user__is_active=False).count(),
            total_patients=Patient.objects.count(),
            recent_appointments=ser(qs.order_by("-created_at")[:6]),
            today_schedule=ser(today_qs[:8]),
        )
    return Response(data)
