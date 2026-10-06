from copy import copy

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import Role, User

from .models import Doctor, DoctorAvailability


class ProfileUserMixin(serializers.Serializer):
    """Flattens the related User's fields onto a Doctor/Patient profile serializer."""

    first_name = serializers.CharField(source="user.first_name", max_length=100)
    last_name = serializers.CharField(source="user.last_name", max_length=100)
    email = serializers.EmailField(source="user.email")
    phone_number = serializers.CharField(source="user.phone_number", required=False, allow_blank=True)
    is_active = serializers.BooleanField(source="user.is_active", required=False)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    profile_image = serializers.ImageField(use_url=False, required=False, allow_null=True)

    # Fields the profile owner may not change about themselves.
    admin_only_fields = ["email", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.context.get("self_edit"):
            for name in self.admin_only_fields:
                self.fields[name].read_only = True

    def validate_email(self, value):
        value = value.lower()
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def update(self, instance, data):
        for k, v in data.pop("user", {}).items():
            setattr(instance.user, k, v)
        if password := data.pop("password", None):
            instance.user.set_password(password)
        instance.user.save()
        return super().update(instance, data)


class DoctorSerializer(ProfileUserMixin, serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    available_days = serializers.SerializerMethodField()
    admin_only_fields = ["email", "is_active", "department", "license_number"]

    class Meta:
        model = Doctor
        fields = [
            "id", "doctor_code", "user_id", "first_name", "last_name", "full_name", "email", "phone_number",
            "is_active", "password", "specialization", "department", "department_name", "qualification",
            "experience_years", "consultation_fee", "bio", "profile_image", "license_number", "city",
            "consultation_duration", "is_available", "available_days", "schedule", "created_at", "updated_at",
        ]
        read_only_fields = ["doctor_code", "created_at", "updated_at"]

    schedule = serializers.SerializerMethodField()

    def get_available_days(self, doctor):
        days = sorted({a.day_of_week for a in doctor.availabilities.all() if a.is_active})
        return [DoctorAvailability.Day(d).label for d in days]

    def get_schedule(self, doctor):
        return [{"day": a.get_day_of_week_display(), "start": a.start_time.strftime("%I:%M %p"),
                 "end": a.end_time.strftime("%I:%M %p")}
                for a in sorted(doctor.availabilities.all(), key=lambda a: (a.day_of_week, a.start_time)) if a.is_active]

    def validate(self, attrs):
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError({"password": "An initial password is required."})
        return attrs

    @transaction.atomic
    def create(self, data):
        user_data, password = data.pop("user"), data.pop("password")
        user = User.objects.create_user(role=Role.DOCTOR, password=password, **user_data)
        return Doctor.objects.create(user=user, **data)


class AvailabilitySerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source="get_day_of_week_display", read_only=True)
    doctor_name = serializers.CharField(source="doctor.__str__", read_only=True)

    class Meta:
        model = DoctorAvailability
        fields = ["id", "doctor", "doctor_name", "day_of_week", "day_name", "start_time", "end_time",
                  "slot_duration", "is_active", "created_at", "updated_at"]
        extra_kwargs = {"doctor": {"required": False}}

    def validate(self, attrs):
        if own := self.context.get("doctor"):  # doctors can only manage their own schedule
            attrs["doctor"] = own
        elif not self.instance and not attrs.get("doctor"):
            raise serializers.ValidationError({"doctor": "Doctor is required."})
        obj = copy(self.instance) if self.instance else DoctorAvailability()
        for k, v in attrs.items():
            setattr(obj, k, v)
        try:
            obj.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError({"non_field_errors": e.messages})
        return attrs
