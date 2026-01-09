# Настройка AI интеграции

В этом документе описана настройка интеграции с AI сервисами для генерации контента.

## Содержание

- [Требования](#требования)
- [OpenAI (Текст)](#openai-текст)
- [Stability AI (Изображения)](#stability-ai-изображения)
- [Runway ML (Видео)](#runway-ml-видео)
- [Настройка в Django](#настройка-в-django)
- [Тестирование](#тестирование)

## Требования

Для работы AI интеграции необходимы:

- **API ключи** от соответствующих сервисов
- **Python 3.10+** с установленными зависимостями
- **Redis** для асинхронной обработки
- **Celery** для фоновых задач

## OpenAI (Текст)

### Получение API ключа

1. Зарегистрируйтесь на [OpenAI Platform](https://platform.openai.com/)
2. Перейдите в [API Keys](https://platform.openai.com/api-keys)
3. Создайте новый ключ
4. Скопируйте и сохраните ключ (он покажется только один раз)

### Настройка

#### В Django `.env` файле:

```bash
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_ORG_ID=your-organization-id  # опционально
```

#### В `settings.py`:

```python
import os

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_ORG_ID = os.environ.get('OPENAI_ORG_ID')

# Конфигурация по умолчанию
OPENAI_DEFAULT_MODEL = 'gpt-4o-mini'
OPENAI_DEFAULT_TEMPERATURE = 0.8
OPENAI_MAX_TOKENS = 2000
```

### Использование

```python
from openai import OpenAI

client = OpenAI(api_key=OPENAI_API_KEY)

# Генерация текста
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "Ты опытный SMM-менеджер"},
        {"role": "user", "content": "Создай пост о ..."}
    ],
    temperature=0.8,
    max_tokens=1000
)

text = response.choices[0].message.content
```

### Пример промпта для генерации постов

```python
def generate_post_prompt(trend_title, trend_description, topic_name, tone='friendly', length='medium'):
    return f"""
Ты - опытный SMM-менеджер для "{topic_name}".

Создай {length} пост в {tone} стиле на русском языке.

НОВОСТЬ/ТРЕНД:
Заголовок: {trend_title}
Описание: {trend_description}

ЗАДАЧА:
1. Напиши привлекательный заголовок (до 100 символов)
2. Создай основной текст который:
   - Объясняет суть новости простым языком
   - Показывает практическую пользу для аудитории
   - Связан с темой "{topic_name}"
   - Написан в {tone} тоне
   - Имеет длину: {length}
3. Добавь эмодзи для оживления текста
4. Закончи призывом к действию

Будь креативным но информативным!
"""
```

## Stability AI (Изображения)

### Получение API ключа

1. Зарегистрируйтесь на [DreamStudio](https://dreamstudio.ai/)
2. Перейдите в [Account](https://dreamstudio.ai/account)
3. Скопируйте API ключ

### Настройка

#### В Django `.env` файле:

```bash
STABILITY_API_KEY=your-stability-api-key-here
STABILITY_ENGINE=stable-diffusion-xl-beta-v2-2-2v  # или другая модель
```

#### В `settings.py`:

```python
STABILITY_API_KEY = os.environ.get('STABILITY_API_KEY')
STABILITY_ENGINE = os.environ.get('STABILITY_ENGINE', 'stable-diffusion-xl-beta-v2-2-2v')
```

### Использование

#### Через REST API:

```python
import requests
import base64

def generate_image(prompt, width=1024, height=1024):
    url = f"https://api.stability.ai/v1/generation/{STABILITY_ENGINE}/text-to-image"
    
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "text_prompts": [
            {"text": prompt}
        ],
        "cfg_scale": 7,
        "clip_guidance_preset": "FAST_BLUE",
        "width": width,
        "height": height,
        "samples": 1,
        "steps": 30
    }
    
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    
    result = response.json()
    
    # Сохранение изображения
    for artifact in result['artifacts']:
        if artifact['finish_reason'] == 'SUCCESS':
            image_data = base64.b64decode(artifact['base64'])
            return image_data
    
    return None
```

#### Через официальный SDK:

```bash
pip install stability-sdk
```

```python
from stability_sdk import client

stability_api = client.StabilityInference(
    key=STABILITY_API_KEY,
    engine=STABILITY_ENGINE
)

def generate_image_sdk(prompt):
    answers = stability_api.generate(
        prompt=prompt,
        width=1024,
        height=1024,
        samples=1,
        cfg_scale=7.0,
        steps=30
    )
    
    for resp in answers:
        for artifact in resp.artifacts:
            if artifact.finish_reason == client.generation.FinishReason.SUCCESS:
                return artifact.binary
    
    return None
```

### Пример промпта для изображения

```python
def generate_image_prompt(post_text, topic_name, style='modern'):
    return f"""
{topic_name} - {post_text[:100]}...

Создай современное, яркое изображение в стиле {style} для поста в Instagram.
Используй сочные цвета, четкие линии, современные элементы.
Изображение должно быть квадратным (1:1), подходит для социальных сетей.
"""
```

## Runway ML (Видео)

### Получение API ключа

1. Зарегистрируйтесь на [Runway](https://runwayml.com/)
2. Перейдите в [Settings → API](https://app.runwayml.com/settings/credentials)
3. Создайте новый API ключ

### Настройка

#### В Django `.env` файле:

```bash
RUNWAY_API_KEY=your-runway-api-key-here
```

#### В `settings.py`:

```python
RUNWAY_API_KEY = os.environ.get('RUNWAY_API_KEY')
RUNWAY_API_URL = "https://api.runwayml.com/v1"
```

### Использование

#### Генерация видео из текста:

```python
import requests
import time

def generate_video_from_text(prompt, duration=10):
    """Генерация видео из текстового описания"""
    
    # Шаг 1: Создание задачи
    url = f"{RUNWAY_API_URL}/generate/video"
    
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "prompt": prompt,
        "duration": duration,
        "width": 1024,
        "height": 576,
        "fps": 30
    }
    
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    
    task = response.json()
    task_id = task['task_id']
    
    # Шаг 2: Ожидание завершения
    while True:
        status_response = requests.get(
            f"{RUNWAY_API_URL}/tasks/{task_id}",
            headers=headers
        )
        status_response.raise_for_status()
        
        status = status_response.json()
        
        if status['status'] == 'completed':
            return status['result']['video_url']
        elif status['status'] == 'failed':
            raise Exception(f"Video generation failed: {status.get('error')}")
        
        time.sleep(5)  # Ждем 5 секунд перед следующей проверкой
```

#### Генерация видео из изображения:

```python
def generate_video_from_image(image_url, motion_prompt, duration=5):
    """Генерация видео из статичного изображения"""
    
    url = f"{RUNWAY_API_URL}/generate/video-from-image"
    
    headers = {
        "Authorization": f"Bearer {RUNWAY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "image_url": image_url,
        "motion_prompt": motion_prompt,
        "duration": duration
    }
    
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()
    
    task = response.json()
    
    # Ожидание завершения (аналогично предыдущему примеру)
    return wait_for_task_completion(task['task_id'])
```

### Пример промпта для видео

```python
def generate_video_prompt(post_text, image_description):
    return f"""
Создай короткое видео (15 секунд) для Instagram Reels.

Тема: {post_text[:150]}...

Визуальный ряд:
- Начало: {image_description}
- Движение камеры: плавное приближение
- Эффекты: легкие переходы, текстовые вставки
- Музыка: современный electronic beat

Видео должно быть вертикальным (9:16), 1080x1920, 30fps.
"""
```

## Настройка в Django

### 1. Модель AI Settings

```python
# models.py
from django.db import models

class AISettings(models.Model):
    client = models.ForeignKey('core.Client', on_delete=models.CASCADE)
    
    # OpenAI
    openai_api_key = models.CharField(max_length=255, blank=True)
    openai_model = models.CharField(max_length=100, default='gpt-4o-mini')
    openai_temperature = models.FloatField(default=0.8)
    
    # Stability AI
    stability_api_key = models.CharField(max_length=255, blank=True)
    stability_engine = models.CharField(max_length=100, default='stable-diffusion-xl-beta-v2-2-2v')
    
    # Runway ML
    runway_api_key = models.CharField(max_length=255, blank=True)
    
    # Дополнительные настройки
    auto_generate_images = models.BooleanField(default=True)
    auto_generate_video = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "AI Settings"
        verbose_name_plural = "AI Settings"
```

### 2. Serializers

```python
# serializers.py
class AISettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISettings
        fields = [
            'id', 'client', 'openai_model', 'openai_temperature',
            'stability_engine', 'auto_generate_images', 'auto_generate_video'
        ]
        read_only_fields = ['id', 'client']
```

### 3. ViewSet

```python
# views.py
class AISettingsViewSet(ModelViewSet):
    serializer_class = AISettingsSerializer
    permission_classes = [IsTenantOwnerOrEditor]
    
    def get_queryset(self):
        client = get_active_client(self.request.user)
        return AISettings.objects.filter(client=client)
    
    def get_object(self):
        client = get_active_client(self.request.user)
        obj, created = AISettings.objects.get_or_create(client=client)
        return obj
```

### 4. Celery задачи

```python
# tasks.py
from celery import shared_task
from .ai_generator import AIContentGenerator

@shared_task
def generate_post_content(post_id):
    """Асинхронная генерация контента для поста"""
    try:
        generator = AIContentGenerator()
        result = generator.generate_full_post(post_id)
        
        # Обновление статуса поста
        from .models import Post
        post = Post.objects.get(id=post_id)
        post.status = 'ready'
        post.save()
        
        return {'success': True, 'post_id': post_id}
        
    except Exception as e:
        # Логирование ошибки
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating content for post {post_id}: {e}")
        
        return {'success': False, 'error': str(e)}

@shared_task
def generate_image_for_post(post_id, model='pollinations'):
    """Генерация изображения для поста"""
    try:
        generator = AIContentGenerator()
        image_data = generator.generate_image_for_post(post_id, model)
        
        # Сохранение изображения
        from .models import PostImage
        PostImage.objects.create(
            post_id=post_id,
            image=image_data,
            order=0
        )
        
        return {'success': True, 'post_id': post_id}
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating image for post {post_id}: {e}")
        return {'success': False, 'error': str(e)}
```

## Тестирование

### 1. Тестирование подключения

```python
# management/commands/test_ai.py
from django.core.management.base import BaseCommand
from openai import OpenAI
import os

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Тест OpenAI
        try:
            client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Привет!"}],
                max_tokens=10
            )
            self.stdout.write(self.style.SUCCESS("OpenAI: OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"OpenAI: {e}"))
        
        # Тест Stability AI
        try:
            import requests
            response = requests.get(
                "https://api.stability.ai/v1/user/account",
                headers={"Authorization": f"Bearer {os.environ.get('STABILITY_API_KEY')}"}
            )
            self.stdout.write(self.style.SUCCESS("Stability AI: OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Stability AI: {e}"))
```

### 2. Запуск теста

```bash
python manage.py test_ai
```

### 3. Тестирование через Django shell

```bash
python manage.py shell
```

```python
from core.ai_generator import AIContentGenerator

generator = AIContentGenerator()
print(generator.test_connection())  # Должно вернуть True

# Тест генерации текста
result = generator.generate_post_text(
    trend_title="Новый тренд",
    trend_description="Интересное описание",
    topic_name="Тестовая тема",
    template_config={
        'tone': 'friendly',
        'length': 'medium',
        'language': 'ru'
    }
)
print(result)
```

---

**Далее:**
- [Content Generation](./content-generation.md) - Как работает генерация контента
- [Backend Setup](../06-backend/setup.md) - Настройка backend
- [Troubleshooting](../08-guides/troubleshooting.md) - Решение проблем
