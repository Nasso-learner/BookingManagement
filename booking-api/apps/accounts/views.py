from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.audit_logs.models import audit

from .models import User
from .serializers import LoginSerializer, PasswordResetSerializer, RegisterSerializer, UserSerializer


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_scope = "auth"


class LogoutView(APIView):
    permission_classes = [AllowAny]  # access token may already be expired at logout

    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh", ""))
            user = User.objects.filter(pk=token["user_id"]).first()
            token.blacklist()
            if user:
                audit(user, "LOGOUT", user, "User logged out", request)
        except TokenError:
            pass  # already invalid: logout is idempotent
        return Response(status=status.HTTP_205_RESET_CONTENT)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def perform_create(self, serializer):
        user = serializer.save()
        audit(user, "USER_REGISTERED", user, f"{user.role} registered", self.request)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(UserSerializer(serializer.instance).data, status=status.HTTP_201_CREATED)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        user = User.objects.filter(email__iexact=request.data.get("email", ""), is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.WEB_BASE_URL}/reset-password/?uid={uid}&token={token}"
            send_mail("Reset your MediBook password", f"Reset your password: {link}", None, [user.email])
        # Same response either way so emails can't be enumerated.
        return Response({"detail": "If an account exists for this email, a reset link has been sent."})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["password"])
        user.save(update_fields=["password"])
        audit(user, "PASSWORD_RESET", user, "Password reset via email link", request)
        return Response({"detail": "Password has been reset. You can now log in."})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user
