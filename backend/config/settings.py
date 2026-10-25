"""Django settings. Everything environment-specific comes from backend/.env (see .env.example)."""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
# read_env also exports values into os.environ, which is how the Hatchet SDK finds
# HATCHET_CLIENT_TOKEN / HATCHET_CLIENT_TLS_STRATEGY.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    # daphne must come first so `runserver` serves ASGI (HTTP + websockets).
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "channels",
    # Platform apps: shared plumbing, no product features.
    "apps.core",
    "apps.accounts",
    "apps.realtime",
    "apps.jobs",
    # Domain apps, lowest layer first. A domain app may only import from apps listed above it
    # (enforced by apps/core/test_architecture.py).
    "apps.providers",
    "apps.library",
    "apps.rag",
    "apps.agents",
    "apps.chat",
    "apps.scoring",
    "apps.evals",
    "apps.benchmarks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

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
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL")}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Uploaded documents. Local disk for now; swapping in S3/GCS later is a STORAGES change only.
# Files are never served directly: the API decides who may read what.
MEDIA_ROOT = env("MEDIA_ROOT", default=str(BASE_DIR / "media"))
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024  # bigger uploads stream to a temp file
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- API -------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
}

# The Vite dev server proxies /api and /ws, so CORS only matters if you hit Django directly.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:5173"])

# --- Realtime --------------------------------------------------------------
# Redis is used ONLY as the Channels layer: the pipe that lets Hatchet workers (another
# process) push events to whichever Daphne process holds the user's websocket.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                {
                    "address": env("REDIS_URL", default="redis://localhost:6379/0"),
                    # redis-py 8 defaults socket_timeout to 5s, the same as channels-redis'
                    # blocking BZPOPMIN wait, so idle sockets randomly died with TimeoutError.
                    "socket_timeout": 15,
                }
            ]
        },
    }
}

# --- Secrets at rest ---------------------------------------------------------
# Fernet key used by apps.providers.crypto to encrypt LLM API keys in the database.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY")

# Seconds a new websocket has to send its {"type": "auth"} message before we close it.
WS_AUTH_TIMEOUT = 10
