# Social Integration

В этом документе описана интеграция с социальными сетями для автоматической публикации контента.

## Содержание

- [Поддерживаемые платформы](#поддерживаемые-платформы)
- [Instagram](#instagram)
- [Telegram](#telegram)
- [YouTube](#youtube)
- [Модель данных](#модель-данных)
- [Публикация](#публикация)
- [Очередь задач](#очередь-задач)

## Поддерживаемые платформы

Система поддерживает публикацию в следующих социальных сетях:

1. **Instagram** - через Instagram Graph API
2. **Telegram** - через Bot API
3. **YouTube** - через YouTube Data API

### Требования

Для каждой платформы необходимы:
- API ключи/токены
- Соответствующие разрешения
- Настроенные аккаунты в системе

## Instagram

### Требования

1. **Instagram Business Account**
2. **Facebook Page** (привязанный к Instagram)
3. **Meta Developer App** с необходимыми permissions:
   - `instagram_content_publish`
   - `pages_read_engagement`
   - `pages_manage_posts`

### Настройка

#### 1. Регистрация приложения

1. Перейдите в [Meta for Developers](https://developers.facebook.com/)
2. Создайте новое приложение
3. Добавьте продукт "Instagram"
4. Настройте Instagram Business Account

#### 2. Получение токенов

```python
# В Django Admin создайте SocialAccount
{
    "platform": "instagram",
    "name": "Instagram Business",
    "username": "your_business_account",
    "access_token": "EAABs...",
    "extra": {
        "page_id": "123456789",
        "instagram_business_account_id": "17841400000000000"
    }
}
```

#### 3. Permissions

Необходимые разрешения:
- `instagram_content_publish` - для публикации
- `pages_read_engagement` - для чтения данных
- `pages_manage_posts` - для управления постами

### Публикация

#### Создание медиа

```python
import requests

def create_instagram_media(access_token, image_url, caption):
    """Создание медиа объекта"""
    url = f"https://graph.facebook.com/v18.0/{instagram_business_account_id}/media"
    
    data = {
        'image_url': image_url,
        'caption': caption,
        'access_token': access_token
    }
    
    response = requests.post(url, data=data)
    response.raise_for_status()
    
    return response.json()['id']  # creation_id
```

#### Публикация

```python
def publish_instagram_media(access_token, creation_id):
    """Публикация медиа"""
    url = f"https://graph.facebook.com/v18.0/{instagram_business_account_id}/media_publish"
    
    data = {
        'creation_id': creation_id,
        'access_token': access_token
    }
    
    response = requests.post(url, data=data)
    response.raise_for_status()
    
    return response.json()['id']  # media_id
```

#### Пример использования

```python
def publish_to_instagram(post, social_account):
    try:
        # 1. Создание медиа
        creation_id = create_instagram_media(
            social_account.access_token,
            post.image.url,
            post.text
        )
        
        # 2. Публикация
        media_id = publish_instagram_media(
            social_account.access_token,
            creation_id
        )
        
        return {
            'success': True,
            'media_id': media_id,
            'url': f"https://www.instagram.com/p/{media_id}/"
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
```

## Telegram

### Требования

1. **Telegram Bot** (созданный через @BotFather)
2. **Канал** или **чат** для публикации
3. **Bot является администратором канала**

### Настройка

#### 1. Создание бота

1. Найдите @BotFather в Telegram
2. Отправьте `/newbot`
3. Следуйте инструкциям для создания бота
4. Скопируйте токен

#### 2. Настройка канала

1. Создайте канал в Telegram
2. Добавьте бота как администратора
3. Дайте права:
   - Публикация сообщений
   - Редактирование сообщений (опционально)

#### 3. Сохранение в системе

```python
# В Django Admin создайте SocialAccount
{
    "platform": "telegram",
    "name": "Telegram Channel",
    "username": "your_channel_username",
    "access_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "extra": {
        "channel_id": "@your_channel",
        "chat_id": "-1001234567890"
    }
}
```

### Публикация

#### Текст и изображение

```python
import requests

def send_telegram_photo(bot_token, chat_id, photo_url, caption):
    """Отправка фото с подписью"""
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    data = {
        'chat_id': chat_id,
        'caption': caption,
        'parse_mode': 'HTML'
    }
    
    files = {
        'photo': requests.get(photo_url).content
    }
    
    response = requests.post(url, data=data, files=files)
    response.raise_for_status()
    
    return response.json()
```

#### Видео

```python
def send_telegram_video(bot_token, chat_id, video_url, caption):
    """Отправка видео"""
    url = f"https://api.telegram.org/bot{bot_token}/sendVideo"
    
    data = {
        'chat_id': chat_id,
        'caption': caption,
        'parse_mode': 'HTML'
    }
    
    files = {
        'video': requests.get(video_url).content
    }
    
    response = requests.post(url, data=data, files=files)
    response.raise_for_status()
    
    return response.json()
```

#### Пример использования

```python
def publish_to_telegram(post, social_account):
    try:
        bot_token = social_account.access_token
        chat_id = social_account.extra.get('chat_id')
        
        if post.video:
            # Публикация видео
            result = send_telegram_video(
                bot_token,
                chat_id,
                post.video.url,
                post.text
            )
        elif post.image:
            # Публикация изображения
            result = send_telegram_photo(
                bot_token,
                chat_id,
                post.image.url,
                post.text
            )
        else:
            # Публикация текста
            result = send_telegram_text(
                bot_token,
                chat_id,
                post.text
            )
        
        return {
            'success': True,
            'message_id': result['result']['message_id'],
            'url': f"https://t.me/{social_account.username}/{result['result']['message_id']}"
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
```

## YouTube

### Требования

1. **YouTube Channel**
2. **Google Cloud Project** с включенным YouTube Data API
3. **OAuth 2.0 Credentials**

### Настройка

#### 1. Создание проекта

1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
2. Создайте новый проект
3. Включите YouTube Data API v3

#### 2. OAuth 2.0

1. В Google Cloud Console создайте OAuth 2.0 Credentials
2. Укажите redirect URI: `http://localhost:8000/api/auth/youtube/callback/`
3. Добавьте scope: `https://www.googleapis.com/auth/youtube.upload`

#### 3. Авторизация канала

```python
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

def authorize_youtube_channel():
    """Авторизация YouTube канала"""
    flow = InstalledAppFlow.from_client_secrets_file(
        'client_secret.json',
        scopes=['https://www.googleapis.com/auth/youtube.upload']
    )
    
    credentials = flow.run_local_server(port=0)
    
    # Сохранение credentials
    return credentials.to_json()
```

#### 4. Сохранение в системе

```python
# В Django Admin создайте SocialAccount
{
    "platform": "youtube",
    "name": "YouTube Channel",
    "username": "your_channel_name",
    "access_token": "ya29...",
    "refresh_token": "1//0g...",
    "extra": {
        "channel_id": "UC123...",
        "client_id": "123-abc.apps.googleusercontent.com",
        "client_secret": "secret123"
    }
}
```

### Публикация

#### Загрузка видео

```python
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os

def upload_youtube_video(credentials_data, video_path, title, description):
    """Загрузка видео на YouTube"""
    
    # Авторизация
    from google.oauth2.credentials import Credentials
    credentials = Credentials.from_authorized_user_info(
        eval(credentials_data)
    )
    
    youtube = build('youtube', 'v3', credentials=credentials)
    
    # Метаданные видео
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['automated upload', 'zavod'],
            'categoryId': '22'  # People & Blogs
        },
        'status': {
            'privacyStatus': 'private',  # Сначала приватно
            'publishAt': None  # Можно указать время публикации
        }
    }
    
    # Загрузка
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")
    
    return response['id']
```

#### Публикация

```python
def publish_youtube_video(youtube, video_id, publish_time=None):
    """Публикация видео"""
    
    body = {
        'id': video_id,
        'status': {
            'privacyStatus': 'public'
        }
    }
    
    if publish_time:
        body['status']['publishAt'] = publish_time
    
    request = youtube.videos().update(
        part='status',
        body=body
    )
    
    response = request.execute()
    return response
```

#### Пример использования

```python
def publish_to_youtube(post, social_account):
    try:
        # Загрузка видео
        video_id = upload_youtube_video(
            social_account.access_token,
            post.video.file.path,
            post.title,
            post.text
        )
        
        # Публикация (немедленно или по расписанию)
        if post.schedule_time:
            publish_youtube_video(
                youtube,
                video_id,
                post.schedule_time.isoformat()
            )
        else:
            publish_youtube_video(youtube, video_id)
        
        return {
            'success': True,
            'video_id': video_id,
            'url': f"https://www.youtube.com/watch?v={video_id}"
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }
```

## Модель данных

### SocialAccount

```python
# models.py
class SocialAccount(models.Model):
    PLATFORM_CHOICES = [
        ('instagram', 'Instagram'),
        ('telegram', 'Telegram'),
        ('youtube', 'YouTube'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    name = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    extra = models.JSONField(default=dict, blank=True)
    
    class Meta:
        unique_together = ('client', 'platform', 'username')
```

### Schedule

```python
class Schedule(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('published', 'Published'),
        ('failed', 'Failed'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE)
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    external_id = models.CharField(max_length=255, blank=True)
    log = models.TextField(blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
```

## Публикация

### Celery задача

```python
# tasks.py
from celery import shared_task
from .models import Schedule, SocialAccount
from .services import publish_services

@shared_task
def publish_to_social_media(schedule_id):
    """Публикация в социальную сеть"""
    try:
        schedule = Schedule.objects.get(id=schedule_id)
        social_account = schedule.social_account
        post = schedule.post
        
        # Выбор сервиса публикации
        service = publish_services.get(social_account.platform)
        
        if not service:
            raise ValueError(f"Unsupported platform: {social_account.platform}")
        
        # Публикация
        result = service.publish(post, social_account)
        
        # Обновление статуса
        if result['success']:
            schedule.status = 'published'
            schedule.external_id = result.get('external_id')
            schedule.published_at = timezone.now()
        else:
            schedule.status = 'failed'
            schedule.log = result.get('error', 'Unknown error')
        
        schedule.save()
        
        return result
        
    except Exception as e:
        # Логирование ошибки
        schedule.status = 'failed'
        schedule.log = str(e)
        schedule.save()
        
        return {'success': False, 'error': str(e)}
```

### Сервисы публикации

```python
# services/publish_services.py
from .instagram import InstagramPublisher
from .telegram import TelegramPublisher
from .youtube import YouTubePublisher

class PublishService:
    def publish(self, post, social_account):
        raise NotImplementedError

class PublishServices:
    def __init__(self):
        self.services = {
            'instagram': InstagramPublisher(),
            'telegram': TelegramPublisher(),
            'youtube': YouTubePublisher(),
        }
    
    def get(self, platform):
        return self.services.get(platform)

publish_services = PublishServices()
```

## Очередь задач

### Планирование публикаций

```python
# tasks.py
from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone

@shared_task
def process_schedules():
    """Обработка запланированных публикаций"""
    now = timezone.now()
    
    # Находим задачи, которые нужно выполнить
    schedules = Schedule.objects.filter(
        status='pending',
        scheduled_at__lte=now
    ).select_related('post', 'social_account')
    
    for schedule in schedules:
        # Запуск публикации
        publish_to_social_media.delay(schedule.id)
```

### Celery Beat расписание

```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'process-schedules': {
        'task': 'core.tasks.process_schedules',
        'schedule': crontab(minute='*/5'),  # Каждые 5 минут
    },
}
```

### Ретраи и обработка ошибок

```python
@shared_task(bind=True, max_retries=3)
def publish_to_social_media(self, schedule_id):
    try:
        # Логика публикации
        pass
        
    except Exception as exc:
        # Ретраи с экспоненциальной задержкой
        retry_count = self.request.retries
        if retry_count < self.max_retries:
            raise self.retry(exc=exc, countdown=60 * (2 ** retry_count))
        
        # После всех ретраев - помечаем как failed
        schedule = Schedule.objects.get(id=schedule_id)
        schedule.status = 'failed'
        schedule.log = f"Max retries exceeded: {exc}"
        schedule.save()
```

---

**Далее:**
- [Instagram](./instagram.md) - Подробнее об Instagram интеграции
- [Telegram](./telegram.md) - Подробнее о Telegram интеграции
- [YouTube](./youtube.md) - Подробнее о YouTube интеграции
- [Deployment](../07-deployment/docker.md) - Деплоймент системы
