import os
from celery import Celery
from pathlib import Path

# Загрузить переменные окружения из .env файла
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Проксируем HTTP/HTTPS трафик Celery-задач при необходимости
_proxy_mapping = {
    "HTTP_PROXY": os.getenv("CELERY_HTTP_PROXY"),
    "HTTPS_PROXY": os.getenv("CELERY_HTTPS_PROXY"),
    "NO_PROXY": os.getenv("CELERY_NO_PROXY"),
}
for proxy_key, proxy_value in _proxy_mapping.items():
    if proxy_value:
        # requests и многие библиотеки читают и верхний, и нижний регистр
        os.environ[proxy_key] = proxy_value
        os.environ[proxy_key.lower()] = proxy_value

# говорим Celery, где искать Django-настройки
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("content_factory")  # любое имя проекта

# читаем настройки CELERY_ из Django settings
app.config_from_object("django.conf:settings", namespace="CELERY")

# автоматически ищем tasks.py во всех приложениях
app.autodiscover_tasks()
