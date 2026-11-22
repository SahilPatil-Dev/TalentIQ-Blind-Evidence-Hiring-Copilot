"""
Login sessions and role checks.

Clients send:  Authorization: Bearer <token>
Only a SHA-256 hash of each token is stored, tokens expire (AUTH_TOKEN_TTL_HOURS),
and logging out deletes them.
"""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication
from rest_framework.permissions import BasePermission

from .models import AuthToken, Profile

ADMIN, RECRUITER, REVIEWER, AUDITOR = (
    Profile.Role.ADMIN, Profile.Role.RECRUITER, Profile.Role.REVIEWER, Profile.Role.AUDITOR,
)


def _hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_token(user):
    raw = secrets.token_urlsafe(32)
    expires = timezone.now() + timedelta(hours=settings.AUTH_TOKEN_TTL_HOURS)
    AuthToken.objects.create(user=user, key_hash=_hash(raw), expires_at=expires)
    return raw, expires


class TokenAuthentication(BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "").split()
        if not header or header[0] != self.keyword:
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed("Invalid authorization header.")

        token = (
            AuthToken.objects.select_related("user", "user__profile")
            .filter(key_hash=_hash(header[1]))
            .first()
        )
        if token is None or token.expires_at <= timezone.now():
            raise exceptions.AuthenticationFailed("Your session has expired. Please sign in again.")
        user = token.user
        profile = getattr(user, "profile", None)
        if not user.is_active or profile is None or not profile.is_approved:
            raise exceptions.AuthenticationFailed("This account is not active.")
        return user, token

    def authenticate_header(self, request):
        return self.keyword


def role_of(user):
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


def has_role(*roles):
    """Build a permission class that allows only these roles."""

    class _HasRole(BasePermission):
        message = "Your role is not allowed to do this."

        def has_permission(self, request, view):
            user = request.user
            return bool(user and user.is_authenticated and role_of(user) in roles)

    return _HasRole


# Who can do what (kept in one place, used by views and shown in the README).
CAN_VIEW_CANDIDATES = (ADMIN, RECRUITER, REVIEWER)
CAN_MANAGE_HIRING = (ADMIN, RECRUITER)
CAN_SEE_GOVERNANCE = (ADMIN, AUDITOR)
