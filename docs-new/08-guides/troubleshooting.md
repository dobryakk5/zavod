# Troubleshooting

В этом документе собраны常见 проблемы и их решения для системы Zavod.

## Содержание

- [Backend проблемы](#backend-проблемы)
- [Frontend проблемы](#frontend-проблемы)
- [AI интеграция](#ai-интеграция)
- [Social интеграция](#social-интеграция)
- [Docker проблемы](#docker-проблемы)
- [Celery и очереди](#celery-и-очереди)
- [База данных](#база-данных)
- [Производительность](#производительность)

## Backend проблемы

### 1. Django не запускается

**Проблема:** `python manage.py runserver` выдает ошибку

**Решения:**

```bash
# Проверка зависимостей
pip install -r requirements.txt

# Проверка миграций
python manage.py check

# Применение миграций
python manage.py migrate

# Проверка переменных окружения
echo $DATABASE_URL
echo $SECRET_KEY
```

**Частые ошибки:**

- **ModuleNotFoundError**: Убедитесь, что виртуальное окружение активировано
- **OperationalError (psycopg2)**: Проверьте подключение к PostgreSQL
- **ImproperlyConfigured**: Проверьте `.env` файл и переменные окружения

### 2. CORS ошибки

**Проблема:** Frontend не может подключиться к backend

**Решение:**

```python
# config/settings/dev.py
CORS_ALLOW_ALL_ORIGINS = True

# Или конкретные домены
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

### 3. JWT аутентификация не работает

**Проблема:** Ошибки аутентификации

**Решение:**

```python
# Проверка настроек JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Проверка middleware
MIDDLEWARE = [
    # ...
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # ...
]
```

### 4. Multi-tenant изоляция не работает

**Проблема:** Данные одного клиента видны другому

**Решение:**

```python
# Проверка middleware
# config/settings.py
MIDDLEWARE = [
    # ...
    'core.middleware.TenantMiddleware',
    # ...
]

# Проверка queryset фильтрации
class TenantViewSet(ModelViewSet):
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            queryset = queryset.filter(client=tenant)
        return queryset
```

## Frontend проблемы

### 1. Next.js не запускается

**Проблема:** `npm run dev` выдает ошибку

**Решение:**

```bash
# Установка зависимостей
npm install

# Проверка Node.js версии
node --version  # Должно быть 18+

# Очистка кэша
rm -rf node_modules .next
npm install
npm run dev
```

### 2. API запросы не работают

**Проблема:** Ошибки при запросах к backend

**Решение:**

```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```typescript
// lib/api/client.ts
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Проверка интерцепторов
apiClient.interceptors.request.use((config) => {
  console.log('Request:', config);
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);
```

### 3. Telegram Auth не работает

**Проблема:** Не удается авторизоваться через Telegram

**Решение:**

```typescript
// Проверка хеша
function validateTelegramData(data: any): boolean {
  const secret = crypto.createHash('sha256').update(BOT_TOKEN).digest();
  const checkString = Object.keys(data)
    .filter(key => key !== 'hash')
    .sort()
    .map(key => `${key}=${data[key]}`)
    .join('\n');
  
  const hash = crypto
    .createHmac('sha256', secret)
    .update(checkString)
    .digest('hex');
  
  return hash === data.hash;
}
```

### 4. React Query кэширование

**Проблема:** Данные не обновляются

**Решение:**

```typescript
// Принудительное обновление
const queryClient = useQueryClient();
queryClient.invalidateQueries({ queryKey: ['posts'] });

// Настройка рефреша
useQuery({
  queryKey: ['posts'],
  queryFn: () => postsApi.list(),
  refetchInterval: 30000, // Каждые 30 секунд
});
```

## AI интеграция

### 1. OpenAI API не работает

**Проблема:** Ошибки при генерации текста

**Решение:**

```python
# Проверка подключения
import openai

client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Test"}],
        max_tokens=10
    )
    print("OpenAI connection: OK")
except Exception as e:
    print(f"OpenAI error: {e}")
```

**Частые проблемы:**

- **Invalid API key**: Проверьте `OPENAI_API_KEY`
- **Rate limit**: Добавьте задержку между запросами
- **Quota exceeded**: Проверьте лимиты в кабинете OpenAI

### 2. Stability AI не работает

**Проблема:** Ошибки при генерации изображений

**Решение:**

```python
# Проверка API
import requests

def test_stability():
    url = "https://api.stability.ai/v1/user/account"
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print("Stability AI: OK")
    except Exception as e:
        print(f"Stability AI error: {e}")

test_stability()
```

**Частые проблемы:**

- **Invalid API key**: Проверьте `STABILITY_API_KEY`
- **Model not found**: Проверьте название модели
- **Credit limit**: Проверьте баланс на аккаунте

### 3. Runway ML не работает

**Проблема:** Ошибки при генерации видео

**Решение:**

```python
# Проверка аутентификации
import requests

def test_runway():
    url = f"{RUNWAY_API_URL}/user"
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print("Runway ML: OK")
    except Exception as e:
        print(f"Runway ML error: {e}")

test_runway()
```

## Social интеграция

### 1. Instagram Graph API

**Проблема:** Ошибки публикации в Instagram

**Решение:**

```python
# Проверка токена
def check_instagram_token(access_token):
    url = f"https://graph.facebook.com/me"
    params = {
        'access_token': access_token,
        'fields': 'id,name'
    }
    
    response = requests.get(url, params=params)
    return response.json()

# Проверка прав
def check_permissions(access_token):
    url = f"https://graph.facebook.com/debug_token"
    params = {
        'input_token': access_token,
        'access_token': access_token
    }
    
    response = requests.get(url, params=params)
    return response.json()
```

**Частые проблемы:**

- **Invalid session**: Токен устарел, нужно переавторизоваться
- **Permissions**: Недостаточно прав, запросите `instagram_content_publish`
- **Sandbox mode**: Приложение в песочнице, публикация только для тестовых пользователей

### 2. Telegram Bot API

**Проблема:** Ошибки публикации в Telegram

**Решение:**

```python
# Проверка бота
def check_telegram_bot(token):
    url = f"https://api.telegram.org/bot{token}/getMe"
    
    response = requests.get(url)
    return response.json()

# Проверка канала
def check_telegram_channel(token, chat_id):
    url = f"https://api.telegram.org/bot{token}/getChat"
    data = {'chat_id': chat_id}
    
    response = requests.post(url, data=data)
    return response.json()
```

**Частые проблемы:**

- **Bad Request: chat not found**: Бот не является администратором канала
- **Forbidden**: Бот заблокирован или удален
- **Message too long**: Сообщение превышает лимит

### 3. YouTube Data API

**Проблема:** Ошибки загрузки видео на YouTube

**Решение:**

```python
# Проверка аутентификации
from googleapiclient.discovery import build

def check_youtube_auth(credentials):
    try:
        youtube = build('youtube', 'v3', credentials=credentials)
        request = youtube.channels().list(
            part='snippet,contentDetails,statistics',
            mine=True
        )
        response = request.execute()
        print("YouTube: OK")
        return True
    except Exception as e:
        print(f"YouTube error: {e}")
        return False
```

**Частые проблемы:**

- **quotaExceeded**: Превышен лимит квот
- **invalidGrant**: Срок действия OAuth токена истек
- **forbidden**: Недостаточно прав для загрузки видео

## Docker проблемы

### 1. Контейнеры не запускаются

**Проблема:** `docker-compose up` выдает ошибку

**Решение:**

```bash
# Проверка Docker
docker --version
docker-compose --version

# Очистка
docker system prune -f
docker volume prune -f

# Пересборка
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 2. Подключение к базе данных

**Проблема:** Backend не может подключиться к PostgreSQL

**Решение:**

```bash
# Проверка подключения
docker-compose exec db psql -U zavod_user -d zavod -c "SELECT 1;"

# Проверка сетевых настроек
docker-compose exec backend ping db
docker-compose exec backend nslookup db
```

### 3. Volume проблемы

**Проблема:** Данные не сохраняются

**Решение:**

```yaml
# Проверка volumes в docker-compose.yml
volumes:
  postgres_data:
    driver: local

services:
  db:
    volumes:
      - postgres_data:/var/lib/postgresql/data
```

```bash
# Проверка volumes
docker volume ls
docker volume inspect zavod_postgres_data
```

## Celery и очереди

### 1. Celery worker не запускается

**Проблема:** `celery -A config worker` выдает ошибку

**Решение:**

```bash
# Проверка Redis
redis-cli ping

# Проверка подключения
python -c "import redis; r = redis.Redis(); print(r.ping())"

# Запуск с debug
celery -A config worker -l debug
```

### 2. Задачи не выполняются

**Проблема:** Задачи в очереди, но не выполняются

**Решение:**

```python
# Проверка подключения к брокеру
from celery import current_app
inspector = current_app.control.inspect()
print(inspector.active())

# Проверка очереди
print(inspector.scheduled())

# Принудительный запуск задачи
from myapp.tasks import my_task
result = my_task.delay()
print(result.ready())
print(result.result)
```

### 3. Redis проблемы

**Проблема:** Redis не доступен

**Решение:**

```bash
# Проверка Redis
redis-cli ping

# Проверка конфигурации
redis-cli config get '*'

# Очистка очереди
redis-cli flushall

# Проверка подключения из Python
python -c "
import redis
r = redis.Redis()
r.set('test', 'value')
print(r.get('test'))
"
```

## База данных

### 1. PostgreSQL не запускается

**Проблема:** Ошибки при запуске PostgreSQL

**Решение:**

```bash
# Проверка прав доступа
sudo chown -R postgres:postgres /var/lib/postgresql/data

# Проверка логов
docker-compose logs db

# Сброс базы данных
docker-compose down -v
docker-compose up -d
```

### 2. Миграции не применяются

**Проблема:** `python manage.py migrate` выдает ошибку

**Решение:**

```bash
# Проверка состояния миграций
python manage.py showmigrations

# Принудительное применение
python manage.py migrate --fake-initial

# Сброс миграций (только для development)
python manage.py migrate --run-syncdb
```

### 3. Данные не сохраняются

**Проблема:** Данные теряются после перезапуска

**Решение:**

```python
# Проверка настроек базы данных
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'zavod',
        'USER': 'zavod_user',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
        'OPTIONS': {
            'options': '-c default_transaction_isolation=2'
        }
    }
}
```

## Производительность

### 1. Медленная работа API

**Проблема:** Запросы выполняются медленно

**Решение:**

```python
# Добавление индексов
class Post(models.Model):
    title = models.CharField(max_length=255)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    
    class Meta:
        indexes = [
            models.Index(fields=['client', 'created_at']),
            models.Index(fields=['status']),
        ]

# Оптимизация запросов
def get_posts():
    return Post.objects.select_related('client').prefetch_related('images')

# Кэширование
from django.core.cache import cache

def get_expensive_data():
    data = cache.get('expensive_data')
    if data is None:
        data = calculate_expensive_data()
        cache.set('expensive_data', data, 3600)  # 1 час
    return data
```

### 2. Высокое потребление памяти

**Проблема:** Сервисы потребляют много памяти

**Решение:**

```python
# Оптимизация Celery
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000  # 200MB

# Оптимизация Django
CONN_MAX_AGE = 600  # Persistent connections

# Оптимизация запросов
# Используйте pagination
from django.core.paginator import Paginator

def get_paginated_posts(request):
    posts = Post.objects.all()
    paginator = Paginator(posts, 20)
    page = paginator.get_page(request.GET.get('page'))
    return page
```

### 3. Медленная загрузка файлов

**Проблема:** Загрузка изображений/видео работает медленно

**Решение:**

```python
# Асинхронная загрузка
@shared_task
def upload_file_to_storage(file_path, storage_path):
    # Загрузка в облако (S3, GCS)
    storage_client = get_storage_client()
    storage_client.upload_file(file_path, storage_path)

# CDN для статики
STATIC_URL = 'https://cdn.example.com/static/'

# Оптимизация изображений
from PIL import Image

def optimize_image(image_path):
    with Image.open(image_path) as img:
        img = img.convert('RGB')
        img.save(image_path, 'JPEG', quality=85, optimize=True)
```

---

**Если проблема не решена:**

1. Проверьте логи:
   ```bash
   docker-compose logs -f
   tail -f /var/log/django.log
   ```

2. Проверьте мониторинг:
   - Grafana: http://localhost:3001
   - Prometheus: http://localhost:9090

3. Создайте issue в репозитории с описанием проблемы
