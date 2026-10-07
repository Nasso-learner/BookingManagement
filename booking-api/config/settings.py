import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Load KEY=VALUE lines from .env for local runs. Real environment variables win (Docker, CI, prod).
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _value = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _value.strip().strip("\"'"))


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return env(name, str(default)).lower() in ("1", "true", "yes")


SECRET_KEY = env("SECRET_KEY", "dev-insecure-change-me-0123456789abcdef0123456789")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "apps.accounts",
    "apps.departments",
    "apps.doctors",
    "apps.patients",
    "apps.appointments",
    "apps.notifications",
    "apps.audit_logs",
    "apps.analytics",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# if env_bool("USE_SQLITE"):  # local tests only; production is PostgreSQL
#     DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
# else:
DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB"),
            "USER": env("POSTGRES_USER"),
            "PASSWORD": env("POSTGRES_PASSWORD"),
            "HOST": env("POSTGRES_HOST"),
            "PORT": env("POSTGRES_PORT"),
            "CONN_MAX_AGE": 60,
        }
    }

print(DATABASES,"DATABASES")

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "config.pagination.Pagination",
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.ScopedRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"auth": "20/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", "7"))),
    "SIGNING_KEY": env("JWT_SIGNING_KEY", SECRET_KEY),
    "ALGORITHM": "HS256",
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

# Public URL of booking-web, used for password reset links in emails.
WEB_BASE_URL = env("WEB_BASE_URL", "http://localhost:8001")
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@medibook.local")

# Metabase static embedding. The secret comes from Metabase > Admin > Embedding > Static embedding.
METABASE_SITE_URL = env("METABASE_SITE_URL", "http://localhost:3000")  # browser-reachable
METABASE_SECRET_KEY = env("METABASE_SECRET_KEY", "")
METABASE_ADMIN_DASHBOARD_ID = int(env("METABASE_ADMIN_DASHBOARD_ID") or 0)
METABASE_DOCTOR_DASHBOARD_ID = int(env("METABASE_DOCTOR_DASHBOARD_ID") or 0)
METABASE_EMBED_MINUTES = int(env("METABASE_EMBED_MINUTES") or 60)

# Plotly report engine. Report SQL runs on a separate read-only login (see reports/setup_reports.sql).
if env("REPORTS_DB_USER"):
    DATABASES["reporting"] = {**DATABASES["default"], "USER": env("REPORTS_DB_USER"),
                              "PASSWORD": env("REPORTS_DB_PASSWORD"), "CONN_MAX_AGE": 60,
                              "TEST": {"MIRROR": "default"}}
REPORTS_DB_ALIAS = "reporting" if "reporting" in DATABASES else "default"  # default = no read-only role yet
REPORTS_TIMEOUT_MS = int(env("REPORTS_TIMEOUT_MS") or 5000)
REPORTS_MAX_ROWS = int(env("REPORTS_MAX_ROWS") or 2000)

# ClickHouse (high-performance report source, fed from PostgreSQL by PeerDB CDC). Empty host = disabled.
CLICKHOUSE_HOST = env("CLICKHOUSE_HOST", "")
CLICKHOUSE_PORT = int(env("CLICKHOUSE_PORT") or 8123)
CLICKHOUSE_SECURE = env_bool("CLICKHOUSE_SECURE", False)
CLICKHOUSE_REPORT_USER = env("CLICKHOUSE_REPORT_USER", "report_reader")
CLICKHOUSE_REPORT_PASSWORD = env("CLICKHOUSE_REPORT_PASSWORD", "")

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
