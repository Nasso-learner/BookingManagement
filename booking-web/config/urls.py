from django.urls import include, path

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("patient/", include("apps.patients.urls")),
    path("doctor/", include("apps.doctors.urls")),
    path("admin/", include("apps.administration.urls")),
    path("reports/", include("apps.reports.urls")),
]

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
