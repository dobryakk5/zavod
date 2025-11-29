"""
AI-powered content generator for social media posts
Uses OpenRouter API to generate engaging content from trends
Based on the architecture from ai_entity_matcher.py
"""

import os
import requests
import json
import logging
import base64
import shutil
from typing import Dict, Any, Optional
from io import BytesIO

try:
    from huggingface_hub import InferenceClient
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

try:
    from gradio_client import Client as GradioClient
    GRADIO_AVAILABLE = True
except ImportError:
    GradioClient = None
    GRADIO_AVAILABLE = False

logger = logging.getLogger(__name__)


class AIContentGenerator:
    """AI-генератор контента для социальных сетей"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize AI content generator

        Args:
            api_key: OpenRouter API key (if None, will try to get from environment)
        """
        self.api_key = api_key or os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")

        self.model = "x-ai/grok-4.1-fast:free"  # Бесплатная модель
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"

        # Initialize HuggingFace client if available
        self.hf_client = None
        if HF_HUB_AVAILABLE:
            hf_token = os.getenv('HUGGINGFACE_TOKEN') or os.getenv('HF_TOKEN')
            if hf_token:
                try:
                    self.hf_client = InferenceClient(
                        provider="nebius",
                        api_key=hf_token
                    )
                    logger.info("HuggingFace Nebius client initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize HuggingFace client: {e}")
            else:
                logger.debug("HuggingFace token not found, HF image generation will be unavailable")

    def get_ai_response(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.7) -> Optional[str]:
        """
        Send request to OpenRouter API

        Args:
            prompt: Text prompt for AI
            max_tokens: Maximum tokens in response
            temperature: Creativity level (0.0-1.0)

        Returns:
            AI response text or None if error
        """
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://zavod-content-factory.com",
                    "X-Title": "Content Factory AI Generator"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature
                },
                timeout=60  # 60 секунд таймаут
            )

            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                logger.error(f"OpenRouter API Error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            logger.error("OpenRouter API request timed out")
            return None
        except Exception as e:
            logger.error(f"Error calling OpenRouter API: {e}", exc_info=True)
            return None

    def generate_post_text(
        self,
        trend_title: str,
        trend_description: str,
        topic_name: str,
        template_config: Dict[str, Any],
        seo_keywords: Dict[str, list] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate post text from trend using AI

        Args:
            trend_title: Trend title
            trend_description: Trend description
            topic_name: Topic name (e.g., "студия танцев")
            template_config: Template configuration dict with:
                - tone: professional/friendly/informative/casual/enthusiastic
                - length: short/medium/long
                - language: ru/en
                - type: selling/expert/trigger (тип поста по структуре)
                - avatar: client audience avatar text
                - pains: client pains text
                - desires: client desires text
                - objections: client objections text
                - prompt_template: custom prompt template
                - additional_instructions: extra instructions
                - include_hashtags: bool
                - max_hashtags: int
            seo_keywords: Optional dict with keyword groups:
                - commercial: ["купить ...", ...]
                - general: ["топик москва", ...]
                - informational: ["как ...", ...]
                - long_tail: ["длинные фразы", ...]

        Returns:
            Dict with generated content:
            {
                "title": "Заголовок поста",
                "text": "Текст поста",
                "hashtags": ["хэштег1", "хэштег2", ...],
                "success": True/False,
                "error": "error message if failed"
            }
        """
        try:
            # Извлечь параметры из конфигурации
            tone = template_config.get('tone', 'professional')
            length = template_config.get('length', 'medium')
            language = template_config.get('language', 'ru')
            prompt_template = template_config.get("prompt_template", "")
            additional_instructions = template_config.get("additional_instructions", "")
            include_hashtags = template_config.get("include_hashtags", True)
            max_hashtags = template_config.get("max_hashtags", 5)
            post_type = template_config.get("type", "")
            avatar = template_config.get("avatar", "")
            pains = template_config.get("pains", "")
            desires = template_config.get("desires", "")
            objections = template_config.get("objections", "")

            # Извлечь случайные SEO-ключи из каждой группы
            import random
            selected_seo_keywords = []
            if seo_keywords and isinstance(seo_keywords, dict):
                for group_name, keywords_list in seo_keywords.items():
                    if keywords_list and isinstance(keywords_list, list) and len(keywords_list) > 0:
                        # Выбрать случайный ключ из группы
                        random_keyword = random.choice(keywords_list)
                        selected_seo_keywords.append(f"{random_keyword} ({group_name})")

                logger.info(f"Выбраны SEO-ключи для поста: {selected_seo_keywords}")

            # Маппинг тонов на русский для промпта
            tone_map = {
                "professional": "профессиональный",
                "friendly": "дружественный",
                "informative": "информационный",
                "casual": "непринуждённый",
                "enthusiastic": "восторженный"
            }

            # Маппинг длины на русский
            length_map = {
                "short": "короткий (до 280 символов)",
                "medium": "средний (280-500 символов)",
                "long": "длинный (500-1000 символов)"
            }

            tone_ru = tone_map.get(tone, tone)
            length_ru = length_map.get(length, length)
            lang_name = "русском" if language == "ru" else "английском"

            # Если есть кастомный промпт-шаблон, используем его
            if prompt_template:
                prompt = prompt_template.format(
                    trend_title=trend_title,
                    trend_description=trend_description,
                    topic_name=topic_name,
                    tone=tone_ru,
                    length=length_ru,
                    language=lang_name,
                    type=post_type,
                    avatar=avatar,
                    pains=pains,
                    desires=desires,
                    objections=objections,
                )
            else:
                # Дефолтный промпт
                prompt = f"""
Ты - опытный SMM-менеджер, который создаёт контент для социальных сетей.

ДАННЫЕ О ЦЕЛЕВОЙ АУДИТОРИИ:
Аватар: {avatar}
Боли: {pains}
Хотелки: {desires}
Возражения: {objections}

ЗАДАЧА: Создай {length_ru} пост для социальных сетей в {tone_ru} стиле на {lang_name} языке.

ТЕМА БИЗНЕСА: {topic_name}

НОВОСТЬ/ТРЕНД:
Заголовок: {trend_title}
Описание: {trend_description}

ИНСТРУКЦИИ:
1. Создай привлекательный заголовок поста (до 100 символов)
2. Напиши основной текст, который:
   - Объясняет суть новости/тренда
   - Показывает, почему это важно для аудитории именно с учётом его болей, хотелок и возражений
   - Связан с темой бизнеса "{topic_name}"
   - Имеет {tone_ru} тон
   - Соответствует требуемой длине: {length_ru}
"""

            if include_hashtags:
                prompt += f"""3. Добавь {max_hashtags} релевантных хэштега
"""

            # Добавить SEO-ключи если есть
            if selected_seo_keywords:
                seo_keywords_str = "\n   - ".join(selected_seo_keywords)
                prompt += f"""
ВАЖНО - SEO ОПТИМИЗАЦИЯ:
Естественным образом включи в текст поста следующие SEO-ключевые фразы (по одной из каждой группы):
   - {seo_keywords_str}

Фразы должны выглядеть органично и не выделяться из контекста.
"""

            if additional_instructions:
                prompt += f"""
ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ:
{additional_instructions}
"""

            prompt += """
ФОРМАТ ОТВЕТА (строго JSON):
{
    "title": "Заголовок поста",
    "text": "Основной текст поста",
    "hashtags": ["хэштег1", "хэштег2", "хэштег3"]
}

Ответь ТОЛЬКО JSON, без дополнительных комментариев."""

            logger.info(f"Генерация поста для тренда: {trend_title[:50]}")

            # Запрос к AI
            ai_response = self.get_ai_response(prompt, max_tokens=2000, temperature=0.7)

            if not ai_response:
                return {
                    "success": False,
                    "error": "Failed to get response from AI"
                }

            # Парсинг JSON ответа
            try:
                # Очистить ответ от markdown code blocks
                clean_response = ai_response.strip()
                if clean_response.startswith('```json'):
                    clean_response = clean_response[7:]
                if clean_response.startswith('```'):
                    clean_response = clean_response[3:]
                if clean_response.endswith('```'):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()

                result = json.loads(clean_response)

                # Валидация структуры ответа
                if "title" not in result or "text" not in result:
                    logger.error(f"Invalid AI response structure: {clean_response}")
                    return {
                        "success": False,
                        "error": "Invalid response structure from AI"
                    }

                # Добавить пустой список хэштегов если их нет
                if "hashtags" not in result:
                    result["hashtags"] = []

                # Добавить флаг успеха
                result["success"] = True

                logger.info(f"Успешно сгенерирован пост: {result['title'][:50]}")
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {clean_response}")
                return {
                    "success": False,
                    "error": f"JSON parsing error: {str(e)}",
                    "raw_response": clean_response
                }

        except Exception as e:
            logger.error(f"Error generating post text: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def generate_seo_keywords(
        self,
        topic_name: str,
        keywords: list,
        language: str = "ru"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate SEO keyword phrases for a topic using AI, grouped by category

        Args:
            topic_name: Topic name (e.g., "студия танцев")
            keywords: Existing keywords list for the topic
            language: Language code (ru/en)

        Returns:
            Dict with generated keywords:
            {
                "keyword_groups": {
                    "commercial": ["купить ...", "заказать ...", ...],
                    "general": ["топик москва", ...],
                    "informational": ["как ...", "что такое ...", ...]
                },
                "success": True/False,
                "error": "error message if failed"
            }
        """
        try:
            lang_name = "русском" if language == "ru" else "английском"
            keywords_str = ", ".join(keywords) if keywords else "не указаны"

            prompt = f"""
Ты - эксперт по SEO и поисковой оптимизации.

ЗАДАЧА: Составь подробный список часто используемых SEO-фраз и ключевых слов для темы бизнеса на {lang_name} языке.

ТЕМА БИЗНЕСА: {topic_name}

ТЕКУЩИЕ КЛЮЧЕВЫЕ СЛОВА: {keywords_str}

ИНСТРУКЦИИ:
1. Проанализируй тему бизнеса и найди 30-50 релевантных SEO-фраз
2. Раздели фразы на следующие группы:
   - **commercial** (коммерческие): "купить", "заказать", "цена", "стоимость", "услуги"
   - **general** (общие): основные запросы с геолокацией, брендовые запросы
   - **informational** (информационные): "как", "что такое", "зачем", "почему", обучающие
   - **long_tail** (длинные хвосты): специфичные длинные фразы 4-6 слов
3. В каждой группе должно быть 8-15 релевантных фраз
4. Фразы должны быть реалистичными поисковыми запросами

ФОРМАТ ОТВЕТА (строго JSON):
{{
    "commercial": [
        "купить танцы онлайн",
        "заказать занятия танцами",
        "стоимость уроков танцев"
    ],
    "general": [
        "студия танцев москва",
        "школа танцев для начинающих",
        "танцевальная студия рядом"
    ],
    "informational": [
        "как научиться танцевать",
        "виды современных танцев",
        "что нужно для танцев"
    ],
    "long_tail": [
        "лучшая студия танцев для взрослых в москве",
        "где научиться танцевать с нуля недорого"
    ]
}}

Ответь ТОЛЬКО JSON, без дополнительных комментариев."""

            logger.info(f"Генерация SEO-фраз для темы: {topic_name}")

            # Запрос к AI
            ai_response = self.get_ai_response(prompt, max_tokens=2000, temperature=0.5)

            if not ai_response:
                return {
                    "success": False,
                    "error": "Failed to get response from AI"
                }

            # Парсинг JSON ответа
            try:
                # Очистить ответ от markdown code blocks
                clean_response = ai_response.strip()
                if clean_response.startswith('```json'):
                    clean_response = clean_response[7:]
                if clean_response.startswith('```'):
                    clean_response = clean_response[3:]
                if clean_response.endswith('```'):
                    clean_response = clean_response[:-3]
                clean_response = clean_response.strip()

                keyword_groups = json.loads(clean_response)

                # Валидация структуры ответа
                if not isinstance(keyword_groups, dict):
                    logger.error(f"Invalid AI response structure: expected dict, got {type(keyword_groups)}")
                    return {
                        "success": False,
                        "error": "Invalid response structure from AI"
                    }

                # Проверка, что есть хотя бы одна группа
                if not keyword_groups:
                    logger.error(f"Empty keyword groups in AI response")
                    return {
                        "success": False,
                        "error": "No keyword groups generated"
                    }

                logger.info(f"Успешно сгенерированы SEO-фразы для темы: {topic_name}")
                logger.info(f"Группы: {list(keyword_groups.keys())}")

                return {
                    "keyword_groups": keyword_groups,
                    "success": True
                }

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {clean_response[:200]}")
                return {
                    "success": False,
                    "error": f"JSON parsing error: {str(e)}",
                    "raw_response": clean_response
                }

        except Exception as e:
            logger.error(f"Error generating SEO keywords: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def generate_image_prompt(self, post_title: str, post_text: str) -> Optional[str]:
        """
        Generate an optimized image prompt from post content using AI

        Args:
            post_title: Post title
            post_text: Post text content

        Returns:
            Optimized image generation prompt or None if error
        """
        try:
            prompt = f"""
Ты - эксперт по созданию промптов для генерации изображений.

ЗАДАЧА: Создай детальный промпт на английском языке для генерации изображения к посту в социальных сетях.

ПОСТ:
Заголовок: {post_title}
Текст: {post_text[:500]}

ИНСТРУКЦИИ:
1. Промпт должен быть на английском языке
2. Опиши визуальную сцену, которая отражает суть поста
3. Включи стиль изображения (например, "professional photography", "modern digital art", "minimalist design")
4. Укажи освещение, цветовую гамму, композицию
5. Промпт должен быть 1-2 предложения, очень конкретный и визуальный
6. Избегай текста на изображении
7. Фокусируйся на визуальной метафоре или прямом представлении темы

ФОРМАТ ОТВЕТА: Только промпт на английском языке, без дополнительных комментариев.

Пример хорошего промпта:
"A professional, modern office space with a diverse team collaborating around a sleek conference table, warm natural lighting through large windows, minimalist contemporary design, corporate photography style, high quality, focused composition"
"""

            logger.info(f"Генерация промпта для изображения поста: {post_title[:50]}")

            # Запрос к AI
            ai_response = self.get_ai_response(prompt, max_tokens=200, temperature=0.7)

            if not ai_response:
                logger.error("Не удалось получить промпт для изображения")
                return None

            image_prompt = ai_response.strip()
            logger.info(f"Сгенерирован промпт для изображения: {image_prompt[:100]}")

            return image_prompt

        except Exception as e:
            logger.error(f"Error generating image prompt: {e}", exc_info=True)
            return None

    def generate_image(self, prompt: str, output_path: str, model: str = "pollinations") -> Optional[Dict[str, Any]]:
        """
        Generate image using AI based on text prompt

        Args:
            prompt: Text prompt for image generation (in English)
            output_path: Full path where to save the generated image
            model: Image generation model to use:
                - "pollinations": Pollinations AI (free, default)
                - "nanobanana": OpenRouter google/gemini-2.5-flash-image
                - "huggingface": HuggingFace with Nebius GPU provider (requires HF_TOKEN)
                - "flux2": FLUX.2 HuggingFace Space via gradio_client (requires gradio_client)

        Returns:
            Dict with result:
            {
                "success": True/False,
                "image_path": "path to saved image",
                "image_url": "URL of generated image",
                "error": "error message if failed"
            }
        """
        logger.info(f"Генерация изображения моделью '{model}' по промпту: {prompt[:100]}")

        if model == "nanobanana":
            return self._generate_image_openrouter(prompt, output_path)
        elif model == "huggingface":
            return self._generate_image_huggingface(prompt, output_path)
        elif model == "flux2":
            return self._generate_image_flux2(prompt, output_path)
        else:
            return self._generate_image_pollinations(prompt, output_path)

    def _generate_image_pollinations(self, prompt: str, output_path: str) -> Optional[Dict[str, Any]]:
        """
        Generate image using Pollinations AI (free service)

        Args:
            prompt: Text prompt for image generation
            output_path: Full path where to save the generated image

        Returns:
            Dict with result
        """
        try:
            # Используем Pollinations AI - бесплатный сервис генерации изображений
            # URL формируется как: https://image.pollinations.ai/prompt/{encoded_prompt}
            import urllib.parse
            encoded_prompt = urllib.parse.quote(prompt)
            image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"

            logger.info(f"Запрос изображения Pollinations с URL: {image_url}")

            # Скачиваем изображение
            response = requests.get(image_url, timeout=60)

            if response.status_code == 200:
                # Создаём директорию если не существует
                import os
                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                # Сохраняем изображение
                with open(output_path, 'wb') as f:
                    f.write(response.content)

                logger.info(f"Изображение успешно сохранено: {output_path}")

                return {
                    "success": True,
                    "image_path": output_path,
                    "image_url": image_url,
                    "model": "pollinations"
                }
            else:
                logger.error(f"Ошибка загрузки изображения: HTTP {response.status_code}")
                return {
                    "success": False,
                    "error": f"HTTP error {response.status_code}"
                }

        except requests.exceptions.Timeout:
            logger.error("Таймаут при генерации изображения")
            return {
                "success": False,
                "error": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Error generating image: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_image_openrouter(self, prompt: str, output_path: str) -> Optional[Dict[str, Any]]:
        """
        Generate image using OpenRouter google/gemini-2.5-flash-image model

        Args:
            prompt: Text prompt for image generation
            output_path: Full path where to save the generated image

        Returns:
            Dict with result
        """
        try:
            logger.info("Генерация изображения через OpenRouter (google/gemini-2.5-flash-image)")

            # OpenRouter API для генерации изображений
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://zavod-content-factory.com",
                    "X-Title": "Content Factory Image Generator"
                },
                json={
                    "model": "google/gemini-2.5-flash-image",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Generate an image: {prompt}"
                        }
                    ]
                },
                timeout=120  # Генерация изображения может занять больше времени
            )

            if response.status_code == 200:
                data = response.json()
                logger.debug(f"OpenRouter response: {data}")

                # Извлечь изображение из ответа
                # Может быть URL или base64-encoded изображение
                image_url = None
                image_base64 = None

                if 'choices' in data and len(data['choices']) > 0:
                    message = data['choices'][0].get('message', {})
                    content = message.get('content', '')

                    # Проверяем, есть ли base64 изображение в content (часто в виде data URI)
                    if isinstance(content, list):
                        # content может быть массивом объектов
                        for item in content:
                            if isinstance(item, dict):
                                # Проверяем image_url с base64
                                if 'image_url' in item:
                                    img_url_data = item['image_url']
                                    if isinstance(img_url_data, dict) and 'url' in img_url_data:
                                        url_value = img_url_data['url']
                                        if url_value.startswith('data:image'):
                                            image_base64 = url_value
                                        else:
                                            image_url = url_value
                    elif isinstance(content, str):
                        # Попробуем найти data URI или обычный URL
                        if content.startswith('data:image'):
                            image_base64 = content
                        else:
                            # Попробуем найти URL изображения в тексте
                            import re
                            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                            urls = re.findall(url_pattern, content)
                            if urls:
                                image_url = urls[0]

                    # Проверяем альтернативные поля
                    if not image_url and not image_base64:
                        if 'image_url' in message:
                            image_url = message['image_url']

                # Обрабатываем изображение в зависимости от формата
                if image_base64:
                    logger.info("Обнаружено base64-encoded изображение")
                    # Извлекаем base64 данные из data URI
                    # Формат: data:image/png;base64,iVBORw0KGgo...
                    if ',' in image_base64:
                        base64_data = image_base64.split(',', 1)[1]
                    else:
                        base64_data = image_base64

                    # Декодируем base64
                    try:
                        image_bytes = base64.b64decode(base64_data)

                        # Создаём директорию если не существует
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)

                        # Сохраняем изображение
                        with open(output_path, 'wb') as f:
                            f.write(image_bytes)

                        logger.info(f"Изображение NanoBanana успешно сохранено: {output_path}")

                        return {
                            "success": True,
                            "image_path": output_path,
                            "image_url": None,  # Нет прямого URL для base64
                            "model": "nanobanana"
                        }
                    except Exception as e:
                        logger.error(f"Ошибка декодирования base64 изображения: {e}")
                        return {
                            "success": False,
                            "error": f"Base64 decode error: {str(e)}"
                        }

                elif image_url:
                    logger.info(f"Получен URL изображения: {image_url}")

                    # Скачиваем изображение по URL
                    img_response = requests.get(image_url, timeout=60)

                    if img_response.status_code == 200:
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)

                        with open(output_path, 'wb') as f:
                            f.write(img_response.content)

                        logger.info(f"Изображение NanoBanana успешно сохранено: {output_path}")

                        return {
                            "success": True,
                            "image_path": output_path,
                            "image_url": image_url,
                            "model": "nanobanana"
                        }
                    else:
                        logger.error(f"Ошибка загрузки изображения: HTTP {img_response.status_code}")
                        return {
                            "success": False,
                            "error": f"Image download HTTP error {img_response.status_code}"
                        }
                else:
                    logger.error(f"Не удалось извлечь изображение из ответа: {data}")
                    return {
                        "success": False,
                        "error": "No image URL or base64 data in response"
                    }
            else:
                logger.error(f"OpenRouter API Error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"API error {response.status_code}: {response.text}"
                }

        except requests.exceptions.Timeout:
            logger.error("Таймаут при генерации изображения через OpenRouter")
            return {
                "success": False,
                "error": "Request timeout"
            }
        except Exception as e:
            logger.error(f"Error generating image via OpenRouter: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_image_flux2(self, prompt: str, output_path: str) -> Optional[Dict[str, Any]]:
        """
        Generate image using FLUX.2 HuggingFace Space via gradio_client.
        """
        if not GRADIO_AVAILABLE:
            logger.error("gradio_client не установлен – FLUX.2 генерация недоступна")
            return {
                "success": False,
                "error": "gradio_client not installed. Run pip install gradio_client."
            }

        try:
            def _env_bool(name: str, default: bool) -> bool:
                value = os.getenv(name)
                if value is None:
                    return default
                return value.strip().lower() in ("1", "true", "yes", "on")

            space_name = os.getenv('FLUX2_SPACE', 'black-forest-labs/FLUX.2-dev')
            api_name = os.getenv('FLUX2_API_NAME', '/infer')
            width = int(os.getenv('FLUX2_WIDTH', '1024'))
            height = int(os.getenv('FLUX2_HEIGHT', '1024'))
            seed = float(os.getenv('FLUX2_SEED', '0'))
            randomize_seed = _env_bool('FLUX2_RANDOMIZE_SEED', True)
            steps = float(os.getenv('FLUX2_STEPS', '30'))
            guidance_scale = float(os.getenv('FLUX2_GUIDANCE', '4'))
            prompt_upsampling = _env_bool('FLUX2_PROMPT_UPSAMPLING', True)

            logger.info("Генерация изображения через FLUX.2 Space %s", space_name)

            client = GradioClient(space_name)
            result = client.predict(
                prompt=prompt,
                input_images=[],
                seed=seed,
                randomize_seed=randomize_seed,
                width=width,
                height=height,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                prompt_upsampling=prompt_upsampling,
                api_name=api_name
            )

            logger.debug("FLUX.2 ответ: %s", result)

            image_entry: Optional[Dict[str, Any]] = None
            if isinstance(result, (list, tuple)) and len(result) > 0:
                potential = result[0]
                if isinstance(potential, dict):
                    image_entry = potential
            elif isinstance(result, dict):
                image_entry = result

            path_candidate = None
            url_candidate = None

            if image_entry:
                path_candidate = image_entry.get('path')
                url_candidate = image_entry.get('url')

                meta = image_entry.get('meta')
                if isinstance(meta, dict):
                    url_candidate = url_candidate or meta.get('url')

                nested_image = image_entry.get('image')
                if isinstance(nested_image, dict):
                    path_candidate = path_candidate or nested_image.get('path')
                    url_candidate = url_candidate or nested_image.get('url')

            if isinstance(result, str) and not path_candidate:
                path_candidate = result

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            saved = False

            if path_candidate and os.path.exists(path_candidate):
                shutil.copyfile(path_candidate, output_path)
                saved = True
            else:
                download_url = None
                if path_candidate and str(path_candidate).startswith('http'):
                    download_url = path_candidate
                elif url_candidate:
                    download_url = url_candidate

                if download_url:
                    response = requests.get(download_url, timeout=120)
                    response.raise_for_status()
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    saved = True

            if not saved:
                logger.error("FLUX.2 Space не вернуло корректного пути или URL для изображения")
                return {
                    "success": False,
                    "error": "Unable to retrieve generated image from FLUX.2 space"
                }

            logger.info("Изображение FLUX.2 успешно сохранено: %s", output_path)
            return {
                "success": True,
                "image_path": output_path,
                "image_url": url_candidate,
                "model": "flux2"
            }

        except Exception as e:
            logger.error(f"Ошибка генерации через FLUX.2 Space: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _generate_image_huggingface(self, prompt: str, output_path: str, model: str = "black-forest-labs/FLUX.1-dev") -> Optional[Dict[str, Any]]:
        """
        Generate image using HuggingFace InferenceClient with Nebius provider

        Args:
            prompt: Text prompt for image generation
            output_path: Full path where to save the generated image
            model: HuggingFace model to use (default: black-forest-labs/FLUX.1-dev)

        Returns:
            Dict with result
        """
        try:
            if not self.hf_client:
                logger.error("HuggingFace client not initialized (check HF_TOKEN in environment)")
                return {
                    "success": False,
                    "error": "HuggingFace client not available. Install huggingface_hub and set HF_TOKEN environment variable."
                }

            logger.info(f"Генерация изображения через HuggingFace Nebius (модель: {model})")

            # Генерация изображения через InferenceClient
            image = self.hf_client.text_to_image(
                prompt=prompt,
                model=model
            )

            # Конвертируем PIL Image в байты
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()

            # Создаём директорию если не существует
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Сохраняем изображение
            with open(output_path, 'wb') as f:
                f.write(img_byte_arr)

            logger.info(f"Изображение HuggingFace успешно сохранено: {output_path}")

            return {
                "success": True,
                "image_path": output_path,
                "image_url": None,  # InferenceClient не возвращает URL
                "model": "huggingface"
            }

        except Exception as e:
            logger.error(f"Error generating image via HuggingFace: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def test_connection(self) -> bool:
        """
        Test connection to OpenRouter API

        Returns:
            True if connection successful, False otherwise
        """
        try:
            test_prompt = "Ответь одним словом: 'готов'"
            response = self.get_ai_response(test_prompt, max_tokens=10)
            return response is not None
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
