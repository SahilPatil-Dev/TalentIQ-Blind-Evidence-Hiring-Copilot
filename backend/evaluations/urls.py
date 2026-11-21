"""
The API's URL list. Each line connects a web address to a function in views.py.

  GET  /api/health/                          -> is the server awake?
  GET  /api/jobs/                            -> list all roles
  POST /api/jobs/                            -> create a role
  GET  /api/jobs/<id>/                       -> one role + its ranked candidates
  POST /api/jobs/<id>/applications/          -> upload a resume (runs the AI flow)
  GET  /api/applications/<id>/               -> one candidate's evidence review
  POST /api/applications/<id>/decision/      -> shortlist or reject
"""
from django.urls import path

from . import views

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
]
