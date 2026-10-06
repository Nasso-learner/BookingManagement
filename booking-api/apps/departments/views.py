from django.db.models import Count, ProtectedError, Q
from rest_framework import serializers, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsAdmin

from .models import Department


class DepartmentSerializer(serializers.ModelSerializer):
    doctor_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "code", "description", "is_active", "doctor_count", "created_at", "updated_at"]

    def validate_code(self, value):
        return value.upper()


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_queryset(self):
        qs = Department.objects.annotate(doctor_count=Count("doctors", filter=Q(doctors__user__is_active=True)))
        if self.request.user.role != Role.ADMIN:
            qs = qs.filter(is_active=True)
        if q := self.request.query_params.get("q"):
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        return qs

    def get_permissions(self):
        return [IsAuthenticated()] if self.action in ("list", "retrieve") else [IsAdmin()]

    def paginate_queryset(self, queryset):
        # ?all=1 returns an unpaginated list (used for dropdowns).
        return None if self.request.query_params.get("all") else super().paginate_queryset(queryset)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({"detail": "Department has doctors or appointments; deactivate it instead."},
                            status=status.HTTP_400_BAD_REQUEST)
