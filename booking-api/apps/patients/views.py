from django.db.models import Count, Max, Q
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsAdmin, IsAdminOrDoctor, IsPatient
from apps.audit_logs.models import audit
from apps.doctors.serializers import ProfileUserMixin

from .models import Patient


class PatientSerializer(ProfileUserMixin, serializers.ModelSerializer):
    appointments_count = serializers.IntegerField(read_only=True, default=None)
    last_visit = serializers.DateField(read_only=True, default=None)

    class Meta:
        model = Patient
        fields = [
            "id", "patient_code", "user_id", "first_name", "last_name", "full_name", "email", "phone_number",
            "is_active", "date_of_birth", "gender", "blood_group", "address", "city", "emergency_contact_name",
            "emergency_contact_phone", "profile_image", "appointments_count", "last_visit", "created_at",
        ]
        read_only_fields = ["patient_code", "created_at"]


class PatientViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin,
                     viewsets.GenericViewSet):
    """Patients are created via public registration. Admins manage; doctors see their own patients."""

    serializer_class = PatientSerializer
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        qs = Patient.objects.select_related("user")
        user = self.request.user
        if user.role == Role.DOCTOR:
            mine = Q(appointments__doctor__user=user)
            qs = qs.filter(mine).annotate(appointments_count=Count("appointments", filter=mine),
                                          last_visit=Max("appointments__appointment_date", filter=mine))
        else:
            qs = qs.annotate(appointments_count=Count("appointments"),
                             last_visit=Max("appointments__appointment_date"))
        if q := self.request.query_params.get("q"):
            qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
                           | Q(user__email__icontains=q) | Q(patient_code__icontains=q)
                           | Q(user__phone_number__icontains=q))
        if (active := self.request.query_params.get("is_active")) in ("0", "1"):
            qs = qs.filter(user__is_active=active == "1")
        return qs.order_by("-created_at")

    def get_permissions(self):
        if self.action == "me":
            return [IsPatient()]
        if self.action in ("list", "retrieve"):
            return [IsAdminOrDoctor()]
        return [IsAdmin()]

    def perform_update(self, serializer):
        patient = serializer.save()
        audit(self.request.user, "PATIENT_UPDATED", patient, f"Updated {patient}", self.request)

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        patient = request.user.patient
        if request.method == "GET":
            return Response(self.get_serializer(patient).data)
        serializer = PatientSerializer(patient, data=request.data, partial=True,
                                       context={**self.get_serializer_context(), "self_edit": True})
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)
