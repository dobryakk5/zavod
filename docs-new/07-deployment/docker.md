# Docker Deployment

В этом документе описана контейнеризация и деплоймент системы Zavod с использованием Docker.

## Содержание

- [Требования](#требования)
- [Dockerfile](#dockerfile)
- [Docker Compose](#docker-compose)
- [Build образов](#build-образов)
- [Запуск](#запуск)
- [Production](#production)
- [Мониторинг](#мониторинг)

## Требования

- **Docker 20.0+**
- **Docker Compose 2.0+**
- **8GB RAM** (рекомендуется)
- **2GB свободного места**

## Dockerfile

### Backend Dockerfile

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Настройка рабочей директории
WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание пользователя (безопасность)
RUN groupadd -r zavod && useradd -r -g zavod zavod
RUN chown -R zavod:zavod /app
USER zavod

# Экспорт порта
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

# Запуск
CMD ["gunicorn", "config.wsgi:application", "-b", "0.0.0.0:8000", "--workers", "4"]
```

### Frontend Dockerfile

```dockerfile
# frontend/Dockerfile
FROM node:18-alpine

# Установка dumb-init для правильного управления процессами
RUN apk add --no-cache dumb-init

WORKDIR /app

# Копирование package.json и установка зависимостей
COPY package*.json ./
RUN npm ci --only=production

# Копирование исходного кода
COPY . .

# Сборка
RUN npm run build

# Создание непривилегированного пользователя
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001

# Смена пользователя
USER nextjs

# Экспорт порта
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Запуск
CMD ["dumb-init", "npm", "start"]
```

### AI Worker Dockerfile

```dockerfile
# ai-worker/Dockerfile
FROM python:3.11-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-dev \
    curl \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создание пользователя
RUN groupadd -r aiworker && useradd -r -g aiworker aiworker
RUN chown -R aiworker:aiworker /app
USER aiworker

# Запуск Celery worker
CMD ["celery", "-A", "config", "worker", "-l", "info", "-c", "2"]
```

## Docker Compose

### Development

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  # PostgreSQL Database
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: zavod
      POSTGRES_USER: zavod_user
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U zavod_user -d zavod"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis Cache
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Backend API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DEBUG=True
      - DATABASE_URL=postgres://zavod_user:password@db:5432/zavod
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - SECRET_KEY=dev-secret-key-change-in-production
    volumes:
      - ./backend:/app
      - /app/node_modules
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - ./backend/.env

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXT_PUBLIC_DEV_MODE=true
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    depends_on:
      - backend
    env_file:
      - ./frontend/.env.local

  # Celery Worker
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production
    command: celery -A config worker -l info
    environment:
      - DATABASE_URL=postgres://zavod_user:password@db:5432/zavod
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - SECRET_KEY=dev-secret-key-change-in-production
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - ./backend/.env

  # Celery Beat
  beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    environment:
      - DATABASE_URL=postgres://zavod_user:password@db:5432/zavod
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/0
      - SECRET_KEY=dev-secret-key-change-in-production
    volumes:
      - ./backend:/app
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    env_file:
      - ./backend/.env

volumes:
  postgres_data:
  redis_data:
```

### Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  # PostgreSQL
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: zavod
      POSTGRES_USER: zavod_user
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
    ports:
      - "5432:5432"
    secrets:
      - db_password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U zavod_user -d zavod"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Redis
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Backend
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      - DEBUG=False
      - DATABASE_URL=postgres://zavod_user:${DB_PASSWORD}@db:5432/zavod
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_HOSTS=zavod.example.com
    volumes:
      - static_files:/app/staticfiles
      - media_files:/app/media
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    secrets:
      - db_password
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      - NEXT_PUBLIC_API_URL=https://api.zavod.example.com
      - NEXT_PUBLIC_DEV_MODE=false
    ports:
      - "3000:3000"
    depends_on:
      - backend
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M

  # Celery Worker
  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A config worker -l info -c 4
    environment:
      - DEBUG=False
      - DATABASE_URL=postgres://zavod_user:${DB_PASSWORD}@db:5432/zavod
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
    volumes:
      - media_files:/app/media
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    secrets:
      - db_password
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/ssl:/etc/nginx/ssl
      - static_files:/app/staticfiles
      - media_files:/app/media
    depends_on:
      - backend
      - frontend
    deploy:
      replicas: 1
      resources:
        limits:
          cpus: '0.5'
          memory: 256M

  # Monitoring (Prometheus + Grafana)
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=200h'
      - '--web.enable-lifecycle'

  grafana:
    image: grafana/grafana
    ports:
      - "3001:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources

volumes:
  postgres_data:
  redis_data:
  static_files:
  media_files:
  grafana_data:

secrets:
  db_password:
    file: ./secrets/db_password.txt
```

## Build образов

### Development

```bash
# Сборка всех сервисов
docker-compose -f docker-compose.dev.yml build

# Сборка конкретного сервиса
docker-compose -f docker-compose.dev.yml build backend

# Сборка с кешем
docker-compose -f docker-compose.dev.yml build --no-cache
```

### Production

```bash
# Сборка production образов
docker-compose -f docker-compose.prod.yml build

# Мульти-архитектурная сборка
docker buildx build --platform linux/amd64,linux/arm64 -t zavod/backend:latest ./backend
docker buildx build --platform linux/amd64,linux/arm64 -t zavod/frontend:latest ./frontend
```

## Запуск

### Development

```bash
# Запуск всех сервисов
docker-compose -f docker-compose.dev.yml up

# Запуск в фоне
docker-compose -f docker-compose.dev.yml up -d

# Просмотр логов
docker-compose -f docker-compose.dev.yml logs -f

# Остановка
docker-compose -f docker-compose.dev.yml down

# Остановка с удалением volumes
docker-compose -f docker-compose.dev.yml down -v
```

### Production

```bash
# Запуск production окружения
docker-compose -f docker-compose.prod.yml up -d

# Проверка состояния
docker-compose -f docker-compose.prod.yml ps

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f

# Масштабирование сервисов
docker-compose -f docker-compose.prod.yml up -d --scale backend=3
docker-compose -f docker-compose.prod.yml up -d --scale worker=2
```

### Команды внутри контейнеров

```bash
# Django shell
docker-compose -f docker-compose.dev.yml exec backend python manage.py shell

# Django migrations
docker-compose -f docker-compose.dev.yml exec backend python manage.py migrate

# Django collectstatic
docker-compose -f docker-compose.dev.yml exec backend python manage.py collectstatic

# Celery flower (monitoring)
docker-compose -f docker-compose.dev.yml exec worker celery flower
```

## Production

### Environment Variables

Создайте `.env.prod` файл:

```env
# Database
DB_PASSWORD=your-secure-database-password

# Redis
REDIS_PASSWORD=your-secure-redis-password

# Django
SECRET_KEY=your-super-secret-django-key

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

### SSL/TLS

```bash
# Генерация SSL сертификатов (Let's Encrypt)
sudo apt install certbot
sudo certbot certonly --standalone -d zavod.example.com

# Копирование сертификатов
sudo cp /etc/letsencrypt/live/zavod.example.com/fullchain.pem ./nginx/ssl/
sudo cp /etc/letsencrypt/live/zavod.example.com/privkey.pem ./nginx/ssl/
```

### Nginx Configuration

```nginx
# nginx/nginx.conf
upstream backend {
    server backend:8000;
}

upstream frontend {
    server frontend:3000;
}

server {
    listen 80;
    server_name zavod.example.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name zavod.example.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # Static files
    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /app/media/;
        expires 1M;
        add_header Cache-Control "public";
    }

    # API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Backup и Recovery

```bash
# Backup базы данных
docker-compose -f docker-compose.prod.yml exec db pg_dump -U zavod_user zavod > backup.sql

# Restore базы данных
docker-compose -f docker-compose.prod.yml exec -T db psql -U zavod_user -d zavod < backup.sql

# Backup volumes
docker run --rm -v postgres_data:/volume -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /volume .

# Restore volumes
docker run --rm -v postgres_data:/volume -v $(pwd):/backup alpine tar xzf /backup/postgres_backup.tar.gz -C /volume
```

## Мониторинг

### Health Checks

```python
# backend/health.py
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db import connection
from redis import Redis

@require_GET
def health_check(request):
    """Health check endpoint"""
    try:
        # Проверка базы данных
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "ok"
    except Exception:
        db_status = "error"
    
    try:
        # Проверка Redis
        redis = Redis(host='redis', port=6379, db=0)
        redis.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "error"
    
    status = "ok" if db_status == "ok" and redis_status == "ok" else "error"
    
    return JsonResponse({
        "status": status,
        "database": db_status,
        "redis": redis_status
    })
```

### Prometheus Configuration

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'zavod-backend'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics/'
  
  - job_name: 'zavod-frontend'
    static_configs:
      - targets: ['frontend:3000']
    metrics_path: '/metrics/'
  
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:6379']
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['db:5432']
```

### Grafana Dashboards

```json
{
  "dashboard": {
    "title": "Zavod Monitoring",
    "panels": [
      {
        "title": "API Requests",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(django_http_requests_total[5m])",
            "legendFormat": "{{method}} {{status_code}}"
          }
        ]
      },
      {
        "title": "Database Connections",
        "type": "graph",
        "targets": [
          {
            "expr": "pg_stat_database_numbackends",
            "legendFormat": "Connections"
          }
        ]
      },
      {
        "title": "Celery Tasks",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(celery_task_sent_total[5m])",
            "legendFormat": "Tasks Sent"
          },
          {
            "expr": "rate(celery_task_succeeded_total[5m])",
            "legendFormat": "Tasks Succeeded"
          }
        ]
      }
    ]
  }
}
```

### Логирование

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/app/logs/django.log',
            'formatter': 'verbose',
        },
        'celery': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/app/logs/celery.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file'],
    },
    'loggers': {
        'celery': {
            'handlers': ['celery'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
```

---

**Далее:**
- [Kubernetes](./kubernetes.md) - Деплоймент в Kubernetes
- [AWS](./aws.md) - AWS deployment
- [Monitoring](../08-guides/best-practices.md) - Best practices
