from django.urls import path

from .views import (
    analytics,
    appointment_action_view,
    appointment_detail,
    appointment_reschedule,
    appointments,
    audit_logs,
    dashboard,
    departments,
    doctor_form,
    doctor_toggle,
    doctors,
    patient_toggle,
    patients,
    schedules,
)

app_name = "administration"
urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("analytics/", analytics, name="analytics"),
    path("doctors/", doctors, name="doctors"),
    path("doctors/new/", doctor_form, name="doctor_new"),
    path("doctors/<int:pk>/edit/", doctor_form, name="doctor_edit"),
    path("doctors/<int:pk>/toggle/", doctor_toggle, name="doctor_toggle"),
    path("patients/", patients, name="patients"),
    path("patients/<int:pk>/toggle/", patient_toggle, name="patient_toggle"),
    path("departments/", departments, name="departments"),
    path("appointments/", appointments, name="appointments"),
    path("appointments/<int:pk>/", appointment_detail, name="appointment_detail"),
    path("appointments/<int:pk>/reschedule/", appointment_reschedule, name="appointment_reschedule"),
    path("appointments/<int:pk>/<str:name>/", appointment_action_view, name="appointment_action"),
    path("schedules/", schedules, name="schedules"),
    path("audit-logs/", audit_logs, name="audit_logs"),
]
