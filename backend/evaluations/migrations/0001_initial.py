from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="JobRole",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=160)),
                ("department", models.CharField(blank=True, max_length=120)),
                ("rubric_markdown", models.TextField(blank=True)),
                ("rubric_criteria", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="CandidateApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("redacted_text", models.TextField()),
                ("encrypted_pii", models.TextField(blank=True)),
                ("evidence_matrix", models.JSONField(default=list)),
                ("final_score", models.PositiveSmallIntegerField(default=0)),
                ("interview_questions", models.JSONField(default=list)),
                ("status", models.CharField(choices=[("PROCESSING", "Processing"), ("NEEDS_REVIEW", "Needs review"), ("SHORTLISTED", "Shortlisted"), ("REJECTED", "Rejected")], default="PROCESSING", max_length=20)),
                ("workflow_trace", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="applications", to="evaluations.jobrole")),
            ],
            options={"ordering": ["-final_score", "created_at"]},
        ),
    ]
