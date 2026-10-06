from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsAdmin, IsAdminOrDoctor, IsDoctor
from apps.appointments.services.booking_service import available_slots
from apps.audit_logs.models import audit

from .models import Doctor, DoctorAvailability
from .serializers import AvailabilitySerializer, DoctorSerializer


def _parse_date(value):
    try:
        return date.fromisoformat(value or "")
    except ValueError:
        raise ValidationError({"date": "Use YYYY-MM-DD."})


class DoctorViewSet(viewsets.ModelViewSet):
    serializer_class = DoctorSerializer
    http_method_names = ["get", "post", "patch", "put"]  # no delete: deactivate instead (keeps history)

    def get_queryset(self):
        qs = Doctor.objects.select_related("user", "department").prefetch_related("availabilities")
        p = self.request.query_params
        if self.request.user.role != Role.ADMIN:
            qs = qs.filter(user__is_active=True)
        if q := p.get("q"):
            qs = qs.filter(
                Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
                | Q(specialization__icontains=q) | Q(department__name__icontains=q) | Q(city__icontains=q)
                | Q(doctor_code__icontains=q)
            )
        for param, lookup in [("specialization", "specialization__iexact"), ("department", "department_id"),
                              ("city", "city__iexact"), ("min_fee", "consultation_fee__gte"),
                              ("max_fee", "consultation_fee__lte")]:
            if value := p.get(param):
                qs = qs.filter(**{lookup: value})
        if p.get("available") in ("1", "true"):
            qs = qs.filter(is_available=True, availabilities__is_active=True).distinct()
        if p.get("is_active") in ("0", "1"):
            qs = qs.filter(user__is_active=p["is_active"] == "1")
        return qs

    def get_permissions(self):
        if self.action in ("list", "retrieve", "slots", "dates", "filters"):
            return [IsAuthenticated()]
        if self.action == "me":
            return [IsDoctor()]
        return [IsAdmin()]

    def perform_create(self, serializer):
        doctor = serializer.save()
        audit(self.request.user, "DOCTOR_CREATED", doctor, f"Created {doctor} ({doctor.doctor_code})", self.request)

    def perform_update(self, serializer):
        doctor = serializer.save()
        audit(self.request.user, "DOCTOR_UPDATED", doctor, f"Updated {doctor}", self.request)

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        doctor = request.user.doctor
        if request.method == "GET":
            return Response(self.get_serializer(doctor).data)
        serializer = DoctorSerializer(doctor, data=request.data, partial=True,
                                      context={**self.get_serializer_context(), "self_edit": True})
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    @action(detail=False)
    def filters(self, request):
        """Distinct values for the search filter dropdowns."""
        qs = Doctor.objects.filter(user__is_active=True)
        values = lambda f: sorted(v for v in qs.values_list(f, flat=True).distinct() if v)  # noqa: E731
        return Response({"specializations": values("specialization"), "cities": values("city")})

    @action(detail=True)
    def slots(self, request, pk=None):
        day = _parse_date(request.query_params.get("date"))
        slots = available_slots(self.get_object(), day)
        return Response({"date": day, "slots": [{"start": s.strftime("%H:%M"), "end": e.strftime("%H:%M"),
                                                 "label": s.strftime("%I:%M %p")} for s, e in slots]})

    @action(detail=True)
    def dates(self, request, pk=None):
        """Next N days with their number of free slots."""
        doctor = self.get_object()
        days = min(int(request.query_params.get("days", 14)), 60)
        today = timezone.localdate()
        result = []
        for i in range(days):
            day = today + timedelta(days=i)
            result.append({"date": day, "weekday": day.strftime("%a"), "free": len(available_slots(doctor, day))})
        return Response(result)


class AvailabilityViewSet(viewsets.ModelViewSet):
    serializer_class = AvailabilitySerializer
    permission_classes = [IsAdminOrDoctor]
    pagination_class = None

    def get_queryset(self):
        qs = DoctorAvailability.objects.select_related("doctor__user")
        if self.request.user.role == Role.DOCTOR:
            return qs.filter(doctor__user=self.request.user)
        if doctor := self.request.query_params.get("doctor"):
            qs = qs.filter(doctor_id=doctor)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        if self.request.user.is_authenticated and self.request.user.role == Role.DOCTOR:
            ctx["doctor"] = self.request.user.doctor
        return ctx

    def perform_create(self, serializer):
        obj = serializer.save()
        audit(self.request.user, "SCHEDULE_CREATED", obj, str(obj), self.request)

    def perform_update(self, serializer):
        obj = serializer.save()
        audit(self.request.user, "SCHEDULE_UPDATED", obj, str(obj), self.request)

    def perform_destroy(self, instance):
        audit(self.request.user, "SCHEDULE_DELETED", instance, str(instance), self.request)
        instance.delete()
