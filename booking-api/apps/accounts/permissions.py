from rest_framework.permissions import BasePermission

from .models import Role


def HasRole(*roles):
    class _HasRole(BasePermission):
        message = "You do not have permission to perform this action."

        def has_permission(self, request, view):
            return bool(request.user and request.user.is_authenticated and request.user.role in roles)

    return _HasRole


IsAdmin = HasRole(Role.ADMIN)
IsDoctor = HasRole(Role.DOCTOR)
IsPatient = HasRole(Role.PATIENT)
IsAdminOrDoctor = HasRole(Role.ADMIN, Role.DOCTOR)
