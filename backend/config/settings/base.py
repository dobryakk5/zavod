import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
RUNSERVER_LOG_FILE = LOG_DIR / "runserver.log"
CELERY_LOG_FILE = LOG_DIR / "celery.log"

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

# Optional outbound proxy for Django processes (runserver/gunicorn)
_proxy_env = {
    "HTTP_PROXY": os.getenv("DJANGO_HTTP_PROXY") or os.getenv("CELERY_HTTP_PROXY") or os.getenv("HTTP_PROXY"),
    "HTTPS_PROXY": os.getenv("DJANGO_HTTPS_PROXY") or os.getenv("CELERY_HTTPS_PROXY") or os.getenv("HTTPS_PROXY"),
    "NO_PROXY": os.getenv("DJANGO_NO_PROXY") or os.getenv("CELERY_NO_PROXY") or os.getenv("NO_PROXY"),
}
for _proxy_key, _proxy_value in _proxy_env.items():
    if _proxy_value:
        # Ensure both upper- and lower-case variables are exported for requests/urllib
        os.environ[_proxy_key] = _proxy_value
        os.environ[_proxy_key.lower()] = _proxy_value

SECRET_KEY = os.getenv("SECRET_KEY", "change-me")  # поменяешь потом на нормальный
DEBUG = os.getenv("DEBUG", "True") == "True"
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
GOOGLE_API_KEY = os.getenv("Google_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.getenv("GOOGLE_CSE_ID") or os.getenv("CSE_ID") or os.getenv("GOOGLE_CX", "")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "")
YOOKASSA_API_URL = os.getenv("YOOKASSA_API_URL", "https://api.yookassa.ru/v3/payments")
YOOKASSA_WEBHOOK_SECRET = os.getenv("YOOKASSA_WEBHOOK_SECRET", "")
YOOKASSA_CLIENT_ID = os.getenv("YOOKASSA_CLIENT_ID", "")
YOOKASSA_CLIENT_SECRET = os.getenv("YOOKASSA_CLIENT_SECRET", "")
TBANK_API_URL = os.getenv("TBANK_API_URL", "https://securepay.tinkoff.ru/v2")
TBANK_TERMINAL_KEY = os.getenv("TBANK_TERMINAL_KEY", "TinkoffBankTest")
TBANK_SECRET_KEY = os.getenv("TBANK_SECRET_KEY", "TinkoffBankTest")
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "")
CUSTOM_DOMAIN_CNAME_TARGET = os.getenv("CUSTOM_DOMAIN_CNAME_TARGET", "fibonatty.ru").strip().lower().rstrip(".")

DEFAULT_ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "solarlab.media",
    "adm.solarlab.media",
    "fibonatty.ru",
    "adm.fibonatty.ru",
]

def _parse_hosts(hosts_value: str) -> list[str]:
    return [host.strip() for host in hosts_value.split(",") if host.strip()]


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]

def _hosts_to_origins(hosts: list[str]) -> list[str]:
    origins: list[str] = []
    for host in hosts:
        value = host.strip()
        if not value:
            continue
        if value.startswith(("http://", "https://")):
            origins.append(value)
        else:
            scheme = "http" if value.startswith(("localhost", "127.", "0.0.0.0")) else "https"
            origins.append(f"{scheme}://{value}")
    return origins

env_allowed_hosts_raw = os.getenv("ALLOWED_HOSTS")
if env_allowed_hosts_raw:
    parsed_hosts = _parse_hosts(env_allowed_hosts_raw)
    if "*" in parsed_hosts:
        ALLOWED_HOSTS = ["*"]
    else:
        # Append defaults to ensure production domains (adm.solarlab.media, etc.) always whitelisted
        ALLOWED_HOSTS = list(dict.fromkeys(parsed_hosts + DEFAULT_ALLOWED_HOSTS))
    _env_allowed_hosts_list = parsed_hosts
else:
    ALLOWED_HOSTS = DEFAULT_ALLOWED_HOSTS
    _env_allowed_hosts_list = []

CUSTOM_DOMAIN_EDGE_IPS = _parse_csv(os.getenv("CUSTOM_DOMAIN_EDGE_IPS", ""))

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Wagtail
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",

    # 3rd-party
    "corsheaders",
    "modelcluster",
    "taggit",
    "rest_framework",

    # API
    "api",

    # Твои приложения
    "core",
    "home",
    "search",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

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

# Database configuration
# Используем PostgreSQL из DATABASE_URL, fallback на SQLite для разработки
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

WAGTAIL_SITE_NAME = "Ai Marketing"

# URL, по которому ты заходишь в админку
WAGTAILADMIN_BASE_URL = "http://localhost:8000"

# Публичный домен фронтенда для share-ссылок и публичных маршрутов
PUBLIC_FRONTEND_BASE_URL = os.getenv("PUBLIC_FRONTEND_BASE_URL", "").rstrip("/")

# Celery (можно оставить как есть, даже если пока не пользуешься)
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERYD_HIJACK_ROOT_LOGGER = False
CELERY_BEAT_DEBUG = os.getenv("CELERY_BEAT_DEBUG", "False").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
CELERY_BEAT_LOG_LEVEL = "DEBUG" if CELERY_BEAT_DEBUG else "INFO"
CELERY_BEAT_MAX_LOOP_INTERVAL = 30
CELERY_BEAT_SCHEDULER = "celery.beat:PersistentScheduler"
SCHEDULES_POLL_SECONDS = int(os.getenv("SCHEDULES_POLL_SECONDS", "60"))
MEETING_REMINDERS_POLL_SECONDS = int(os.getenv("MEETING_REMINDERS_POLL_SECONDS", "60"))
PAYMENT_REMINDERS_POLL_SECONDS = int(os.getenv("PAYMENT_REMINDERS_POLL_SECONDS", "60"))
TASK_REMINDERS_POLL_SECONDS = int(os.getenv("TASK_REMINDERS_POLL_SECONDS", "60"))
RAG_INDEXING_ENABLED = os.getenv("RAG_INDEXING_ENABLED", "True").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
RAG_INDEX_POLL_SECONDS = int(os.getenv("RAG_INDEX_POLL_SECONDS", "300"))
RAG_INDEX_BATCH_SIZE = int(os.getenv("RAG_INDEX_BATCH_SIZE", "25"))
PROJECT_CHANNEL_ANALYSIS_HOUR = int(os.getenv("PROJECT_CHANNEL_ANALYSIS_HOUR", "9"))
PROJECT_CHANNEL_ANALYSIS_MINUTE = int(os.getenv("PROJECT_CHANNEL_ANALYSIS_MINUTE", "0"))
CELERY_BEAT_SCHEDULE = {
    "process-due-schedules": {
        "task": "core.tasks.publishing.process_due_schedules",
        "schedule": timedelta(seconds=SCHEDULES_POLL_SECONDS),
    },
    "meeting-reminders": {
        "task": "core.tasks.meeting_reminders.send_meeting_reminders",
        "schedule": timedelta(seconds=MEETING_REMINDERS_POLL_SECONDS),
    },
    "payment-reminders": {
        "task": "core.tasks.payment_reminders.send_payment_reminders",
        "schedule": timedelta(seconds=PAYMENT_REMINDERS_POLL_SECONDS),
    },
    "task-deadline-reminders": {
        "task": "core.tasks.task_deadline_reminders.send_task_deadline_reminders",
        "schedule": timedelta(seconds=TASK_REMINDERS_POLL_SECONDS),
    },
    "kb-rag-indexing": {
        "task": "core.tasks.process_pending_kb_rag_indexing",
        "schedule": timedelta(seconds=RAG_INDEX_POLL_SECONDS),
        "args": (RAG_INDEX_BATCH_SIZE,),
    },
    "project-channel-analysis-daily": {
        "task": "core.tasks.channel_analysis.schedule_project_channel_analysis_daily",
        "schedule": crontab(hour=PROJECT_CHANNEL_ANALYSIS_HOUR, minute=PROJECT_CHANNEL_ANALYSIS_MINUTE),
    },
}

# AI Content Generation
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# RAG (KB semantic search)
RAG_CONFIG = {
    # RAG_E5* must be used only for embeddings.
    "E5_MODEL_PATH": os.getenv(
        "RAG_E5_MODEL_PATH",
        str(BASE_DIR / "models" / "multilingual-e5-small"),
    ),
    "CHUNK_SIZE": int(os.getenv("RAG_CHUNK_SIZE", "512")),
    "CHUNK_OVERLAP": int(os.getenv("RAG_CHUNK_OVERLAP", "64")),
    "TOP_K": int(os.getenv("RAG_TOP_K", "10")),
    "RRF_K": int(os.getenv("RAG_RRF_K", "60")),
    "TS_LANGUAGE": os.getenv("RAG_TS_LANGUAGE", "russian"),
    "CONTEXT_ENABLED": os.getenv("RAG_CONTEXT_ENABLED", "True"),
    "CONTEXT_CONCURRENCY": int(os.getenv("RAG_CONTEXT_CONCURRENCY", "4")),
    "CONTEXT_MAX_TOKENS": int(os.getenv("RAG_CONTEXT_MAX_TOKENS", "300")),
    "CONTEXT_TEMPERATURE": float(os.getenv("RAG_CONTEXT_TEMPERATURE", "0.0")),
    "CONTEXT_TIMEOUT_SECONDS": float(os.getenv("RAG_CONTEXT_TIMEOUT_SECONDS", "120")),
}

# Опционально: другие AI сервисы (для будущего использования)
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# STABILITY_API_KEY = os.getenv("STABILITY_API_KEY")
# RUNWAY_API_KEY = os.getenv("RUNWAY_API_KEY")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "api.authentication.CookieJWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "team_invitation_minute": "10/min",
        "team_invitation_day": "100/day",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
}

# CORS / CSRF settings
_DEFAULT_CLIENT_ORIGINS_BASE = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://solarlab.media",
    "https://adm.solarlab.media",
    "https://fibonatty.ru",
    "https://adm.fibonatty.ru",
]
_DEFAULT_CLIENT_ORIGINS = _DEFAULT_CLIENT_ORIGINS_BASE + _hosts_to_origins(_env_allowed_hosts_list)
DEFAULT_CLIENT_ORIGINS = ",".join(list(dict.fromkeys(_DEFAULT_CLIENT_ORIGINS)))

CORS_ALLOWED_ORIGINS = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    DEFAULT_CLIENT_ORIGINS,
).split(",")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    DEFAULT_CLIENT_ORIGINS,
).split(",")

# VK integration defaults (override in env for production)
VK_CLIENT_ID = os.getenv("VK_CLIENT_ID", "")
VK_CLIENT_SECRET = os.getenv("VK_CLIENT_SECRET", "")
VK_REDIRECT_URI = os.getenv("VK_REDIRECT_URI", "http://localhost:8000/api/vk/callback/")
VK_API_VERSION = os.getenv("VK_API_VERSION", "5.131")

# VK auth for user login (separated from VK integrations flow)
VK_AUTH_APP_ID = os.getenv("VK_AUTH_APP_ID", "")
VK_AUTH_APP_SECRET = os.getenv("VK_AUTH_APP_SECRET", "")
VK_AUTH_REDIRECT_URI = os.getenv("VK_AUTH_REDIRECT_URI", "http://localhost:3000/auth/vk/callback")
VK_CALLBACK_SECRET = os.getenv("VK_CALLBACK_SECRET", "")
VK_CALLBACK_CONFIRMATION_TOKEN = os.getenv("VK_CALLBACK_CONFIRMATION_TOKEN", "")

# Telegram API Settings (системные credentials для всех клиентов)
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")
TELEGRAM_ALERT_USER_ID = os.getenv("TELEGRAM_ALERT_USER_ID", "")

# Email (SMTP)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
_EMAIL_BACKEND_ENV = os.getenv("EMAIL_BACKEND", "").strip()
if _EMAIL_BACKEND_ENV:
    EMAIL_BACKEND = _EMAIL_BACKEND_ENV
elif EMAIL_HOST and EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "support@fibonatty.ru")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
TEAM_MAX_COLLABORATORS = int(os.getenv("TEAM_MAX_COLLABORATORS", "20"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[%(asctime)s] %(levelname)s %(name)s:%(lineno)d %(message)s",
        },
        "simple": {
            "format": "%(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "runserver_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": RUNSERVER_LOG_FILE,
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "celery_file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": CELERY_LOG_FILE,
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django.server": {
            "handlers": ["console", "runserver_file"],
            "level": "INFO",
            "propagate": False,
        },
        # Silence noisy per-request INFO logs from httpx/httpcore.
        "httpx": {
            "handlers": ["console", "runserver_file", "celery_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "httpcore": {
            "handlers": ["console", "runserver_file", "celery_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
        "celery.beat": {
            "handlers": ["console", "celery_file"],
            "level": CELERY_BEAT_LOG_LEVEL,
            "propagate": False,
        },
        "celery.apps.beat": {
            "handlers": ["console", "celery_file"],
            "level": CELERY_BEAT_LOG_LEVEL,
            "propagate": False,
        },
        "core.tasks": {
            "handlers": ["console", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
        "core.services.website_scan_service": {
            "handlers": ["console", "runserver_file", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
        "core.tasks.website_scan": {
            "handlers": ["console", "runserver_file", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
        "api.views_accounts": {
            "handlers": ["console", "runserver_file", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
        "api.views_vk_auth": {
            "handlers": ["console", "runserver_file", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
        "api.views_social_accounts": {
            "handlers": ["console", "runserver_file", "celery_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
