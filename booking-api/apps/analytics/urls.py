from django.urls import path

from .views import embed

urlpatterns = [
    path("analytics/embed/", embed, name="analytics_embed"),
]
