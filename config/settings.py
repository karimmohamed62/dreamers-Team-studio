"""
إعدادات مشروع Dreamers Studio
محطة توليد محتوى السوشيال ميديا
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = ["*"]  # للتطوير فقط — ظبطها في الإنتاج

GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# ── Video generation guards ────────────────────────────────────────────────────
ENABLE_VIDEO_GENERATION      = os.getenv("ENABLE_VIDEO_GENERATION", "True") == "True"
MAX_VIDEO_GENERATIONS_PER_DAY = int(os.getenv("MAX_VIDEO_GENERATIONS_PER_DAY", "5"))

SESSION_ENGINE = "django.contrib.sessions.backends.db"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "studio",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# للتطوير: يسمح لتطبيق Flutter يكلم الباك-إند. في الإنتاج حدد الدومينات.
CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "ar"
TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Render / Production ────────────────────────────────────────────────────────
import dj_database_url

if os.getenv("DATABASE_URL"):
    DATABASES["default"] = dj_database_url.parse(os.getenv("DATABASE_URL"))

if not DEBUG:
    ALLOWED_HOSTS = ["*.onrender.com", "localhost", "127.0.0.1"]
    CSRF_TRUSTED_ORIGINS = ["https://*.onrender.com"]
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
