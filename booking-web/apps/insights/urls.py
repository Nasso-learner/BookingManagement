from django.urls import path

from .views import dashboard, data

urlpatterns = [
    path("", dashboard, name="insights"),
    path("data/", data, name="insights_data"),
]
