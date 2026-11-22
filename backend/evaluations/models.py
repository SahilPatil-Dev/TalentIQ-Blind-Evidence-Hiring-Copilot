"""
Database tables (Django "models").

There are only two:
  JobRole              - a position you are hiring for, with its scoring rubric
  CandidateApplication - one uploaded resume + the AI evaluation of it
"""
from django.conf import settings
from django.db import models


class JobRole(models.Model):
    title = models.CharField(max_length=160)
    department = models.CharField(max_length=120, blank=True)
    # Free-text description of what a strong candidate looks like.
    rubric_markdown = models.TextField(blank=True)
    # The scoring rubric as a list, e.g.
    # [{"name": "Python backend", "weight": 40, "keywords": ["Python", "Django"]}]
    # Weights must add up to 100 (checked in serializers.py).
    rubric_criteria = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class CandidateApplication(models.Model):
    class Status(models.TextChoices):
        PROCESSING = "PROCESSING", "Processing"
        NEEDS_REVIEW = "NEEDS_REVIEW", "Needs review"  # waiting for the recruiter
        SHORTLISTED = "SHORTLISTED", "Shortlisted"     # identity gets revealed
        REJECTED = "REJECTED", "Rejected"

    job = models.ForeignKey(
        JobRole, on_delete=models.CASCADE, related_name="applications"
    )
    # The resume text AFTER names/emails/etc. were removed. Only this is ever
    # sent to the AI model.
    redacted_text = models.TextField()
    # The removed identity details, stored encrypted. Only decrypted after the
    # recruiter shortlists the candidate.
    encrypted_pii = models.TextField(blank=True)
    # One entry per rubric criterion: {criterion, weight, status, quote}
    evidence_matrix = models.JSONField(default=list)
    final_score = models.PositiveSmallIntegerField(default=0)  # 0-100
    interview_questions = models.JSONField(default=list)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PROCESSING
    )
    # The steps the evaluation flow went through (shown in the UI).
    workflow_trace = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    # Human oversight: who decided, and the written reason they gave.
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decision_reason = models.TextField(blank=True)
    # A legal hold stops automatic and manual deletion (e.g. a dispute).
    legal_hold = models.BooleanField(default=False)

    class Meta:
        # Best score first, so the list is already ranked.
        ordering = ["-final_score", "created_at"]

    def __str__(self):
        return f"Application {self.pk} for {self.job}"


# --------------------------------------------------------------------------
# Accounts and roles
# --------------------------------------------------------------------------
class Profile(models.Model):
    """Extra account data: the user's role and whether an admin approved them."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"      # everything, incl. users, keys, retention
        RECRUITER = "recruiter", "Recruiter"  # create roles, upload, decide, reveal
        REVIEWER = "reviewer", "Reviewer"     # read-only, blind evidence
        AUDITOR = "auditor", "Auditor"        # audit log, fairness, compliance; no candidates

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.REVIEWER)
    is_approved = models.BooleanField(default=False)
    failed_logins = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.email} ({self.role})"


class AuthToken(models.Model):
    """A login session. Only a hash of the token is stored."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="auth_tokens"
    )
    key_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


# --------------------------------------------------------------------------
# Audit log (append-only, hash-chained)
# --------------------------------------------------------------------------
class AuditLog(models.Model):
    """One immutable record of something that happened. See services/audit.py."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor_email = models.CharField(max_length=254, blank=True)  # kept if the user is deleted
    action = models.CharField(max_length=60, db_index=True)
    target_type = models.CharField(max_length=40, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    detail = models.JSONField(default=dict)
    ip_address = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField()
    prev_hash = models.CharField(max_length=64, blank=True)
    entry_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("Audit log entries cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Audit log entries cannot be deleted.")


# --------------------------------------------------------------------------
# Managed encryption keys (envelope encryption)
# --------------------------------------------------------------------------
class EncryptionKey(models.Model):
    """A data key. It is stored WRAPPED (encrypted) by the master key from the environment."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"  # still able to decrypt old data

    version = models.PositiveIntegerField(unique=True)
    wrapped_key = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["version"]


# --------------------------------------------------------------------------
# Retention policy (one row)
# --------------------------------------------------------------------------
class RetentionPolicy(models.Model):
    """How long candidate data may be kept, in days, by outcome."""

    rejected_days = models.PositiveIntegerField(default=30)
    undecided_days = models.PositiveIntegerField(default=90)
    shortlisted_days = models.PositiveIntegerField(default=365)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_run_deleted = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


# --------------------------------------------------------------------------
# Fairness test runs
# --------------------------------------------------------------------------
class FairnessRun(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    passed = models.BooleanField(default=False)
    summary = models.JSONField(default=dict)
    details = models.JSONField(default=list)

    class Meta:
        ordering = ["-created_at"]
