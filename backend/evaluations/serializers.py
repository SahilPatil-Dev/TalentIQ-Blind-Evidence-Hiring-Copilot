"""
Serializers turn database rows into JSON (and check incoming JSON).

Privacy note: CandidateApplicationSerializer deliberately has NO name/email
fields. The candidate is only ever shown as "Candidate 0007".
"""
from rest_framework import serializers

from .models import CandidateApplication, JobRole


class JobRoleSerializer(serializers.ModelSerializer):
    # Extra computed numbers the dashboard shows next to each role.
    application_count = serializers.SerializerMethodField()
    needs_review_count = serializers.SerializerMethodField()

    class Meta:
        model = JobRole
        fields = [
            "id",
            "title",
            "department",
            "rubric_markdown",
            "rubric_criteria",
            "application_count",
            "needs_review_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_application_count(self, role):
        return role.applications.count()

    def get_needs_review_count(self, role):
        return role.applications.filter(status="NEEDS_REVIEW").count()

    def validate_rubric_criteria(self, criteria):
        """Rubric rules: at least one criterion, each valid, weights total 100."""
        if not isinstance(criteria, list) or not criteria:
            raise serializers.ValidationError("Provide at least one rubric criterion.")

        for item in criteria:
            is_valid = (
                isinstance(item, dict)
                and str(item.get("name", "")).strip()
                and isinstance(item.get("weight"), (int, float))
                and item["weight"] > 0
                and isinstance(item.get("keywords", []), list)
            )
            if not is_valid:
                raise serializers.ValidationError(
                    "Each criterion needs a name, positive weight, and keyword list."
                )

        if sum(item["weight"] for item in criteria) != 100:
            raise serializers.ValidationError("Criterion weights must total 100.")
        return criteria


class CandidateApplicationSerializer(serializers.ModelSerializer):
    # An anonymous label such as "Candidate 0007" instead of a real name.
    candidate_label = serializers.SerializerMethodField()

    class Meta:
        model = CandidateApplication
        fields = [
            "id",
            "job",
            "candidate_label",
            "evidence_matrix",
            "final_score",
            "interview_questions",
            "status",
            "workflow_trace",
            "created_at",
            "decided_at",
            "decision_reason",
            "legal_hold",
        ]
        read_only_fields = fields

    def get_candidate_label(self, application):
        return f"Candidate {application.pk:04d}"
