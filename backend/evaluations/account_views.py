"""
Accounts: register, sign in, sign out, change password, and (admin) manage users.

Rules:
  * The FIRST account ever created becomes an administrator.
  * Every later account waits for an administrator to approve it (and to choose its role).
  * 5 wrong passwords lock the account for 15 minutes.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from .auth import ADMIN, has_role, issue_token
from .models import AuthToken, Profile
from .services.audit import log_event
from .views import BadRequest, get_or_404

User = get_user_model()


class AuthThrottle(AnonRateThrottle):
    scope = "auth"


def user_payload(user):
    profile = user.profile
    return {
        "id": user.id,
        "email": user.email,
        "name": user.first_name,
        "role": profile.role,
        "is_approved": profile.is_approved,
        "is_active": user.is_active,
        "date_joined": user.date_joined,
    }


def _check_password(password, user=None):
    try:
        validate_password(password, user)
    except ValidationError as error:
        raise BadRequest(" ".join(error.messages))


@api_view(["POST"])
@parser_classes([JSONParser])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def register(request):
    email = str(request.data.get("email", "")).strip().lower()
    password = str(request.data.get("password", ""))
    name = str(request.data.get("name", "")).strip()[:150]
    try:
        validate_email(email)
    except ValidationError:
        raise BadRequest("Enter a valid email address.")
    if not name:
        raise BadRequest("Enter your name.")
    _check_password(password)

    with transaction.atomic():
        if User.objects.filter(username=email).exists():
            raise BadRequest("An account with this email already exists.")
        first = not User.objects.exists()
        user = User.objects.create_user(username=email, email=email, password=password, first_name=name)
        Profile.objects.create(
            user=user,
            role=Profile.Role.ADMIN if first else Profile.Role.REVIEWER,
            is_approved=first,
        )
    log_event(request, "user.register", "user", user.id, {"first_admin": first}, actor=user)
    return Response(
        {"status": "active" if first else "pending",
         "message": "Administrator account created. You can sign in."
         if first else "Account created. An administrator must approve it before you can sign in."},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@parser_classes([JSONParser])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([AuthThrottle])
def login(request):
    email = str(request.data.get("email", "")).strip().lower()
    password = str(request.data.get("password", ""))
    generic = Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

    user = User.objects.filter(username=email).select_related("profile").first()
    if user is None or not hasattr(user, "profile"):
        User().set_password(password)  # spend similar time, so timing does not reveal accounts
        return generic
    profile = user.profile

    now = timezone.now()
    if profile.locked_until and profile.locked_until > now:
        log_event(request, "user.login_blocked", "user", user.id, {"reason": "locked"}, actor=user)
        return Response({"detail": "Too many attempts. Try again in a few minutes."},
                        status=status.HTTP_429_TOO_MANY_REQUESTS)

    if not user.check_password(password):
        profile.failed_logins += 1
        if profile.failed_logins >= settings.MAX_FAILED_LOGINS:
            profile.locked_until = now + timedelta(minutes=settings.LOCKOUT_MINUTES)
            profile.failed_logins = 0
        profile.save(update_fields=["failed_logins", "locked_until"])
        log_event(request, "user.login_failed", "user", user.id, {}, actor=user)
        return generic

    if not user.is_active or not profile.is_approved:
        return Response({"detail": "Your account is not active yet. Ask an administrator to approve it."},
                        status=status.HTTP_403_FORBIDDEN)

    profile.failed_logins = 0
    profile.locked_until = None
    profile.save(update_fields=["failed_logins", "locked_until"])
    token, expires = issue_token(user)
    log_event(request, "user.login", "user", user.id, {}, actor=user)
    return Response({"token": token, "expires_at": expires, "user": user_payload(user)})


@api_view(["POST"])
def logout(request):
    if isinstance(request.auth, AuthToken):
        request.auth.delete()
    log_event(request, "user.logout", "user", request.user.id)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def me(request):
    return Response(user_payload(request.user))


@api_view(["POST"])
@parser_classes([JSONParser])
def change_password(request):
    current = str(request.data.get("current_password", ""))
    new = str(request.data.get("new_password", ""))
    if not request.user.check_password(current):
        raise BadRequest("Your current password is incorrect.")
    _check_password(new, request.user)
    request.user.set_password(new)
    request.user.save(update_fields=["password"])
    # Sign out every other session.
    AuthToken.objects.filter(user=request.user).exclude(pk=getattr(request.auth, "pk", None)).delete()
    log_event(request, "user.password_change", "user", request.user.id)
    return Response({"detail": "Password updated."})


@api_view(["GET"])
@permission_classes([has_role(ADMIN)])
def users(request):
    rows = User.objects.select_related("profile").order_by("date_joined")
    return Response([user_payload(user) for user in rows if hasattr(user, "profile")])


@api_view(["PATCH"])
@parser_classes([JSONParser])
@permission_classes([has_role(ADMIN)])
def user_detail(request, user_id):
    """Admin: change a user's role, approve them, or deactivate them."""
    user = get_or_404(User, user_id, "User")
    profile = user.profile
    changes = {}

    if "role" in request.data:
        if request.data["role"] not in Profile.Role.values:
            raise BadRequest("Unknown role.")
        changes["role"] = request.data["role"]
    for flag in ("is_approved", "is_active"):
        if flag in request.data:
            if not isinstance(request.data[flag], bool):
                raise BadRequest(f"{flag} must be true or false.")
            changes[flag] = request.data[flag]

    # Never remove the last working administrator (including yourself).
    removes_admin = (
        profile.role == ADMIN
        and (changes.get("role", ADMIN) != ADMIN
             or changes.get("is_approved", True) is False
             or changes.get("is_active", True) is False)
    )
    if removes_admin:
        others = Profile.objects.filter(role=ADMIN, is_approved=True, user__is_active=True).exclude(pk=profile.pk)
        if not others.exists():
            raise BadRequest("There must be at least one active administrator.")

    with transaction.atomic():
        if "role" in changes:
            profile.role = changes["role"]
        if "is_approved" in changes:
            profile.is_approved = changes["is_approved"]
        profile.save()
        if "is_active" in changes:
            user.is_active = changes["is_active"]
            user.save(update_fields=["is_active"])
        if changes.get("is_active") is False or changes.get("is_approved") is False or "role" in changes:
            AuthToken.objects.filter(user=user).delete()  # force a fresh sign-in
    log_event(request, "user.update", "user", user.id, changes)
    return Response(user_payload(user))
