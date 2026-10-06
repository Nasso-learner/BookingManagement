"""Signed Metabase static-embed URLs. The secret never leaves booking-api."""
import time

import jwt
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsAdminOrDoctor


class AnalyticsNotConfigured(APIException):
    status_code = 503
    default_detail = "Analytics is not configured yet. Set METABASE_SECRET_KEY and the dashboard IDs in booking-api/.env."


@api_view(["GET"])
@permission_classes([IsAdminOrDoctor])
def embed(request):
    """Admins get the clinic-wide dashboard; doctors get theirs with doctor_id locked to their own profile."""
    if request.user.role == Role.ADMIN:
        dashboard, params = settings.METABASE_ADMIN_DASHBOARD_ID, {}
    else:
        dashboard, params = settings.METABASE_DOCTOR_DASHBOARD_ID, {"doctor_id": request.user.doctor.pk}
    if not (settings.METABASE_SECRET_KEY and dashboard):
        raise AnalyticsNotConfigured()
    expires = int(time.time()) + settings.METABASE_EMBED_MINUTES * 60
    token = jwt.encode({"resource": {"dashboard": dashboard}, "params": params, "exp": expires},
                       settings.METABASE_SECRET_KEY, algorithm="HS256")
    url = f"{settings.METABASE_SITE_URL.rstrip('/')}/embed/dashboard/{token}#bordered=false&titled=false"
    return Response({"url": url, "expires_at": expires})
