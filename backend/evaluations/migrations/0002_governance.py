import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("evaluations", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="candidateapplication",
            name="decided_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="candidateapplication",
            name="decision_reason",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="candidateapplication",
            name="legal_hold",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(
                    choices=[("admin", "Administrator"), ("recruiter", "Recruiter"),
                             ("reviewer", "Reviewer"), ("auditor", "Auditor")],
                    default="reviewer", max_length=20)),
                ("is_approved", models.BooleanField(default=False)),
                ("failed_logins", models.PositiveSmallIntegerField(default=0)),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("user", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE, related_name="profile",
                    to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="AuthToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key_hash", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="auth_tokens",
                    to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_email", models.CharField(blank=True, max_length=254)),
                ("action", models.CharField(db_index=True, max_length=60)),
                ("target_type", models.CharField(blank=True, max_length=40)),
                ("target_id", models.CharField(blank=True, max_length=40)),
                ("detail", models.JSONField(default=dict)),
                ("ip_address", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField()),
                ("prev_hash", models.CharField(blank=True, max_length=64)),
                ("entry_hash", models.CharField(max_length=64)),
                ("actor", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["id"]},
        ),
        migrations.CreateModel(
            name="EncryptionKey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField(unique=True)),
                ("wrapped_key", models.TextField()),
                ("status", models.CharField(
                    choices=[("active", "Active"), ("retired", "Retired")],
                    default="active", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("retired_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["version"]},
        ),
        migrations.CreateModel(
            name="RetentionPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rejected_days", models.PositiveIntegerField(default=30)),
                ("undecided_days", models.PositiveIntegerField(default=90)),
                ("shortlisted_days", models.PositiveIntegerField(default=365)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("last_run_deleted", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="FairnessRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("passed", models.BooleanField(default=False)),
                ("summary", models.JSONField(default=dict)),
                ("details", models.JSONField(default=list)),
                ("created_by", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
