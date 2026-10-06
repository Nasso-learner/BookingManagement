from django.urls import path

from .views import action, analytics, appointment_detail, appointments, availability, dashboard, patients, profile

app_name = "doctor"
urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("analytics/", analytics, name="analytics"),
    path("profile/", profile, name="profile"),
    path("availability/", availability, name="availability"),
    path("appointments/", appointments, name="appointments"),
    path("appointments/<int:pk>/", appointment_detail, name="appointment_detail"),
    path("appointments/<int:pk>/<str:name>/", action, name="action"),
    path("patients/", patients, name="patients"),
]
