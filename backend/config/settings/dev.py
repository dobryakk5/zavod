import os

from .base import *


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Development defaults for local Celery worker.
# If you want old synchronous behavior, set CELERY_ALWAYS_EAGER=1 in env.
CELERY_ALWAYS_EAGER = _env_bool("CELERY_ALWAYS_EAGER", False)
CELERY_TASK_ALWAYS_EAGER = CELERY_ALWAYS_EAGER
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
CELERY_TASK_EAGER_PROPAGATES = True

# Keep local CPU usage predictable on startup.
CELERY_WORKER_POOL = os.getenv("CELERY_WORKER_POOL", "solo")
CELERY_WORKER_CONCURRENCY = int(os.getenv("CELERY_WORKER_CONCURRENCY", "1"))
CELERY_WORKER_PREFETCH_MULTIPLIER = int(os.getenv("CELERY_WORKER_PREFETCH_MULTIPLIER", "1"))
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
