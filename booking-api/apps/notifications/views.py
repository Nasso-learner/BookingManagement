from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    appointment_number = serializers.CharField(source="appointment.appointment_number", read_only=True, default=None)

    class Meta:
        model = Notification
        fields = ["id", "notification_type", "title", "message", "is_read", "appointment", "appointment_number", "created_at"]


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user).select_related("appointment")
        if self.request.query_params.get("unread") == "1":
            qs = qs.filter(is_read=False)
        return qs

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["unread_count"] = Notification.objects.filter(user=request.user, is_read=False).count()
        return response

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        self.get_queryset().filter(pk=pk).update(is_read=True)
        return Response({"ok": True})

    @action(detail=False, methods=["post"])
    def read_all(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"ok": True})
