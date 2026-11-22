"""
The API's URL list. Each line connects a web address to a function in views.py.

  GET  /api/health/                          -> is the server awake?
  GET  /api/jobs/                            -> list all roles
  POST /api/jobs/                            -> create a role
  GET  /api/jobs/<id>/                       -> one role + its ranked candidates
  POST /api/jobs/<id>/applications/          -> upload a resume (runs the AI flow)
  GET  /api/applications/<id>/               -> one candidate's evidence review
  POST /api/applications/<id>/decision/      -> shortlist or reject (needs a reason)
  POST /api/applications/<id>/reveal/        -> audited identity reveal (needs a reason)
  POST /api/applications/<id>/hold/          -> legal hold on/off (admin)
  DELETE /api/applications/<id>/             -> erase a candidate (admin)

  /api/auth/...   register, login, logout, me, password
  /api/users/...  user management (admin)
  /api/audit/ /api/retention/ /api/keys/ /api/fairness/ /api/compliance/   governance
"""
from django.urls import path

from . import account_views, admin_views, views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("jobs/", views.jobs, name="jobs"),
    path("jobs/<int:job_id>/", views.job_detail, name="job-detail"),
    path(
        "jobs/<int:job_id>/applications/",
        views.upload_application,
        name="upload-application",
    ),
    path(
        "applications/<int:application_id>/",
        views.application_detail,
        name="application-detail",
    ),
    path(
        "applications/<int:application_id>/decision/",
        views.decide_application,
        name="application-decision",
    ),
    path("applications/<int:application_id>/reveal/", views.reveal_identity, name="application-reveal"),
    path("applications/<int:application_id>/hold/", views.set_legal_hold, name="application-hold"),
    # accounts
    path("auth/register/", account_views.register, name="register"),
    path("auth/login/", account_views.login, name="login"),
    path("auth/logout/", account_views.logout, name="logout"),
    path("auth/me/", account_views.me, name="me"),
    path("auth/password/", account_views.change_password, name="change-password"),
    path("users/", account_views.users, name="users"),
    path("users/<int:user_id>/", account_views.user_detail, name="user-detail"),
    # governance
    path("audit/", admin_views.audit_log, name="audit-log"),
    path("audit/verify/", admin_views.audit_verify, name="audit-verify"),
    path("retention/", admin_views.retention_policy, name="retention"),
    path("retention/run/", admin_views.retention_run, name="retention-run"),
    path("keys/", admin_views.key_status, name="keys"),
    path("keys/rotate/", admin_views.key_rotate, name="keys-rotate"),
    path("keys/reencrypt/", admin_views.key_reencrypt, name="keys-reencrypt"),
    path("fairness/runs/", admin_views.fairness_runs, name="fairness-runs"),
    path("fairness/runs/<int:run_id>/", admin_views.fairness_run_detail, name="fairness-run"),
    path("fairness/adverse-impact/", admin_views.adverse_impact, name="adverse-impact"),
    path("compliance/", admin_views.compliance_report, name="compliance"),
]
