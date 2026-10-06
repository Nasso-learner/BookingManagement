from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/", include("apps.departments.urls")),
    path("api/", include("apps.doctors.urls")),
    path("api/", include("apps.patients.urls")),
    path("api/", include("apps.appointments.urls")),
    path("api/", include("apps.notifications.urls")),
    path("api/", include("apps.audit_logs.urls")),
    path("api/", include("apps.analytics.urls")),
    path("api/", include("apps.reports.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # dev only; serve media via nginx/S3 in prod
