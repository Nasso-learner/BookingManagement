from django.urls import path

from .views import report_delete, report_form, report_list, report_preview, report_view

urlpatterns = [
    path("", report_list, name="reports"),
    path("new/", report_form, name="report_new"),
    path("preview/", report_preview, name="report_preview"),
    path("<int:pk>/", report_view, name="report_view"),
    path("<int:pk>/edit/", report_form, name="report_edit"),
    path("<int:pk>/delete/", report_delete, name="report_delete"),
]
