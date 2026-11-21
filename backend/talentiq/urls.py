"""Top-level URLs: every API route lives under /api/ (see evaluations/urls.py)."""
from django.urls import include, path

urlpatterns = [path("api/", include("evaluations.urls"))]
