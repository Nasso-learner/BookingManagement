from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsAdmin, IsAdminOrDoctor
from apps.audit_logs.models import audit

from . import engine
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    chart_type_display = serializers.CharField(source="get_chart_type_display", read_only=True)
    source_display = serializers.CharField(source="get_source_display", read_only=True)

    class Meta:
        model = Report
        fields = ["id", "title", "description", "source", "source_display", "sql", "chart_type", "chart_type_display",
                  "x_column", "y_columns", "series_column", "doctor_access", "is_active", "created_at", "updated_at"]

    def validate(self, attrs):
        sql = attrs.get("sql", getattr(self.instance, "sql", ""))
        doctor_access = attrs.get("doctor_access", getattr(self.instance, "doctor_access", False))
        attrs["sql"] = engine.validate_sql(sql, doctor_access)
        return attrs

    def to_representation(self, obj):
        data = super().to_representation(obj)
        if self.context["request"].user.role != Role.ADMIN:
            data.pop("sql")  # doctors see the chart, not the query
        return data


def _scope(user):
    """Admins run unscoped; doctors always get their own doctor id bound to :doctor_id."""
    return None if user.role == Role.ADMIN else user.doctor.pk


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Report.objects.all()
        if self.request.user.role != Role.ADMIN:
            qs = qs.filter(doctor_access=True, is_active=True)
        return qs

    def get_permissions(self):
        return [IsAdminOrDoctor()] if self.action in ("list", "retrieve", "run") else [IsAdmin()]

    def perform_create(self, serializer):
        report = serializer.save(created_by=self.request.user)
        audit(self.request.user, "REPORT_CREATED", report, report.title, self.request)

    def perform_update(self, serializer):
        report = serializer.save()
        audit(self.request.user, "REPORT_UPDATED", report, report.title, self.request)

    def perform_destroy(self, instance):
        audit(self.request.user, "REPORT_DELETED", instance, instance.title, self.request)
        instance.delete()

    @action(detail=True)
    def run(self, request, pk=None):
        report = self.get_object()
        try:
            result = engine.run(report.sql, doctor_id=_scope(request.user), source=report.source)
        except ValidationError:
            if request.user.role == Role.ADMIN:
                raise
            raise ValidationError({"detail": "This report could not be generated. Please contact the administrator."})
        audit(request.user, "REPORT_RUN", report, report.title, request)
        return Response(result)

    @action(detail=False, methods=["post"])
    def preview(self, request):
        """Admin-only: run unsaved SQL. Pass doctor_id to preview what a given doctor would see."""
        doctor_id = request.data.get("doctor_id") or None
        engine.validate_sql(request.data.get("sql"), doctor_access=bool(doctor_id))
        source = request.data.get("source") or engine.POSTGRES
        if source not in (engine.POSTGRES, engine.CLICKHOUSE):
            raise ValidationError({"source": "Unknown data source."})
        return Response(engine.run(request.data.get("sql"), doctor_id=int(doctor_id) if doctor_id else None,
                                   source=source))
