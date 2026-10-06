"""booking-web: UI only. No models, no database — all data comes from booking-api over HTTP."""
import os
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


SECRET_KEY = env("SECRET_KEY", "dev-insecure-web-change-me-0123456789abcdef")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "django.contrib.messages",
    "apps.core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.JWTAuthMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csrf",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.ui",
            ]
        },
    }
]

DATABASES = {}  # intentionally empty
MESSAGE_STORAGE = "django.contrib.messages.storage.cookie.CookieStorage"  # no session DB needed

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Asia/Kolkata")
USE_I18N = False
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# booking-api
API_BASE_URL = env("API_BASE_URL", "http://localhost:8000/api").rstrip("/")
API_MEDIA_URL = env("API_MEDIA_URL", "http://localhost:8000/media/")  # browser-reachable
API_TIMEOUT = float(env("API_TIMEOUT", "10"))
API_PAGE_SIZE = 10  # must match booking-api REST_FRAMEWORK.PAGE_SIZE

# JWT cookies. The signing key is shared with booking-api so access tokens can be verified locally.
JWT_SIGNING_KEY = env("JWT_SIGNING_KEY", "dev-insecure-change-me-0123456789abcdef0123456789")
JWT_ACCESS_COOKIE = "access_token"
JWT_REFRESH_COOKIE = "refresh_token"
JWT_ACCESS_MAX_AGE = int(env("JWT_ACCESS_MINUTES", "15")) * 60
JWT_REFRESH_MAX_AGE = int(env("JWT_REFRESH_DAYS", "7")) * 86400
JWT_COOKIE_SECURE = env_bool("COOKIE_SECURE", not DEBUG)
JWT_COOKIE_SAMESITE = "Lax"

CURRENCY_SYMBOL = env("CURRENCY_SYMBOL", "₹")

CSRF_COOKIE_SECURE = JWT_COOKIE_SECURE
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True
