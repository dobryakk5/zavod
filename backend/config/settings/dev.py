from .base import *

# Development settings
# Run Celery tasks synchronously in development
CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
