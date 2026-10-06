from django.contrib.auth import password_validation
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.audit_logs.models import audit

from .models import Role, User


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    profile_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name", "phone_number", "role",
                  "is_active", "date_joined", "last_login", "profile_id"]
        read_only_fields = ["id", "email", "role", "is_active", "date_joined", "last_login"]

    def get_profile_id(self, user):
        profile = getattr(user, "doctor", None) if user.role == Role.DOCTOR else getattr(user, "patient", None)
        return profile.pk if profile else None


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["name"] = user.full_name
        token["email"] = user.email
        return token

    def validate(self, attrs):
        attrs["email"] = attrs.get("email", "").lower()
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        audit(self.user, "LOGIN", self.user, "User logged in", self.context.get("request"))
        return data


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    # ADMIN is deliberately not a choice: admins are created by other admins / createsuperuser.
    role = serializers.ChoiceField(choices=[Role.PATIENT, Role.DOCTOR], default=Role.PATIENT)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        password_validation.validate_password(attrs["password"], User(email=attrs["email"], first_name=attrs["first_name"]))
        return attrs

    @transaction.atomic
    def create(self, data):
        from apps.doctors.models import Doctor
        from apps.patients.models import Patient

        role = data.pop("role")
        # Doctors self-register as inactive and need admin approval before they can log in.
        user = User.objects.create_user(role=role, is_active=role == Role.PATIENT, **data)
        (Patient if role == Role.PATIENT else Doctor).objects.create(user=user)
        return user


class PasswordResetSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(attrs["uid"])))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user is None or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "This reset link is invalid or has expired."})
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        password_validation.validate_password(attrs["password"], user)
        attrs["user"] = user
        return attrs
