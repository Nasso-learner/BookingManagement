from django.db.models import Q
from rest_framework import serializers, viewsets

from apps.accounts.permissions import IsAdmin

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True, default=None)
    user_name = serializers.CharField(source="user.full_name", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = ["id", "user", "user_email", "user_name", "action", "model_name", "object_id", "description",
                  "ip_address", "created_at"]


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user")
        p = self.request.query_params
        if a := p.get("action"):
            qs = qs.filter(action=a)
        if q := p.get("q"):
            qs = qs.filter(Q(description__icontains=q) | Q(user__email__icontains=q) | Q(object_id=q))
        return qs
