from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core import api
from apps.core.middleware import DASHBOARDS, clear_auth_cookies, set_auth_cookies
from apps.core.views import safe_next


def _login_response(request, tokens, remember):
    home = DASHBOARDS.get(tokens["user"]["role"], "/")
    nxt = safe_next(request, home)
    if any(nxt.startswith(p) for p in DASHBOARDS.values() if p != home):
        nxt = home  # don't follow `next` into another role's area (it would just 403)
    response = redirect(nxt)
    set_auth_cookies(response, tokens["access"], tokens["refresh"], remember)
    return response


def login_view(request):
    if request.jwt_user:
        return redirect(request.jwt_user.dashboard)
    error = None
    if request.method == "POST":
        try:
            tokens = api.post(request, "/auth/login/", {"email": request.POST.get("email", ""),
                                                        "password": request.POST.get("password", "")}, auth=False)
            messages.success(request, f"Welcome back, {tokens['user']['first_name']}!")
            return _login_response(request, tokens, remember=bool(request.POST.get("remember")))
        except api.APIError as e:
            error = "Invalid email or password, or your account is not active yet." if e.status == 401 else e.message
    return render(request, "auth/login.html", {"error": error, "email": request.POST.get("email", "")})


def register_view(request):
    if request.jwt_user:
        return redirect(request.jwt_user.dashboard)
    errors = {}
    if request.method == "POST":
        fields = ("first_name", "last_name", "email", "phone_number", "password", "confirm_password", "role")
        data = {k: request.POST.get(k, "") for k in fields}
        data["role"] = "DOCTOR" if data["role"] == "DOCTOR" else "PATIENT"  # never ADMIN
        try:
            api.post(request, "/auth/register/", data, auth=False)
            if data["role"] == "DOCTOR":
                messages.info(request, "Thanks! Your doctor account is pending admin approval. "
                                       "You'll be able to log in once it's approved.")
                return redirect("/login/")
            tokens = api.post(request, "/auth/login/", {"email": data["email"], "password": data["password"]}, auth=False)
            messages.success(request, "Your account is ready. Welcome to MediBook!")
            return _login_response(request, tokens, remember=False)
        except api.APIError as e:
            errors = e.errors
    return render(request, "auth/register.html", {"errors": errors, "form": request.POST})


def forgot_password_view(request):
    sent = False
    if request.method == "POST":
        try:
            api.post(request, "/auth/forgot-password/", {"email": request.POST.get("email", "")}, auth=False)
            sent = True
        except api.APIError as e:
            messages.error(request, e.message)
    return render(request, "auth/forgot_password.html", {"sent": sent})


def reset_password_view(request):
    uid, token = request.GET.get("uid", ""), request.GET.get("token", "")
    errors = {}
    if request.method == "POST":
        try:
            api.post(request, "/auth/reset-password/", {
                "uid": uid, "token": token, "password": request.POST.get("password", ""),
                "confirm_password": request.POST.get("confirm_password", ""),
            }, auth=False)
            messages.success(request, "Your password has been reset. Please log in.")
            return redirect("/login/")
        except api.APIError as e:
            errors = e.errors
    return render(request, "auth/reset_password.html", {"errors": errors, "valid_link": bool(uid and token)})


@require_POST
def logout_view(request):
    refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
    if refresh:
        try:
            api.post(request, "/auth/logout/", {"refresh": refresh}, auth=False)
        except api.APIError:
            pass  # cookies are cleared regardless
    response = redirect("/login/")
    clear_auth_cookies(response)
    request.clear_auth = True
    messages.info(request, "You have been signed out.")
    return response
