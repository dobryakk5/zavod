# Backend Setup

В этом документе описана настройка backend части системы Zavod на Django.

## Содержание

- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [База данных](#база-данных)
- [Celery](#celery)
- [Redis](#redis)
- [Запуск](#запуск)
- [Тестирование](#тестирование)

## Требования

- **Python 3.10+**
- **PostgreSQL 12+**
- **Redis 6+**
- **Virtual Environment**

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd zavod/backend
```

### 2. Создание виртуального окружения

```bash
# Linux/Mac
python -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка окружения

```bash
cp .env.example .env
```

Заполните `.env` файл своими значениями:

```env
# Django
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgres://user:password@localhost:5432/zavod

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# AI Services
OPENAI_API_KEY=your-openai-api-key
STABILITY_API_KEY=your-stability-api-key
RUNWAY_API_KEY=your-runway-api-key

# Social APIs
INSTAGRAM_ACCESS_TOKEN=your-instagram-token
TELEGRAM_BOT_TOKEN=your-telegram-token
YOUTUBE_CLIENT_ID=your-youtube-client-id
YOUTUBE_CLIENT_SECRET=your-youtube-client-secret
```

## Конфигурация

### Django Settings

Основные настройки в `config/settings/`:

#### Base Settings (`config/settings/base.py`)

```python
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.environ.get('SECRET_KEY')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'rest_framework',
    'corsheaders',
    'taggit',
    
    # Local apps
    'core',
    'api',
]

# Middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'core.middleware.TenantMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'zavod'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}
```

#### Development Settings (`config/settings/dev.py`)

```python
from .base import *

DEBUG = True

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# CORS
CORS_ALLOW_ALL_ORIGINS = True

# Celery
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_TASK_ALWAYS_EAGER = False
```

#### Production Settings (`config/settings/production.py`)

```python
from .base import *

DEBUG = False

# Security
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Database
import dj_database_url
DATABASES['default'] = dj_database_url.config(conn_max_age=600)

# Static files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

### Tenant Middleware

```python
# core/middleware.py
from django.utils.deprecation import MiddlewareMixin
from .models import Client, UserTenantRole

class TenantMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            # Определяем активного клиента для пользователя
            client = self.get_client_for_user(request.user)
            if client:
                request.tenant = client
    
    def get_client_for_user(self, user):
        # Логика определения клиента
        # Например, по session или query параметру
        tenant_id = user.session.get('tenant_id')
        if tenant_id:
            try:
                return Client.objects.get(id=tenant_id)
            except Client.DoesNotExist:
                pass
        
        # Или первый доступный клиент
        role = UserTenantRole.objects.filter(user=user).first()
        return role.client if role else None
```

## База данных

### PostgreSQL Setup

#### Linux (Ubuntu/Debian)

```bash
# Установка PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Запуск сервиса
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создание базы данных
sudo -u postgres psql
CREATE DATABASE zavod;
CREATE USER zavod_user WITH PASSWORD 'password';
GRANT ALL PRIVILEGES ON DATABASE zavod TO zavod_user;
\q
```

#### Mac

```bash
# Установка через Homebrew
brew install postgresql
brew services start postgresql

# Создание базы данных
createdb zavod
createuser zavod_user
```

#### Docker

```bash
docker run -d \
  --name postgres-zavod \
  -e POSTGRES_DB=zavod \
  -e POSTGRES_USER=zavod_user \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  postgres:15
```

### Миграции

```bash
# Применение миграций
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Сбор статики (для production)
python manage.py collectstatic
```

## Celery

### Установка и настройка

#### Redis как брокер

```bash
# Установка Redis
# Linux
sudo apt install redis-server

# Mac
brew install redis
brew services start redis

# Docker
docker run -d -p 6379:6379 redis:alpine
```

#### Конфигурация Celery

```python
# config/celery.py
import os
from celery import Celery

# Установка переменной окружения для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('zavod')
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматическое обнаружение задач
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
```

```python
# config/__init__.py
from .celery import app as celery_app

__all__ = ('celery_app',)
```

#### Запуск Celery Worker

```bash
# В директории backend
celery -A config worker -l info

# С несколькими воркерами
celery -A config worker -l info -c 4

# Beat для периодических задач
celery -A config beat -l info
```

#### Periodic Tasks

```python
# config/celery.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'process-schedules': {
        'task': 'core.tasks.process_schedules',
        'schedule': crontab(minute='*/5'),  # Каждые 5 минут
    },
    'discover-content': {
        'task': 'core.tasks.discover_content_for_topic',
        'schedule': crontab(hour=9, minute=0),  # Каждый день в 9:00
        'args': (1,),  # ID темы
    },
    'generate-seo': {
        'task': 'core.tasks.generate_seo_for_client',
        'schedule': crontab(hour=2, minute=0),  # Каждую ночь в 2:00
        'args': (1,),  # ID клиента
    },
}

app.conf.timezone = 'UTC'
```

## Redis

### Конфигурация

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
    }
}

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
```

### Использование Redis для кэширования

```python
from django.core.cache import cache

# Кэширование данных
def get_expensive_data():
    data = cache.get('expensive_data')
    if data is None:
        data = calculate_expensive_data()
        cache.set('expensive_data', data, 3600)  # Кэш на 1 час
    return data

# Кэширование результатов API
def get_api_data(url):
    cache_key = f'api_data_{hash(url)}'
    data = cache.get(cache_key)
    if data is None:
        data = requests.get(url).json()
        cache.set(cache_key, data, 600)  # Кэш на 10 минут
    return data
```

## Запуск

### Development

```bash
# Активация виртуального окружения
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Запуск Django development server
python manage.py runserver

# Запуск Celery worker
celery -A config worker -l info

# Запуск Celery beat (для периодических задач)
celery -A config beat -l info
```

### Production

#### Gunicorn

```bash
# Установка Gunicorn
pip install gunicorn

# Запуск
gunicorn config.wsgi:application -w 4 -b 0.0.0.0:8000
```

#### Nginx (обратный прокси)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/static/files/;
    }
}
```

#### Systemd сервисы

```ini
# /etc/systemd/system/zavod-web.service
[Unit]
Description=Zavod Web Service
After=network.target

[Service]
Type=exec
User=zavod
Group=zavod
WorkingDirectory=/path/to/zavod/backend
Environment="PATH=/path/to/zavod/venv/bin"
ExecStart=/path/to/zavod/venv/bin/gunicorn config.wsgi:application -w 4 -b 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/zavod-worker.service
[Unit]
Description=Zavod Celery Worker
After=network.target

[Service]
Type=exec
User=zavod
Group=zavod
WorkingDirectory=/path/to/zavod/backend
Environment="PATH=/path/to/zavod/venv/bin"
ExecStart=/path/to/zavod/venv/bin/celery -A config worker -l info
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Запуск сервисов
sudo systemctl start zavod-web
sudo systemctl start zavod-worker
sudo systemctl enable zavod-web
sudo systemctl enable zavod-worker
```

## Тестирование

### Unit Tests

```python
# core/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Client, Post, Topic

User = get_user_model()

class ClientModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client.objects.create(
            name='Test Client',
            slug='test-client'
        )

    def test_client_creation(self):
        self.assertEqual(self.client.name, 'Test Client')
        self.assertEqual(self.client.slug, 'test-client')

    def test_user_client_relation(self):
        from core.models import UserTenantRole
        role = UserTenantRole.objects.create(
            user=self.user,
            client=self.client,
            role='owner'
        )
        self.assertEqual(role.user, self.user)
        self.assertEqual(role.client, self.client)
```

### Запуск тестов

```bash
# Все тесты
python manage.py test

# Конкретный app
python manage.py test core

# Конкретный тест
python manage.py test core.tests.ClientModelTest

# С coverage
pip install coverage
coverage run --source='.' manage.py test
coverage report
coverage html
```

### API Tests

```python
# api/tests.py
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

class APITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_auth_required(self):
        url = reverse('api:posts-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_success(self):
        self.client.force_authenticate(user=self.user)
        url = reverse('api:posts-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
```

### Load Testing

```python
# load_test.py
import requests
import concurrent.futures
import time

def make_request(url):
    try:
        response = requests.get(url)
        return response.status_code
    except Exception as e:
        return str(e)

def load_test(url, num_requests=100, concurrent_users=10):
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = [executor.submit(make_request, url) for _ in range(num_requests)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    
    end_time = time.time()
    
    print(f"Total requests: {num_requests}")
    print(f"Concurrent users: {concurrent_users}")
    print(f"Total time: {end_time - start_time:.2f} seconds")
    print(f"Success rate: {results.count(200) / len(results) * 100:.2f}%")

if __name__ == '__main__':
    load_test('http://localhost:8000/api/posts/')
```

---

**Далее:**
- [Permissions](./permissions.md) - Права доступа и security
- [API](../02-api/overview.md) - API документация
- [Deployment](../07-deployment/docker.md) - Деплоймент
