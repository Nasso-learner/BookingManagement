from django.conf import settings
from django.db import models


class Report(models.Model):
    """A saved SQL query + chart settings. Admins author; doctors may view (scoped to their own data)."""

    class Chart(models.TextChoices):
        TABLE = "TABLE", "Table"
        NUMBER = "NUMBER", "Number (KPI)"
        BAR = "BAR", "Bar"
        STACKED_BAR = "STACKED_BAR", "Stacked bar"
        HBAR = "HBAR", "Horizontal bar"
        LINE = "LINE", "Line"
        AREA = "AREA", "Area"
        PIE = "PIE", "Donut"
        SCATTER = "SCATTER", "Scatter"

    title = models.CharField(max_length=150)
    description = models.CharField(max_length=300, blank=True)
    sql = models.TextField(help_text="One SELECT/WITH statement. Use :doctor_id to scope rows for doctors.")
    chart_type = models.CharField(max_length=12, choices=Chart.choices, default=Chart.BAR)
    x_column = models.CharField(max_length=100, blank=True, help_text="Category / date column (default: first column)")
    y_columns = models.CharField(max_length=300, blank=True, help_text="Comma-separated value columns (default: second column)")
    series_column = models.CharField(max_length=100, blank=True, help_text="Optional column that splits the data into series")
    doctor_access = models.BooleanField(default=False, help_text="Visible to doctors, filtered by :doctor_id")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
