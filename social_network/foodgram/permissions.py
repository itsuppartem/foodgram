from rest_framework import permissions
from typing import Any


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission class
    Name of the class reflects the essence
    """
    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        return (
            request.method in permissions.SAFE_METHODS
            or obj.author == request.user
        )


class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        return (
            request.method in permissions.SAFE_METHODS
            or obj.author == request.user
        )
