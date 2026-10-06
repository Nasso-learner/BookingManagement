from functools import wraps
from urllib.parse import quote

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def login_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.jwt_user:
            return redirect(f"/login/?next={quote(request.get_full_path())}")
        return view(request, *args, **kwargs)

    return wrapper


def role_required(*roles):
    """403 unless the logged-in user has one of `roles`. Implies login_required."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.jwt_user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return login_required(wrapper)

    return decorator
