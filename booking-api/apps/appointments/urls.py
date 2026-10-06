from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AppointmentViewSet, dashboard

router = DefaultRouter()
router.register("appointments", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("dashboard/", dashboard, name="dashboard"),
    *router.urls,
]
