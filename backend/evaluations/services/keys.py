"""
Managed encryption keys (envelope encryption).

  master key (KEK)   lives ONLY in the environment (KEY_ENCRYPTION_KEY). Never in the DB.
  data keys          random Fernet keys, stored in the database WRAPPED by the master key.
  ciphertext         "v<version>:<fernet token>", so every record says which key made it.

Rotation:
  rotate_data_key()   creates a new active data key (old ones stay, to read old data)
  reencrypt_all()     moves every stored identity onto the active key
  rewrap_keys()       re-wraps data keys after you change the master key.
                      KEY_ENCRYPTION_KEY accepts "new,old": the first encrypts, all decrypt.

Data written before this feature has no "v<n>:" prefix and is read with the legacy key
(PII_ENCRYPTION_KEY) until reencrypt_all() moves it.

To use a cloud KMS instead, replace _kek() with a client that wraps/unwraps with it.
"""
import json

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import CandidateApplication, EncryptionKey


def _kek():
    keys = [k.strip() for k in str(settings.KEY_ENCRYPTION_KEY).split(",") if k.strip()]
    return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])


def _legacy():
    return Fernet(settings.PII_ENCRYPTION_KEY)


def _new_key_row():
    last = EncryptionKey.objects.order_by("-version").first()
    return EncryptionKey.objects.create(
        version=(last.version + 1) if last else 1,
        wrapped_key=_kek().encrypt(Fernet.generate_key()).decode(),
        status=EncryptionKey.Status.ACTIVE,
    )


@transaction.atomic
def rotate_data_key():
    """Retire the active key and create a new active one."""
    EncryptionKey.objects.filter(status=EncryptionKey.Status.ACTIVE).update(
        status=EncryptionKey.Status.RETIRED, retired_at=timezone.now()
    )
    return _new_key_row()


def active_key():
    key = EncryptionKey.objects.filter(status=EncryptionKey.Status.ACTIVE).order_by("-version").first()
    return key or _new_key_row()


def _fernet_for(key_row):
    return Fernet(_kek().decrypt(key_row.wrapped_key.encode()))


def encrypt_data(data):
    key = active_key()
    token = _fernet_for(key).encrypt(json.dumps(data).encode()).decode()
    return f"v{key.version}:{token}"


def key_version_of(value):
    """Which key made this ciphertext? 0 = legacy, None = nothing stored."""
    if not value:
        return None
    if value.startswith("v") and ":" in value:
        head = value.split(":", 1)[0][1:]
        if head.isdigit():
            return int(head)
    return 0


def decrypt_data(value):
    if not value:
        return {}
    version = key_version_of(value)
    if version == 0:
        return json.loads(_legacy().decrypt(value.encode()))
    key_row = EncryptionKey.objects.get(version=version)
    return json.loads(_fernet_for(key_row).decrypt(value.split(":", 1)[1].encode()))


def reencrypt_all():
    """Move every stored identity to the active key. Returns how many were moved."""
    active = active_key()
    moved = 0
    for application in CandidateApplication.objects.exclude(encrypted_pii="").iterator():
        if key_version_of(application.encrypted_pii) == active.version:
            continue
        application.encrypted_pii = encrypt_data(decrypt_data(application.encrypted_pii))
        application.save(update_fields=["encrypted_pii"])
        moved += 1
    return moved


def rewrap_keys():
    """Re-wrap all data keys with the FIRST master key. Run after rotating the master key."""
    kek = _kek()
    count = 0
    for row in EncryptionKey.objects.all():
        row.wrapped_key = kek.rotate(row.wrapped_key.encode()).decode()
        row.save(update_fields=["wrapped_key"])
        count += 1
    return count


def key_report():
    """Key versions and how many stored identities use each (for the admin page)."""
    usage = {}
    for value in CandidateApplication.objects.exclude(encrypted_pii="").values_list("encrypted_pii", flat=True):
        version = key_version_of(value)
        usage[version] = usage.get(version, 0) + 1
    keys = [
        {
            "version": row.version,
            "status": row.status,
            "created_at": row.created_at,
            "retired_at": row.retired_at,
            "records": usage.get(row.version, 0),
        }
        for row in EncryptionKey.objects.all()
    ]
    return {
        "keys": keys,
        "legacy_records": usage.get(0, 0),
        "master_key_configured": settings.KEK_IS_EXPLICIT,
    }
