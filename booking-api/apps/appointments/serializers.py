from rest_framework import serializers

from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    patient = serializers.SerializerMethodField()
    doctor = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    cancelled_by_name = serializers.CharField(source="cancelled_by.full_name", read_only=True, default=None)
    rescheduled_from_number = serializers.CharField(source="rescheduled_from.appointment_number", read_only=True, default=None)
    rescheduled_to = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id", "appointment_number", "status", "status_display", "booking_source", "patient", "doctor",
            "department", "appointment_date", "start_time", "end_time", "reason", "patient_notes",
            "doctor_notes", "cancellation_reason", "cancelled_by_name", "cancelled_at", "completed_at",
            "rescheduled_from", "rescheduled_from_number", "rescheduled_to", "reschedule_reason",
            "created_at", "updated_at",
        ]

    def get_patient(self, a):
        p, u = a.patient, a.patient.user
        return {"id": p.id, "patient_code": p.patient_code, "name": u.full_name, "email": u.email,
                "phone_number": u.phone_number, "gender": p.gender, "date_of_birth": p.date_of_birth,
                "blood_group": p.blood_group}

    def get_doctor(self, a):
        d = a.doctor
        return {"id": d.id, "doctor_code": d.doctor_code, "name": d.user.full_name, "specialization": d.specialization,
                "profile_image": d.profile_image.name or None, "consultation_fee": str(d.consultation_fee),
                "phone_number": d.user.phone_number, "email": d.user.email}

    def get_department(self, a):
        return {"id": a.department_id, "name": a.department.name} if a.department_id else None

    def get_rescheduled_to(self, a):
        nxt = getattr(a, "rescheduled_to", None)
        return {"id": nxt.id, "appointment_number": nxt.appointment_number} if nxt else None


class BookSerializer(serializers.Serializer):
    doctor = serializers.IntegerField()
    patient = serializers.IntegerField(required=False)  # admin only
    appointment_date = serializers.DateField()
    start_time = serializers.TimeField()
    reason = serializers.CharField(max_length=2000)
    patient_notes = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class RescheduleSerializer(serializers.Serializer):
    appointment_date = serializers.DateField()
    start_time = serializers.TimeField()
    reason = serializers.CharField(max_length=2000)
