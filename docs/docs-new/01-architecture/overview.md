# Архитектура системы

В этом документе описана архитектура системы автоматической генерации и публикации контента Zavod.

## Содержание

- [Обзор](#обзор)
- [Компоненты системы](#компоненты-системы)
- [Поток данных](#поток-данных)
- [Multi-tenant архитектура](#multi-tenant-архитектура)
- [Технологический стек](#технологический-стек)

## Обзор

Zavod - это SaaS-платформа для автоматической генерации и публикации контента в социальных сетях. Система объединяет AI-генерацию, сбор контента из внешних источников и автоматическую публикацию.

### Основные возможности

- **Сбор контента** из RSS, API новостей, YouTube, Instagram
- **AI-генерация** текста, изображений и видео
- **Multi-tenant** архитектура для работы с несколькими клиентами
- **Автоматическая публикация** в Instagram, Telegram, YouTube
- **Гибкое расписание** публикаций
- **Модерация** контента через веб-интерфейс

## Компоненты системы

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   AI Services   │
│   (Next.js)     │◄──►│   (Django)      │◄──►│   (OpenAI,      │
│                 │    │                 │    │   Stability,    │
│   UI/UX         │    │   Business      │    │   Runway)       │
│   Auth          │    │   Logic         │    │                 │
│   Dashboard     │    │   ORM           │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │    │   Queue         │    │   Storage       │
│   (PostgreSQL)  │    │   (Redis)       │    │   (S3/Local)    │
│                 │    │                 │    │                 │
│   Content       │    │   Celery        │    │   Images        │
│   Users         │    │   Tasks         │    │   Videos        │
│   Clients       │    │   Scheduler     │    │   Media         │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Social Networks                              │
│                                                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│   │  Instagram  │  │  Telegram   │  │   YouTube   │             │
│   │   Graph     │  │    Bot      │  │    Data     │             │
│   │    API      │  │     API     │  │     API     │             │
│   └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Frontend (Next.js)

**Ответственность:**
- Веб-интерфейс для модерации контента
- Авторизация пользователей
- Управление расписанием публикаций
- Просмотр статистики

**Ключевые особенности:**
- SSR для SEO и производительности
- TypeScript для типобезопасности
- shadcn/ui для компонентов
- React Query для управления состоянием

### Backend (Django)

**Ответственность:**
- API для frontend
- Business-логика
- Управление пользователями и ролями
- Multi-tenant изоляция

**Ключевые особенности:**
- Django REST Framework для API
- JWT аутентификация
- Django ORM для работы с БД
- Middleware для tenant-изоляции

### AI Services

**Ответственность:**
- Генерация текста (OpenAI GPT)
- Генерация изображений (Stability AI)
- Генерация видео (Runway ML)

**Ключевые особенности:**
- Асинхронная обработка
- Кэширование результатов
- Обработка ошибок и retry-логика

### Queue (Celery + Redis)

**Ответственность:**
- Асинхронные задачи
- Планирование публикаций
- Обработка AI-генерации

**Ключевые особенности:**
- Celery для фоновых задач
- Redis как брокер сообщений
- Celery Beat для расписаний
- Retry и dead-letter queue

### Database (PostgreSQL)

**Ответственность:**
- Хранение структурированных данных
- Multi-tenant изоляция
- Транзакции и целостность

**Ключевые особенности:**
- JSONB для гибких данных
- Индексы для производительности
- Репликация и бэкапы

## Поток данных

### Создание и публикация поста

```
1. Сбор контента
   ↓
2. AI-генерация (текст → изображение → видео)
   ↓
3. Сохранение в БД (статус: draft)
   ↓
4. Модерация в UI (статус: approved)
   ↓
5. Планирование публикации
   ↓
6. Celery задача по расписанию
   ↓
7. Публикация в соцсети
   ↓
8. Обновление статуса (published)
```

### Подробный workflow

1. **Сбор контента**
   - Celery Beat запускает задачу по расписанию
   - Сбор данных из RSS, API, веб-сайтов
   - Сохранение в `SourceData`

2. **AI-генерация**
   - Запуск генерации текста через OpenAI
   - Генерация изображения через Stability AI
   - Генерация видео через Runway ML (опционально)
   - Сохранение в `Content` со статусом `draft`

3. **Модерация**
   - Frontend получает список черновиков
   - Редактор просматривает и редактирует
   - Утверждение поста (статус `approved`)

4. **Планирование**
   - Выбор даты и времени публикации
   - Выбор социальных сетей
   - Создание задачи в Celery с ETA

5. **Публикация**
   - Celery worker выполняет задачу в указанное время
   - Вызов API социальной сети
   - Обновление статуса публикации

## Multi-tenant архитектура

### Принципы

Каждый клиент изолирован от других:

1. **Данные**: Все таблицы имеют `client_id`
2. **Middleware**: Автоматическая фильтрация по клиенту
3. **Роли**: owner, editor, viewer для каждого клиента
4. **Хранение**: Медиафайлы в папках по client_id

### Модель данных

```python
class Client(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    timezone = models.CharField(max_length=64)

class UserTenantRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    role = models.CharField(choices=ROLE_CHOICES)
    
    class Meta:
        unique_together = ('user', 'client')

class Content(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    text = models.TextField()
    status = models.CharField(choices=STATUS_CHOICES)
```

### Фильтрация

Middleware определяет активного клиента:

```python
class TenantMiddleware:
    def __call__(self, request):
        if request.user.is_authenticated:
            # Определение активного клиента
            # Добавление в request.tenant
        return self.get_response(request)
```

QuerySet фильтрация:

```python
class TenantManager(models.Manager):
    def get_queryset(self):
        if hasattr(self.model, 'client'):
            return super().get_queryset().filter(
                client_id=get_active_client_id()
            )
        return super().get_queryset()
```

## Технологический стек

### Backend

- **Python 3.10+** - Язык программирования
- **Django 4.2+** - Веб-фреймворк
- **Django REST Framework** - API
- **PostgreSQL** - Основная БД
- **Redis** - Очередь и кэш
- **Celery** - Асинхронные задачи
- **OpenAI API** - Текстовая генерация
- **Stability AI** - Генерация изображений
- **Runway ML** - Генерация видео

### Frontend

- **Next.js 15** - React фреймворк
- **TypeScript** - Типизация
- **Tailwind CSS** - Стили
- **shadcn/ui** - Компоненты
- **React Query** - Управление состоянием
- **Lucide React** - Иконки

### Инфраструктура

- **Docker** - Контейнеризация
- **Kubernetes** - Оркестрация
- **AWS/GCP** - Облако
- **S3/MinIO** - Хранение файлов
- **Nginx** - Обратный прокси

### DevOps

- **GitHub Actions** - CI/CD
- **Docker Compose** - Локальный запуск
- **Prometheus + Grafana** - Мониторинг
- **Sentry** - Логирование ошибок

---

**Далее:**
- [Data Flow](./data-flow.md) - Подробный поток данных
- [Multi-tenant](./multi-tenant.md) - Глубокое погружение в multi-tenant
- [API Overview](../02-api/overview.md) - Документация API
