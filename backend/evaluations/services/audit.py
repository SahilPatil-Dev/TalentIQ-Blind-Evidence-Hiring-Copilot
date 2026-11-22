"""
Tamper-evident audit log.

Every important action (login, decision, identity reveal, deletion, key rotation...)
is written as one row. Each row stores the hash of the row before it, so editing or
removing an old row breaks the chain and verify_chain() reports exactly where.

Never put identity values (names, emails...) in `detail`. Log field NAMES only.
"""
import hashlib
import json
import threading

from django.db import transaction
from django.utils import timezone

from ..models import AuditLog

_lock = threading.Lock()  # one worker process: keeps two threads from forking the chain


def client_ip(request):
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", ""))[:64]


def _digest(prev_hash, fields):
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


def _fields(entry_like):
    return {
        "actor_id": entry_like["actor_id"],
        "actor_email": entry_like["actor_email"],
        "action": entry_like["action"],
        "target_type": entry_like["target_type"],
        "target_id": entry_like["target_id"],
        "detail": entry_like["detail"],
        "ip_address": entry_like["ip_address"],
        "created_at": entry_like["created_at"],
    }


def log_event(request, action, target_type="", target_id="", detail=None, actor=None):
    """Append one audit entry. `actor` defaults to the signed-in user of `request`."""
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        actor = user if user is not None and user.is_authenticated else None

    with _lock, transaction.atomic():
        last = AuditLog.objects.order_by("-id").first()
        prev_hash = last.entry_hash if last else ""
        created_at = timezone.now().replace(microsecond=0)
        values = {
            "actor_id": actor.pk if actor else None,
            "actor_email": actor.email if actor else "",
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id),
            "detail": detail or {},
            "ip_address": client_ip(request),
            "created_at": created_at.isoformat(),
        }
        return AuditLog.objects.create(
            actor=actor,
            actor_email=values["actor_email"],
            action=action,
            target_type=target_type,
            target_id=values["target_id"],
            detail=values["detail"],
            ip_address=values["ip_address"],
            created_at=created_at,
            prev_hash=prev_hash,
            entry_hash=_digest(prev_hash, _fields(values)),
        )


def verify_chain():
    """Recompute every hash. Returns {"valid", "checked", "first_bad_id"}."""
    prev_hash = ""
    checked = 0
    for entry in AuditLog.objects.order_by("id").iterator():
        values = {
            "actor_id": entry.actor_id,
            "actor_email": entry.actor_email,
            "action": entry.action,
            "target_type": entry.target_type,
            "target_id": entry.target_id,
            "detail": entry.detail,
            "ip_address": entry.ip_address,
            "created_at": entry.created_at.replace(microsecond=0).isoformat(),
        }
        if entry.prev_hash != prev_hash or entry.entry_hash != _digest(prev_hash, _fields(values)):
            return {"valid": False, "checked": checked, "first_bad_id": entry.id}
        prev_hash = entry.entry_hash
        checked += 1
    return {"valid": True, "checked": checked, "first_bad_id": None}
