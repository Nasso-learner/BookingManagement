from django.contrib import admin

from .models import Doctor, DoctorAvailability

admin.site.register(Doctor)
admin.site.register(DoctorAvailability)
