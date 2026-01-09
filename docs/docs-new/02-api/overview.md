# API Документация

Этот раздел содержит полную документацию по REST API системы Zavod.

## Содержание

- [Обзор](#обзор)
- [Аутентификация](#аутентификация)
- [Структура ответов](#структура-ответов)
- [Коды ошибок](#коды-ошибок)
- [Эндпоинты](#эндпоинты)
  - [Клиенты](#клиенты)
  - [Посты](#посты)
  - [Темы](#темы)
  - [Тренды](#тренды)
  - [Истории](#истории)
  - [Шаблоны](#шаблоны)
  - [Расписания](#расписания)
  - [Социальные сети](#социальные-сети)
  - [Аналитика](#аналитика)

## Обзор

API построено на Django REST Framework и предоставляет полный доступ ко всем функциям системы.

### Базовый URL

```
http://localhost:8000/api/
```

### Формат данных

- **Content-Type**: `application/json`
- **Аутентификация**: JWT токены
- **Multi-tenant**: Все запросы автоматически фильтруются по клиенту

## Аутентификация

### Telegram Auth

**POST** `/api/auth/telegram`

Аутентификация через Telegram WebApp.

```json
{
  "id": 123456789,
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "photo_url": "https://t.me/i/userpic/320/username.jpg",
  "auth_date": 1234567890
}
```

**Ответ:**
```json
{
  "user": {
    "telegramId": "123456789",
    "firstName": "John",
    "lastName": "Doe",
    "username": "johndoe",
    "photoUrl": "https://t.me/i/userpic/320/username.jpg",
    "authDate": "2024-01-01T00:00:00Z",
    "isDev": false
  }
}
```

### JWT Token

**POST** `/api/auth/token/`

Получение JWT токена.

```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**Ответ:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

### Refresh Token

**POST** `/api/auth/refresh/`

Обновление JWT токена.

```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

## Структура ответов

### Успешный ответ

```json
{
  "success": true,
  "data": {
    // Данные
  }
}
```

### Ошибочный ответ

```json
{
  "success": false,
  "error": "Описание ошибки"
}
```

## Коды ошибок

- `200` - Успешно
- `201` - Создано
- `400` - Неверный запрос
- `401` - Неавторизовано
- `403` - Доступ запрещен
- `404` - Не найдено
- `500` - Внутренняя ошибка сервера

## Эндпоинты

### Клиенты

#### GET `/api/client/info/`

Получение информации о клиенте и пользователе.

**Ответ:**
```json
{
  "client": {
    "id": 1,
    "name": "Client Name",
    "slug": "client-slug"
  },
  "role": "owner"
}
```

#### GET `/api/client/summary/`

Статистика по клиенту.

**Ответ:**
```json
{
  "total_posts": 150,
  "posts_scheduled": 25,
  "posts_published": 120,
  "by_platform": [
    {
      "platform": "instagram",
      "count": 50
    }
  ]
}
```

#### GET `/api/client/settings/`

Настройки клиента.

**Ответ:**
```json
{
  "slug": "client-slug",
  "timezone": "Europe/Helsinki",
  "avatar": "Портрет ЦА...",
  "pains": "Проблемы...",
  "desires": "Желания...",
  "objections": "Возражения..."
}
```

#### PATCH `/api/client/settings/`

Обновление настроек клиента.

**Тело запроса:**
```json
{
  "timezone": "Europe/Moscow",
  "avatar": "Новый портрет ЦА"
}
```

### Посты

#### GET `/api/posts/`

Список постов.

**Параметры:**
- `status` - фильтр по статусу
- `platform` - фильтр по платформе

**Ответ:**
```json
[
  {
    "id": 1,
    "title": "Post Title",
    "status": "published",
    "created_at": "2024-01-01T00:00:00Z",
    "platforms": ["instagram", "telegram"]
  }
]
```

#### GET `/api/posts/{id}/`

Детали поста.

**Ответ:**
```json
{
  "id": 1,
  "title": "Post Title",
  "text": "Post content...",
  "status": "published",
  "tags": ["ai", "instagram"],
  "images": [
    {
      "id": 1,
      "image": "https://example.com/image.jpg",
      "alt_text": "Image description"
    }
  ]
}
```

#### POST `/api/posts/`

Создание поста.

**Тело запроса:**
```json
{
  "title": "Post Title",
  "text": "Post content...",
  "status": "draft",
  "tags": ["ai", "instagram"]
}
```

#### PATCH `/api/posts/{id}/`

Обновление поста.

#### POST `/api/posts/{id}/generate_image/`

Генерация изображения.

**Тело запроса:**
```json
{
  "model": "pollinations"
}
```

#### POST `/api/posts/{id}/generate_video/`

Генерация видео.

**Тело запроса:**
```json
{
  "method": "wan",
  "source": "image"
}
```

#### POST `/api/posts/{id}/regenerate_text/`

Регенерация текста.

#### POST `/api/posts/{id}/quick_publish/`

Быстрая публикация.

**Тело запроса:**
```json
{
  "social_account_id": 1
}
```

### Темы

#### GET `/api/topics/`

Список тем.

**Ответ:**
```json
[
  {
    "id": 1,
    "name": "Topic Name",
    "keywords": ["keyword1", "keyword2"],
    "is_active": true,
    "use_google_trends": true
  }
]
```

#### POST `/api/topics/`

Создание темы.

#### PATCH `/api/topics/{id}/`

Обновление темы.

#### POST `/api/topics/{id}/discover_content/`

Поиск контента по теме.

#### POST `/api/topics/{id}/generate_posts/`

Генерация постов из трендов.

#### POST `/api/topics/{id}/generate_seo/`

Генерация SEO-ключей.

### Тренды

#### GET `/api/trends/`

Список трендов.

**Параметры:**
- `topic` - фильтр по теме
- `unused` - только неиспользованные

**Ответ:**
```json
[
  {
    "id": 1,
    "topic": 1,
    "title": "Trend Title",
    "description": "Trend description...",
    "source": "google_trends",
    "used_for_post": null
  }
]
```

#### POST `/api/trends/{id}/generate_post/`

Генерация поста из тренда.

#### POST `/api/trends/{id}/generate_story/`

Генерация истории из тренда.

**Тело запроса:**
```json
{
  "episode_count": 3
}
```

### Истории

#### GET `/api/stories/`

Список историй.

#### POST `/api/stories/`

Создание истории.

**Тело запроса:**
```json
{
  "title": "Story Title",
  "trend_item": 1,
  "template": 1,
  "episode_count": 5
}
```

#### POST `/api/stories/{id}/generate_posts/`

Генерация постов из эпизодов.

### Шаблоны

#### GET `/api/templates/`

Список шаблонов.

**Ответ:**
```json
[
  {
    "id": 1,
    "name": "Template Name",
    "type": "selling",
    "tone": "professional",
    "length": "medium",
    "language": "ru",
    "is_default": true
  }
]
```

#### POST `/api/templates/`

Создание шаблона.

**Тело запроса:**
```json
{
  "name": "New Template",
  "type": "selling",
  "tone": "professional",
  "length": "medium",
  "language": "ru",
  "seo_prompt_template": "SEO prompt...",
  "trend_prompt_template": "Trend prompt..."
}
```

### Расписания

#### GET `/api/schedules/`

Список расписаний.

**Ответ:**
```json
[
  {
    "id": 1,
    "platform": "instagram",
    "post_title": "Post Title",
    "scheduled_at": "2024-01-01T00:00:00Z",
    "status": "pending"
  }
]
```

#### POST `/api/schedules/`

Создание расписания.

**Тело запроса:**
```json
{
  "post": 1,
  "social_account": 1,
  "scheduled_at": "2024-01-01T00:00:00Z",
  "status": "pending"
}
```

#### POST `/api/schedules/{id}/publish_now/`

Публикация немедленно.

### Социальные сети

#### GET `/api/social-accounts/`

Список социальных аккаунтов.

**Ответ:**
```json
[
  {
    "id": 1,
    "platform": "instagram",
    "name": "Instagram Account",
    "username": "username",
    "is_active": true
  }
]
```

#### POST `/api/social-accounts/`

Создание социального аккаунта.

**Тело запроса:**
```json
{
  "platform": "instagram",
  "name": "New Account",
  "username": "newusername",
  "access_token": "token123"
}
```

### Аналитика

#### POST `/api/tg_channel/`

Анализ Telegram канала.

**Тело запроса:**
```json
{
  "action": "analyze",
  "channel_url": "https://t.me/example",
  "channel_type": "telegram"
}
```

**Ответ:**
```json
{
  "success": true,
  "message": "Channel analysis started",
  "task_id": "mock_task_123"
}
```

---

**Далее:**
- [Authentication](./authentication.md) - Подробнее об аутентификации
- [Clients](./clients.md) - Работа с клиентами
- [Posts](./posts.md) - Полная документация по постам
