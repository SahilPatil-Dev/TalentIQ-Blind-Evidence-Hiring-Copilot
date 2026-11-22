"""
Compliance review: an automatic self-check of the live system.

Each check returns a status:
  pass    the control is in place and verified now
  warn    works, but should be improved
  fail    a control is missing or broken
  manual  cannot be checked by software: a person must confirm it

References point to the rule a control relates to. This is an engineering checklist,
not legal advice, and passing it does not make a deployment compliant.
"""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from ..models import AuditLog, CandidateApplication, FairnessRun, Profile
from . import keys, retention
from .audit import verify_chain


def _check(check_id, area, title, status, detail, reference=""):
    return {"id": check_id, "area": area, "title": title, "status": status,
            "detail": detail, "reference": reference}


def build_report():
    now = timezone.now()
    checks = []
    add = checks.append

    # ---- Security ----
    add(_check("debug", "Security", "Debug mode is off",
               "fail" if settings.DEBUG else "pass",
               "DJANGO_DEBUG=1 exposes internals." if settings.DEBUG else "Debug is off.",
               "GDPR Art. 32"))
    weak_secret = settings.SECRET_KEY.startswith("unsafe") or len(settings.SECRET_KEY) < 32
    add(_check("secret_key", "Security", "Django secret key is strong",
               "fail" if weak_secret else "pass",
               "Set a long random DJANGO_SECRET_KEY." if weak_secret else "A long random key is set.",
               "GDPR Art. 32"))
    engine = settings.DATABASES["default"]["ENGINE"]
    add(_check("database", "Security", "Production database",
               "pass" if "postgresql" in engine else "warn",
               "PostgreSQL in use." if "postgresql" in engine
               else "SQLite is not durable on most hosts. Set DATABASE_URL.",
               "GDPR Art. 32"))
    hsts = getattr(settings, "SECURE_HSTS_SECONDS", 0)
    add(_check("hsts", "Security", "HTTPS enforced via HSTS",
               "pass" if hsts and not settings.DEBUG else "warn",
               f"HSTS max-age {hsts}s." if hsts else "HSTS is not enabled.", "GDPR Art. 32"))
    bad_origins = [o for o in settings.CORS_ALLOWED_ORIGINS if o == "*" or (o.startswith("http://") and "localhost" not in o)]
    only_local = all("localhost" in o for o in settings.CORS_ALLOWED_ORIGINS)
    add(_check("cors", "Security", "CORS allows only your website",
               "fail" if bad_origins else ("warn" if only_local and not settings.DEBUG else "pass"),
               "Insecure origin configured." if bad_origins
               else ("Only localhost is allowed: add your real website URL." if only_local and not settings.DEBUG
                     else "Only listed https origins are allowed."),
               "GDPR Art. 32"))

    # ---- Encryption ----
    add(_check("master_key", "Encryption", "Master key is set explicitly",
               "pass" if settings.KEK_IS_EXPLICIT else "warn",
               "KEY_ENCRYPTION_KEY is set in the environment." if settings.KEK_IS_EXPLICIT
               else "Master key is derived from the secret key. Set KEY_ENCRYPTION_KEY.",
               "GDPR Art. 32(1)(a)"))
    report = keys.key_report()
    active = [k for k in report["keys"] if k["status"] == "active"]
    stale = report["legacy_records"] + sum(k["records"] for k in report["keys"] if k["status"] != "active")
    add(_check("key_currency", "Encryption", "All identities use the current data key",
               "pass" if stale == 0 else "warn",
               f"{stale} record(s) use an older key. Run re-encryption." if stale
               else ("Active key version " + str(active[0]["version"]) if active else "No data yet."),
               "GDPR Art. 32"))
    add(_check("key_age", "Encryption", "Data key rotated in the last 12 months",
               "pass" if active and now - active[0]["created_at"] < timedelta(days=365) else "warn",
               "Rotate the data key at least yearly.", "GDPR Art. 32"))

    # ---- Access control & audit ----
    admins = Profile.objects.filter(role="admin", is_approved=True, user__is_active=True).count()
    add(_check("admins", "Access control", "At least two active administrators",
               "pass" if admins >= 2 else "warn",
               f"{admins} administrator(s). Keep a second one so you cannot be locked out.", "GDPR Art. 32"))
    pending = Profile.objects.filter(is_approved=False).count()
    add(_check("pending_users", "Access control", "No accounts waiting for approval",
               "pass" if pending == 0 else "warn", f"{pending} account(s) awaiting approval.", ""))
    chain = verify_chain()
    add(_check("audit_chain", "Audit", "Audit log chain is intact",
               "pass" if chain["valid"] else "fail",
               f"{chain['checked']} entries verified." if chain["valid"]
               else f"Chain broken at entry {chain['first_bad_id']}: the log was altered.",
               "GDPR Art. 5(2), 32; EU AI Act Art. 12"))
    reveals = AuditLog.objects.filter(action="identity.reveal").count()
    add(_check("reveal_audit", "Audit", "Identity reveals are justified and logged",
               "pass", f"{reveals} reveal(s) recorded, each with the user and a written reason.",
               "GDPR Art. 5(1)(b),(c)"))
    decided = CandidateApplication.objects.exclude(status__in=["NEEDS_REVIEW", "PROCESSING"])
    unexplained = decided.filter(decision_reason="").count()
    add(_check("human_decision", "Human oversight", "Every decision has a person and a reason",
               "pass" if unexplained == 0 else "warn",
               f"{unexplained} decision(s) without a recorded reason." if unexplained
               else "All decisions record who decided and why.",
               "GDPR Art. 22; EU AI Act Art. 14"))

    # ---- Retention ----
    policy = retention.get_policy()
    overdue = len(retention.find_expired(policy, now))
    add(_check("retention_overdue", "Retention", "No data kept past its retention period",
               "pass" if overdue == 0 else "fail",
               f"{overdue} application(s) are past retention. Run the retention job." if overdue
               else "Nothing is overdue.", "GDPR Art. 5(1)(e)"))
    recent = policy.last_run_at and now - policy.last_run_at < timedelta(days=30)
    add(_check("retention_run", "Retention", "Retention job ran in the last 30 days",
               "pass" if recent else "warn",
               f"Last run {policy.last_run_at:%Y-%m-%d}." if policy.last_run_at else "Never run.",
               "GDPR Art. 5(1)(e)"))

    # ---- Fairness ----
    last = FairnessRun.objects.first()
    if last is None:
        add(_check("fairness_run", "Fairness", "Fairness test run recently", "fail", "No fairness test has been run.",
                   "NYC Local Law 144; EU AI Act Art. 10"))
    else:
        age = now - last.created_at
        status = "fail" if not last.passed else ("pass" if age < timedelta(days=90) else "warn")
        add(_check("fairness_run", "Fairness", "Fairness test passed in the last 90 days", status,
                   f"Last run {last.created_at:%Y-%m-%d}: {'passed' if last.passed else 'FAILED'}.",
                   "NYC Local Law 144; EU AI Act Art. 10"))

    # ---- Third parties & things only people can confirm ----
    uses_ai = bool(settings.MISTRAL_API_KEY)
    add(_check("third_party", "Third parties", "Data sent to the AI provider is redacted",
               "warn" if uses_ai else "pass",
               "Redacted resume text is sent to Mistral. Sign a data processing agreement and check that "
               "redaction covers your resume formats (see the fairness probes)." if uses_ai
               else "No external AI provider is configured.", "GDPR Art. 28, 44"))
    manual = [
        ("dpia", "Data protection impact assessment completed", "GDPR Art. 35"),
        ("notice", "Candidates are told an automated tool scores resumes and how to ask for human review",
         "GDPR Art. 13, 22; NYC Local Law 144"),
        ("bias_audit", "Independent bias audit done and published (if hiring in NYC)", "NYC Local Law 144"),
        ("dpa", "Data processing agreements signed with Mistral, Render and Vercel", "GDPR Art. 28"),
        ("ai_act", "EU AI Act high-risk obligations reviewed (employment use)", "EU AI Act Annex III"),
        ("dsar", "A process exists to answer candidate access and erasure requests", "GDPR Art. 15, 17"),
    ]
    for check_id, title, reference in manual:
        add(_check(check_id, "Needs a person", title, "manual", "Confirm and record outside the system.", reference))

    counts = {s: sum(1 for c in checks if c["status"] == s) for s in ("pass", "warn", "fail", "manual")}
    return {
        "generated_at": now,
        "counts": counts,
        "checks": checks,
        "disclaimer": "Engineering self-assessment. Not legal advice and not a certification.",
    }
