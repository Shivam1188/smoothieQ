from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsSuperUserOrReadOnly(BasePermission):
    """
    Allows only superusers to create, update, or delete.
    Read-only access for others.
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True  # Allow GET, HEAD, OPTIONS
        return request.user and request.user.is_superuser