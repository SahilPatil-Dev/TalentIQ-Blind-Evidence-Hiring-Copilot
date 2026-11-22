"""
Django settings for TalentIQ.

HOW THIS FILE WORKS
-------------------
Anything that changes between your laptop and a real server (secret keys, the
database, the Mistral API key, which website may call the API) is read from
ENVIRONMENT VARIABLES. That way the exact same code runs:
  * on your laptop      -> values come from the `.env` file (loaded just below)
  * in Docker           -> values come from docker-compose.yml
  * on Render (hosting) -> values come from the Render dashboard / render.yaml

See `.env.example` in the project root for the full list of variables.
"""
import base64
import hashlib
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------
# Tiny `.env` loader (so you don't need an extra library)
# --------------------------------------------------------------------------
def _load_dotenv():
    """Read KEY=value lines from a `.env` file and put them in os.environ.

    It looks in the project root first, then inside `backend/`. Values that are
    already set in the real environment always win (setdefault).
    """
    for folder in (BASE_DIR.parent, BASE_DIR):
        env_file = folder / ".env"
        if not env_file.is_file():
            continue
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv()


def env_list(name, default=""):
    """Read a comma-separated variable: "a.com, b.com" -> ["a.com", "b.com"]."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


# --------------------------------------------------------------------------
# Core Django settings
# --------------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-local-development-key")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"  # keep this OFF on a real server

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
# Render tells every service its own public hostname in this variable.
if os.getenv("RENDER_EXTERNAL_HOSTNAME"):
    ALLOWED_HOSTS.append(os.environ["RENDER_EXTERNAL_HOSTNAME"])

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",   # builds the JSON API
    "corsheaders",      # lets the Next.js website call this API from another domain
    "evaluations",      # <- our app: models, views, and the AI evaluation flow
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "talentiq.urls"
TEMPLATES = []  # no HTML pages here: this project is an API only
WSGI_APPLICATION = "talentiq.wsgi.application"
ASGI_APPLICATION = "talentiq.asgi.application"

# Behind Render's proxy the request arrives as http, so trust its https header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --------------------------------------------------------------------------
# Database: PostgreSQL when DATABASE_URL is set, otherwise a local SQLite file
# --------------------------------------------------------------------------
_database_url = os.getenv("DATABASE_URL")
DATABASES = {
    "default": dj_database_url.parse(_database_url, conn_max_age=600)
    if _database_url
    else {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"

# --------------------------------------------------------------------------
# Django REST Framework (the JSON API layer)
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    # Everything needs a signed-in user unless a view says otherwise (see auth.py).
    "DEFAULT_AUTHENTICATION_CLASSES": ["evaluations.auth.TokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # Protect your Mistral credits and the login form from guessing.
    # On Render there is one proxy in front of us, so NUM_PROXIES=1 there.
    "NUM_PROXIES": int(os.getenv("NUM_PROXIES", "0")),
    "DEFAULT_THROTTLE_RATES": {
        "upload": os.getenv("UPLOAD_RATE_LIMIT", "30/hour"),  # per signed-in user
        "auth": os.getenv("AUTH_RATE_LIMIT", "20/hour"),      # login + register, per IP
    },
}

# --------------------------------------------------------------------------
# Accounts and sessions
# --------------------------------------------------------------------------
AUTH_TOKEN_TTL_HOURS = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12"))
MAX_FAILED_LOGINS = int(os.getenv("MAX_FAILED_LOGINS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# Browser security headers (only matter over HTTPS, so off while developing)
# --------------------------------------------------------------------------
if not DEBUG:
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_CONTENT_TYPE_NOSNIFF = True

# --------------------------------------------------------------------------
# CORS: which websites are allowed to call this API from a browser
# --------------------------------------------------------------------------
# Put your Vercel URL here once you have it, e.g. https://talentiq.vercel.app
CORS_ALLOWED_ORIGINS = [
    origin.rstrip("/")  # a trailing slash would make the setting invalid
    for origin in env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
]

# --------------------------------------------------------------------------
# Mistral AI (Codestral) settings
# --------------------------------------------------------------------------
# Leave MISTRAL_API_KEY empty and the app still works using simple local
# keyword matching, so you can demo it without any AI key.
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "codestral-2508")
MISTRAL_API_URL = os.getenv(
    "MISTRAL_API_URL", "https://api.mistral.ai/v1/chat/completions"
)
MISTRAL_TIMEOUT = int(os.getenv("MISTRAL_TIMEOUT", "60"))  # seconds

# --------------------------------------------------------------------------
# Encryption key for the hidden candidate identity (name, email, ...)
# --------------------------------------------------------------------------
# Best practice: set PII_ENCRYPTION_KEY yourself. If you don't, we derive one
# from SECRET_KEY (fine for a demo; just never change SECRET_KEY afterwards or
# old identities can no longer be decrypted).
_configured_encryption_key = os.getenv("PII_ENCRYPTION_KEY")
PII_ENCRYPTION_KEY = (
    _configured_encryption_key.encode()
    if _configured_encryption_key
    else base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest())
)

# Master key ("KEK") that wraps the data keys stored in the database.
# KEY_ENCRYPTION_KEY takes one Fernet key, or "new,old" while rotating the master key.
# Without it we fall back to PII_ENCRYPTION_KEY (and ultimately SECRET_KEY): fine for a
# demo, but the compliance review flags it.
KEK_IS_EXPLICIT = bool(os.getenv("KEY_ENCRYPTION_KEY"))
KEY_ENCRYPTION_KEY = os.getenv("KEY_ENCRYPTION_KEY") or PII_ENCRYPTION_KEY.decode()
