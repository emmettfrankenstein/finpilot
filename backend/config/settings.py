"""Django settings for the FinPilot API.

All environment-specific values come from environment variables (see `.env.example`).
Nothing secret is hard-coded; local development falls back to safe, obviously-fake defaults
only when DJANGO_DEBUG is true.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, str(default)).lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in env(name, default).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false")
    SECRET_KEY = "insecure-local-development-key-do-not-use"  # noqa: S105

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "apps.core",
    "apps.users",
    "apps.portfolio",
    "apps.ingestion",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.AccessLogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "finpilot"),
        "USER": env("POSTGRES_USER", "finpilot"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        # Persistent connections act as a lightweight per-worker pool; PgBouncer in production.
        "CONN_MAX_AGE": int(env("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "connect_timeout": 5,
            # Guard rail: no single API query may hold a connection for more than 10s.
            "options": "-c statement_timeout=10000",
        },
    }
}

AUTH_USER_MODEL = "users.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Uploads: import files are read in memory; cap them to keep the API responsive.
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
IMPORT_MAX_BYTES = int(env("IMPORT_MAX_BYTES", str(5 * 1024 * 1024)))

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {"login": env("LOGIN_THROTTLE_RATE", "10/min")},
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "COERCE_DECIMAL_TO_STRING": True,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(hours=int(env("JWT_REFRESH_HOURS", "8"))),
    "ROTATE_REFRESH_TOKENS": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": env("JWT_SIGNING_KEY", SECRET_KEY),
}

# Refresh token lives in an httpOnly cookie that only the auth endpoints receive.
REFRESH_COOKIE_NAME = "finpilot_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth/"
REFRESH_COOKIE_SECURE = env_bool("REFRESH_COOKIE_SECURE", not DEBUG)
REFRESH_COOKIE_SAMESITE = "Strict"

SPECTACULAR_SETTINGS = {
    "TITLE": "FinPilot API",
    "DESCRIPTION": (
        "Investment portfolio and goal monitoring API. Synthetic assessment data only. "
        "Authenticate with POST /api/v1/auth/login and send `Authorization: Bearer <access>`."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "ENUM_NAME_OVERRIDES": {
        "LevelEnum": "apps.portfolio.models.Level",
        "AccountStatusEnum": "apps.portfolio.models.AccountStatus",
        "TransactionStatusEnum": "apps.portfolio.models.TransactionStatus",
        "BatchStatusEnum": "apps.ingestion.models.BatchStatus",
    },
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
CORS_ALLOW_CREDENTIALS = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

LOG_LEVEL = env("LOG_LEVEL", "INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.core.logging.RequestIdFilter"}},
    "formatters": {
        "json": {"()": "apps.core.logging.JsonFormatter"},
        "plain": {"format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": env("LOG_FORMAT", "json"),
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {"level": "ERROR"},
        "django.server": {"level": "WARNING"},
        "finpilot": {"level": LOG_LEVEL, "propagate": True},
    },
}
