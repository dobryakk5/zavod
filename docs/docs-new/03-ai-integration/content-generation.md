# Генерация контента

В этом документе описана система генерации контента с использованием AI.

## Содержание

- [Обзор](#обзор)
- [Генерация текста](#генерация-текста)
- [Генерация изображений](#генерация-изображений)
- [Генерация видео](#генерация-видео)
- [Шаблоны и промпты](#шаблоны-и-промпты)
- [Celery задачи](#celery-задачи)
- [Тестирование](#тестирование)

## Обзор

Система автоматической генерации контента включает три этапа:

1. **Генерация текста** - создание постов на основе трендов и шаблонов
2. **Генерация изображений** - создание визуального контента для постов
3. **Генерация видео** - создание коротких видео (Reels/Shorts)

### Workflow

```
Тренд → AI Генерация текста → AI Генерация изображения → AI Генерация видео → Пост
```

## Генерация текста

### Источники контента

Система собирает контент из различных источников:

- **RSS ленты** - новостные сайты, блоги
- **Google Trends** - популярные поисковые запросы
- **Telegram каналы** - тематические каналы
- **YouTube** - популярные видео
- **Instagram** - популярные посты
- **VKontakte** - популярные записи

### AI Генерация

#### OpenAI GPT

```python
from openai import OpenAI

class AIContentGenerator:
    def __init__(self):
        self.client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        self.model = "gpt-4o-mini"
    
    def generate_post_text(self, trend_title, trend_description, topic_name, template_config):
        """Генерация текста поста"""
        
        prompt = self._build_prompt(trend_title, trend_description, topic_name, template_config)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": template_config.get('seo_prompt_template', '')},
                {"role": "user", "content": prompt}
            ],
            temperature=template_config.get('temperature', 0.8),
            max_tokens=template_config.get('max_tokens', 1500)
        )
        
        return response.choices[0].message.content
    
    def _build_prompt(self, trend_title, trend_description, topic_name, template_config):
        """Построение промпта для генерации"""
        
        prompt_template = template_config.get('trend_prompt_template', self._default_prompt_template())
        
        return prompt_template.format(
            topic_name=topic_name,
            trend_title=trend_title,
            trend_description=trend_description,
            tone=template_config.get('tone', 'friendly'),
            length=template_config.get('length', 'medium'),
            language=template_config.get('language', 'ru')
        )
    
    def _default_prompt_template(self):
        """Стандартный промпт для генерации постов"""
        return """
Ты - опытный SMM-менеджер для "{topic_name}".

Создай {length} пост в {tone} стиле на {language} языке.

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

### Пример генерации

```python
# Пример использования
generator = AIContentGenerator()

result = generator.generate_post_text(
    trend_title="Новый стиль танца стал вирусным в TikTok",
    trend_description="Миллионы пользователей повторяют новый танец",
    topic_name="студия танцев",
    template_config={
        'tone': 'friendly',
        'length': 'medium',
        'language': 'ru',
        'seo_prompt_template': '',
        'trend_prompt_template': '',
        'prompt_type': 'trend',
        'additional_instructions': '',
        'include_hashtags': True,
        'max_hashtags': 5
    }
)

print(result)
```

## Генерация изображений

### Stability AI

```python
import requests
import base64

class ImageGenerator:
    def __init__(self):
        self.api_key = os.environ.get('STABILITY_API_KEY')
        self.engine = os.environ.get('STABILITY_ENGINE', 'stable-diffusion-xl-beta-v2-2-2v')
    
    def generate_image(self, prompt, width=1024, height=1024):
        """Генерация изображения"""
        
        url = f"https://api.stability.ai/v1/generation/{self.engine}/text-to-image"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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
        
        # Извлечение изображения
        for artifact in result['artifacts']:
            if artifact['finish_reason'] == 'SUCCESS':
                return base64.b64decode(artifact['base64'])
        
        return None
    
    def generate_image_from_text(self, post_text, topic_name, style='modern'):
        """Генерация изображения на основе текста поста"""
        
        prompt = f"""
{topic_name} - {post_text[:100]}...

Создай современное, яркое изображение в стиле {style} для поста в Instagram.
Используй сочные цвета, четкие линии, современные элементы.
Изображение должно быть квадратным (1:1), подходит для социальных сетей.
"""
        
        return self.generate_image(prompt)
```

### Модели генерации

Система поддерживает несколько моделей:

1. **Pollinations AI** - быстрая генерация, бесплатная
2. **Google Gemini (NanoBanana)** - качественные изображения
3. **HuggingFace FLUX.1** - передовые модели
4. **Stable Diffusion (Flux.2)** - высокое качество

```python
def generate_image_for_post(post_id, model='pollinations'):
    """Генерация изображения для поста"""
    
    post = Post.objects.get(id=post_id)
    
    if model == 'pollinations':
        return generate_with_pollinations(post.text, post.topic.name)
    elif model == 'nanobanana':
        return generate_with_gemini(post.text, post.topic.name)
    elif model == 'huggingface':
        return generate_with_hf(post.text, post.topic.name)
    elif model == 'flux2':
        return generate_with_flux2(post.text, post.topic.name)
    else:
        raise ValueError(f"Unknown model: {model}")
```

## Генерация видео

### Runway ML

```python
import requests
import time

class VideoGenerator:
    def __init__(self):
        self.api_key = os.environ.get('RUNWAY_API_KEY')
        self.api_url = "https://api.runwayml.com/v1"
    
    def generate_video_from_text(self, prompt, duration=10):
        """Генерация видео из текстового описания"""
        
        # Создание задачи
        url = f"{self.api_url}/generate/video"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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
        
        # Ожидание завершения
        return self._wait_for_task_completion(task_id)
    
    def generate_video_from_image(self, image_url, motion_prompt, duration=5):
        """Генерация видео из статичного изображения"""
        
        url = f"{self.api_url}/generate/video-from-image"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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
        return self._wait_for_task_completion(task['task_id'])
    
    def _wait_for_task_completion(self, task_id):
        """Ожидание завершения задачи"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        while True:
            response = requests.get(
                f"{self.api_url}/tasks/{task_id}",
                headers=headers
            )
            response.raise_for_status()
            
            status = response.json()
            
            if status['status'] == 'completed':
                return status['result']['video_url']
            elif status['status'] == 'failed':
                raise Exception(f"Video generation failed: {status.get('error')}")
            
            time.sleep(5)
```

### Методы генерации

```python
def generate_video_for_post(post_id, method='wan', source='image'):
    """Генерация видео для поста"""
    
    post = Post.objects.get(id=post_id)
    
    if source == 'image':
        # Генерация из изображения
        if method == 'wan':
            return generate_wan_video(post.image.url, post.text)
        elif method == 'runway':
            return generate_runway_video(post.image.url, post.text)
    elif source == 'text':
        # Генерация из текста
        return generate_text_to_video(post.text, post.topic.name)
    
    raise ValueError(f"Unknown method: {method} or source: {source}")
```

## Шаблоны и промпты

### ContentTemplate Model

```python
class ContentTemplate(models.Model):
    TYPE_CHOICES = [
        ('selling', 'Продающий'),
        ('informative', 'Информационный'),
        ('educational', 'Образовательный'),
        ('entertainment', 'Развлекательный'),
    ]
    
    TONE_CHOICES = [
        ('professional', 'Профессиональный'),
        ('friendly', 'Дружественный'),
        ('enthusiastic', 'Воодушевленный'),
        ('serious', 'Серьезный'),
    ]
    
    LENGTH_CHOICES = [
        ('short', 'Короткий'),
        ('medium', 'Средний'),
        ('long', 'Длинный'),
    ]
    
    LANGUAGE_CHOICES = [
        ('ru', 'Русский'),
        ('en', 'Английский'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    tone = models.CharField(max_length=20, choices=TONE_CHOICES)
    length = models.CharField(max_length=10, choices=LENGTH_CHOICES)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='ru')
    
    # Промпты
    seo_prompt_template = models.TextField()
    trend_prompt_template = models.TextField()
    additional_instructions = models.TextField(blank=True)
    
    # Настройки
    include_hashtags = models.BooleanField(default=True)
    max_hashtags = models.IntegerField(default=5)
    is_default = models.BooleanField(default=False)
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Content Template"
        verbose_name_plural = "Content Templates"
        unique_together = [('client', 'name')]
```

### Пример шаблона

```json
{
  "name": "Instagram пост - дружественный",
  "type": "selling",
  "tone": "friendly",
  "length": "medium",
  "language": "ru",
  "seo_prompt_template": "Ты - опытный SMM-менеджер для \"{topic_name}\".",
  "trend_prompt_template": "Создай {length} пост в {tone} стиле на {language} языке.\n\nНОВОСТЬ/ТРЕНД:\nЗаголовок: {trend_title}\nОписание: {trend_description}\n\nЗАДАЧА:\n1. Напиши привлекательный заголовок (до 100 символов)\n2. Создай основной текст который:\n   - Объясняет суть новости простым языком\n   - Показывает практическую пользу для аудитории\n   - Связан с темой \"{topic_name}\"\n   - Написан в {tone} тоне\n   - Имеет длину: {length}\n3. Добавь эмодзи для оживления текста\n4. Закончи призывом к действию\n\nБудь креативным но информативным!",
  "additional_instructions": "Всегда упоминай бренд в конце поста. Используй emoji умеренно (2-3 в тексте). Избегай сложных терминов.",
  "include_hashtags": true,
  "max_hashtags": 5
}
```

## Celery задачи

### Генерация поста из тренда

```python
@shared_task
def generate_post_from_trend(trend_id, template_id=None):
    """Генерация поста из тренда"""
    
    try:
        trend = TrendItem.objects.get(id=trend_id)
        topic = trend.topic
        
        # Получение шаблона
        if template_id:
            template = ContentTemplate.objects.get(id=template_id)
        else:
            template = ContentTemplate.objects.filter(
                client=topic.client,
                is_default=True
            ).first()
        
        if not template:
            raise ValueError("No template found")
        
        # Генерация текста
        generator = AIContentGenerator()
        template_config = {
            'tone': template.tone,
            'length': template.length,
            'language': template.language,
            'seo_prompt_template': template.seo_prompt_template,
            'trend_prompt_template': template.trend_prompt_template,
            'additional_instructions': template.additional_instructions,
            'include_hashtags': template.include_hashtags,
            'max_hashtags': template.max_hashtags
        }
        
        text = generator.generate_post_text(
            trend.title,
            trend.description,
            topic.name,
            template_config
        )
        
        # Создание поста
        post = Post.objects.create(
            client=topic.client,
            title=trend.title,
            text=text,
            status='draft',
            generated_by='openai',
            source_links=[trend.url] if trend.url else []
        )
        
        # Отметка тренда как использованного
        trend.used_for_post = post
        trend.used_for_post_title = trend.title
        trend.save()
        
        # Генерация изображения (если настроено)
        if template.client.auto_generate_images:
            generate_image_for_post.delay(post.id)
        
        return {
            'success': True,
            'post_id': post.id,
            'trend_id': trend_id
        }
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating post from trend {trend_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'trend_id': trend_id
        }
```

### Генерация истории

```python
@shared_task
def generate_story_from_trend(trend_id, episode_count=5, template_id=None):
    """Генерация истории из тренда"""
    
    try:
        trend = TrendItem.objects.get(id=trend_id)
        topic = trend.topic
        
        # Создание истории
        story = Story.objects.create(
            title=f"История: {trend.title}",
            trend_item=trend,
            trend_title=trend.title,
            template_id=template_id,
            episode_count=episode_count,
            status='generating'
        )
        
        # Генерация эпизодов
        generator = AIContentGenerator()
        
        for order in range(1, episode_count + 1):
            episode_title = generator.generate_episode_title(
                trend.title,
                trend.description,
                topic.name,
                order,
                episode_count
            )
            
            StoryEpisode.objects.create(
                story=story,
                order=order,
                title=episode_title
            )
        
        story.status = 'completed'
        story.save()
        
        return {
            'success': True,
            'story_id': story.id,
            'episodes_count': episode_count
        }
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating story from trend {trend_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'trend_id': trend_id
        }
```

### Генерация постов из истории

```python
@shared_task
def generate_posts_from_story(story_id):
    """Генерация постов из эпизодов истории"""
    
    try:
        story = Story.objects.get(id=story_id)
        episodes = story.episodes.all().order_by('order')
        
        generated_posts = []
        
        for episode in episodes:
            # Генерация поста для эпизода
            post_data = {
                'client': story.trend_item.client,
                'title': f"{story.title} - Эпизод {episode.order}",
                'text': generator.generate_post_from_episode(
                    episode.title,
                    story.trend_item.description,
                    story.trend_item.topic.name
                ),
                'status': 'draft',
                'generated_by': 'openai'
            }
            
            post = Post.objects.create(**post_data)
            generated_posts.append(post.id)
        
        story.status = 'posts_created'
        story.save()
        
        return {
            'success': True,
            'story_id': story_id,
            'posts_count': len(generated_posts),
            'post_ids': generated_posts
        }
        
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating posts from story {story_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'story_id': story_id
        }
```

## Тестирование

### Тестирование генератора

```python
# management/commands/test_ai.py
from django.core.management.base import BaseCommand
from core.ai_generator import AIContentGenerator

class Command(BaseCommand):
    def handle(self, *args, **options):
        generator = AIContentGenerator()
        
        # Тест подключения
        if generator.test_connection():
            self.stdout.write(self.style.SUCCESS("OpenAI: OK"))
        else:
            self.stdout.write(self.style.ERROR("OpenAI: Connection failed"))
        
        # Тест генерации текста
        try:
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
            self.stdout.write(f"Generated text: {result[:100]}...")
            self.stdout.write(self.style.SUCCESS("Text generation: OK"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Text generation: {e}"))
```

### Unit тесты

```python
# core/tests/test_ai_generator.py
from django.test import TestCase
from core.ai_generator import AIContentGenerator

class AIContentGeneratorTest(TestCase):
    def setUp(self):
        self.generator = AIContentGenerator()
    
    def test_prompt_building(self):
        """Тест построения промпта"""
        prompt = self.generator._build_prompt(
            "Test Title",
            "Test Description",
            "Test Topic",
            {
                'tone': 'friendly',
                'length': 'medium',
                'language': 'ru'
            }
        )
        
        self.assertIn("Test Title", prompt)
        self.assertIn("Test Description", prompt)
        self.assertIn("Test Topic", prompt)
        self.assertIn("friendly", prompt)
    
    def test_template_validation(self):
        """Тест валидации шаблона"""
        from core.models import ContentTemplate, Client
        
        client = Client.objects.create(name="Test Client", slug="test-client")
        
        template = ContentTemplate.objects.create(
            client=client,
            name="Test Template",
            type="selling",
            tone="friendly",
            length="medium",
            language="ru",
            seo_prompt_template="Test prompt",
            trend_prompt_template="Test trend prompt"
        )
        
        self.assertEqual(template.name, "Test Template")
        self.assertTrue(template.seo_prompt_template)
```

---

**Далее:**
- [AI Setup](./setup.md) - Настройка AI сервисов
- [Backend Setup](../06-backend/setup.md) - Настройка backend
- [Troubleshooting](../08-guides/troubleshooting.md) - Решение проблем
