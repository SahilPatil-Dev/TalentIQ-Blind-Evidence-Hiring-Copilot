"""
Database tables (Django "models").

There are only two:
  JobRole              - a position you are hiring for, with its scoring rubric
  CandidateApplication - one uploaded resume + the AI evaluation of it
"""
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

    class Meta:
        # Best score first, so the list is already ranked.
        ordering = ["-final_score", "created_at"]

    def __str__(self):
        return f"Application {self.pk} for {self.job}"
