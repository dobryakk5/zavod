import os
from celery import Celery
from pathlib import Path

# Загрузить переменные окружения из .env файла
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# говорим Celery, где искать Django-настройки
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("content_factory")  # любое имя проекта

# читаем настройки CELERY_ из Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# автоматически ищем tasks.py во всех приложениях
app.autodiscover_tasks()
