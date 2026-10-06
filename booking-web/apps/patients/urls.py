from django.urls import path

from .views import (
    appointment_detail,
    appointments,
    book,
    book_start,
    cancel,
    dashboard,
    doctor_detail,
    doctors,
    profile,
    reschedule_view,
)

app_name = "patient"
urlpatterns = [
    path("", dashboard, name="dashboard"),
    path("profile/", profile, name="profile"),
    path("doctors/", doctors, name="doctors"),
    path("doctors/<int:pk>/", doctor_detail, name="doctor_detail"),
    path("book/", book_start, name="book_start"),
    path("book/<int:pk>/", book, name="book"),
    path("appointments/", appointments, name="appointments"),
    path("appointments/<int:pk>/", appointment_detail, name="appointment_detail"),
    path("appointments/<int:pk>/cancel/", cancel, name="cancel"),
    path("appointments/<int:pk>/reschedule/", reschedule_view, name="reschedule"),
]
