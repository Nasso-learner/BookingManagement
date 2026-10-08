from django.urls import path

from .views import clinic

urlpatterns = [
    path("insights/clinic/", clinic, name="insights_clinic"),
]
