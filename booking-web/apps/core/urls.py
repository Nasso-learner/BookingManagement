from django.urls import path

from .views import doctor_slots_json, home, notification_read, notifications_json, notifications_read_all

urlpatterns = [
    path("", home, name="home"),
    path("ajax/notifications/", notifications_json, name="notifications"),
    path("ajax/notifications/read-all/", notifications_read_all, name="notifications_read_all"),
    path("ajax/notifications/<int:pk>/read/", notification_read, name="notification_read"),
    path("ajax/doctors/<int:pk>/slots/", doctor_slots_json, name="doctor_slots"),
]
