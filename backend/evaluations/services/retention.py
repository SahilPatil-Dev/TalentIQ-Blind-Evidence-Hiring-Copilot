"""
Retention and deletion.

Candidate data is kept only as long as the policy says, counted from:
  * rejected      -> the decision date
  * not decided   -> the upload date
  * shortlisted   -> the decision date
An application under legal hold is never deleted. Deleting an application removes
the redacted text, the encrypted identity and the evaluation. The audit log keeps
only that a deletion happened (ids and counts, never personal data).
"""
from datetime import timedelta

from django.utils import timezone

from ..models import AuthToken, CandidateApplication, RetentionPolicy
from .audit import log_event

Status = CandidateApplication.Status


def get_policy():
    policy = RetentionPolicy.objects.order_by("id").first()
    return policy or RetentionPolicy.objects.create()


def expiry_date(application, policy):
    """When this application is due for deletion."""
    if application.status == Status.REJECTED:
        return (application.decided_at or application.created_at) + timedelta(days=policy.rejected_days)
    if application.status == Status.SHORTLISTED:
        return (application.decided_at or application.created_at) + timedelta(days=policy.shortlisted_days)
    return application.created_at + timedelta(days=policy.undecided_days)


def find_expired(policy=None, now=None):
    policy = policy or get_policy()
    now = now or timezone.now()
    return [
        application
        for application in CandidateApplication.objects.filter(legal_hold=False)
        if expiry_date(application, policy) <= now
    ]


def enforce(dry_run=False, actor=None, request=None):
    """Delete expired applications and expired login sessions."""
    policy = get_policy()
    expired = find_expired(policy)
    ids = [application.id for application in expired]

    if not dry_run:
        CandidateApplication.objects.filter(id__in=ids).delete()
        AuthToken.objects.filter(expires_at__lte=timezone.now()).delete()
        policy.last_run_at = timezone.now()
        policy.last_run_deleted = len(ids)
        policy.save(update_fields=["last_run_at", "last_run_deleted", "updated_at"])
        log_event(
            request, "retention.run", "retention", policy.id,
            {"deleted": len(ids), "application_ids": ids[:200]}, actor=actor,
        )
    return {"dry_run": dry_run, "deleted": 0 if dry_run else len(ids), "due": len(ids), "application_ids": ids}
