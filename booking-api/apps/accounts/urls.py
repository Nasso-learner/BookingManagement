from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import ForgotPasswordView, LoginView, LogoutView, MeView, RegisterView, ResetPasswordView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot_password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset_password"),
    path("me/", MeView.as_view(), name="me"),
]
