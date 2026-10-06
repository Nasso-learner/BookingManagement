from types import SimpleNamespace
from urllib.parse import quote

import jwt
import requests
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from .api import APIError, NotAuthenticated

DASHBOARDS = {"ADMIN": "/admin/", "DOCTOR": "/doctor/", "PATIENT": "/patient/"}


def decode_access(token):
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SIGNING_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None
    return payload if payload.get("token_type") == "access" else None


def _cookie(response, name, value, max_age):
    response.set_cookie(name, value, max_age=max_age, httponly=True, secure=settings.JWT_COOKIE_SECURE,
                        samesite=settings.JWT_COOKIE_SAMESITE, path="/")


def set_auth_cookies(response, access, refresh=None, remember=True):
    _cookie(response, settings.JWT_ACCESS_COOKIE, access, settings.JWT_ACCESS_MAX_AGE)
    if refresh:
        # Without "remember me" the refresh cookie dies with the browser session.
        _cookie(response, settings.JWT_REFRESH_COOKIE, refresh, settings.JWT_REFRESH_MAX_AGE if remember else None)


def clear_auth_cookies(response):
    for name in (settings.JWT_ACCESS_COOKIE, settings.JWT_REFRESH_COOKIE):
        response.delete_cookie(name, path="/", samesite=settings.JWT_COOKIE_SAMESITE)


def refresh_access(refresh):
    try:
        r = requests.post(f"{settings.API_BASE_URL}/auth/refresh/", json={"refresh": refresh}, timeout=settings.API_TIMEOUT)
        return r.json().get("access") if r.ok else None
    except requests.RequestException:
        return None


class JWTAuthMiddleware:
    """Reads JWTs from HttpOnly cookies, transparently refreshes an expired access token,
    and exposes request.jwt_user / request.access_token to views."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        access = request.COOKIES.get(settings.JWT_ACCESS_COOKIE)
        refresh = request.COOKIES.get(settings.JWT_REFRESH_COOKIE)
        payload, new_access = decode_access(access), None
        if payload is None and refresh:
            new_access = refresh_access(refresh)
            payload = decode_access(new_access)
        request.access_token = (new_access or access) if payload else None
        request.jwt_user = None
        if payload:
            name = payload.get("name") or payload.get("email", "")
            request.jwt_user = SimpleNamespace(
                id=payload["user_id"], role=payload.get("role"), name=name, email=payload.get("email", ""),
                initials="".join(p[0] for p in name.split()[:2]).upper(), dashboard=DASHBOARDS.get(payload.get("role"), "/"),
            )
        request.clear_auth = bool(refresh and payload is None)  # refresh token dead -> drop cookies

        response = self.get_response(request)

        if request.clear_auth:
            clear_auth_cookies(response)
        elif new_access:
            set_auth_cookies(response, new_access)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, NotAuthenticated):
            request.clear_auth = True
            messages.info(request, "Your session has expired. Please log in again.")
            return redirect(f"/login/?next={quote(request.get_full_path())}")
        if isinstance(exception, APIError):  # unhandled API failure (e.g. API down) -> friendly page
            status = 503 if exception.status >= 500 else 400
            return render(request, f"errors/{500 if status == 503 else 400}.html", {"message": exception.message}, status=status)
        return None
