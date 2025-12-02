"""
AI-powered content generator for social media posts
Uses OpenRouter API to generate engaging content from trends
Based on the architecture from ai_entity_matcher.py
"""

import os
import requests
import json
import logging
from typing import Dict, Any, Optional

from . import foto_video_gen

try:
    from huggingface_hub import InferenceClient
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

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

    def generate_video_prompt(self, post_title: str, post_text: str, language: str = "ru") -> Optional[str]:
        """Сгенерировать промпт для короткого вовлекающего видео по тексту поста."""
        try:
            lang_name = "русском" if language == "ru" else "английском"
            prompt = f"""
Ты — режиссёр и сценарист коротких вертикальных видео TikTok/Reels. На входе у тебя текст поста.

1. Сделай вовлекающий, визуально насыщенный prompt на английском языке.
2. Описывай сцену, настроение, движения камеры, переходы, ключевые визуальные объекты.
3. Стиль — современный, динамичный, вдохновляющий. Максимум 3 предложения.
4. Не добавляй хештеги, кавычки и технические команды.

Пост ({lang_name}):
Заголовок: {post_title}
Текст: {post_text[:800]}

Выход: только английский prompt для генерации видео.
"""

            logger.info("Генерация промпта для видео по посту: %s", post_title[:50])
            ai_response = self.get_ai_response(prompt, max_tokens=300, temperature=0.7)
            if not ai_response:
                logger.error("Не удалось получить промпт для видео")
                return None

            video_prompt = ai_response.strip()
            logger.info("Сгенерирован промпт для видео: %s", video_prompt[:120])
            return video_prompt

        except Exception as e:
            logger.error(f"Error generating video prompt: {e}", exc_info=True)
            return None

    def generate_image(self, prompt: str, output_path: str, model: str = "pollinations") -> Optional[Dict[str, Any]]:
        """
        Генерация изображения с использованием вынесенного фото/видео модуля.
        """
        return foto_video_gen.generate_image(
            prompt=prompt,
            output_path=output_path,
            model=model,
            api_key=self.api_key,
            api_url=self.api_url,
            hf_client=self.hf_client
        )

    def generate_video_from_image(
        self,
        image_path: str,
        prompt: str,
        method: str = "wan",
        negative_prompt: Optional[str] = None,
        **options: Any
    ) -> Dict[str, Any]:
        """
        Создать видео из изображения, поддерживая WAN и VEO методы.
        """
        return foto_video_gen.generate_video_from_image(
            image_path=image_path,
            prompt=prompt,
            method=method,
            negative_prompt=negative_prompt,
            **options
        )

    def generate_video_from_text(
        self,
        prompt: str,
        method: str = "veo",
        **options: Any
    ) -> Dict[str, Any]:
        """
        Создать видео только по тексту (доступно для VEO).
        """
        return foto_video_gen.generate_video_from_text(
            prompt=prompt,
            method=method,
            **options
        )

    def generate_story_episodes(
        self,
        trend_title: str,
        trend_description: str,
        topic_name: str,
        episode_count: int,
        client_desires: str = "",
        language: str = "ru"
    ) -> Optional[Dict[str, Any]]:
        """
        Generate story episodes from trend using AI (using tng-r1t-chimera model)

        Args:
            trend_title: Trend title
            trend_description: Trend description
            topic_name: Topic name (e.g., "студия танцев")
            episode_count: Number of episodes to generate
            client_desires: Client's target audience desires
            language: Language code (ru/en)

        Returns:
            Dict with generated story:
            {
                "title": "Общий заголовок истории",
                "episodes": [
                    {"order": 1, "title": "Заголовок эпизода 1"},
                    {"order": 2, "title": "Заголовок эпизода 2"},
                    ...
                ],
                "success": True/False,
                "error": "error message if failed"
            }
        """
        try:
            lang_name = "русском" if language == "ru" else "английском"

            prompt = f"""
Ты - профессиональный сценарист и SMM-специалист, который создаёт вовлекающие истории для социальных сетей.

ЗАДАЧА: Создай увлекательную историю (мини-сериал) из {episode_count} эпизодов на {lang_name} языке.

ТЕМА БИЗНЕСА: {topic_name}

ОСНОВА ДЛЯ ИСТОРИИ:
Тренд: {trend_title}
Описание: {trend_description}

ЦЕЛЕВАЯ АУДИТОРИЯ:
Хотелки и желания: {client_desires}

ИНСТРУКЦИИ:
1. Придумай общий заголовок истории (1 предложение, до 100 символов)
2. Создай {episode_count} эпизодов, которые:
   - Вовлекают аудиторию через эмоциональную связь
   - Учитывают желания целевой аудитории ({client_desires})
   - Связаны с темой бизнеса "{topic_name}"
   - Основаны на тренде "{trend_title}"
   - Имеют развитие сюжета от эпизода к эпизоду
   - Держат интригу и мотивируют читать дальше
   - Каждый эпизод имеет заголовок (20-80 символов)

3. История должна быть:
   - Вовлекающей и эмоциональной
   - С человеческими персонажами (если уместно)
   - С развитием конфликта или интриги
   - Связана с желаниями аудитории

ПРИМЕРЫ ХОРОШИХ ИСТОРИЙ:
- "Маша на занятиях по танцам увидела Колю" → "Коля пригласил Машу потанцевать" → "На следующее занятие он не пришел" → "Он вернулся в новой рубашке" → "Они встретились глазами"
- "Анна решила изменить свою жизнь" → "Первое занятие было тяжелым" → "Через неделю она почувствовала изменения" → "Коллеги заметили перемены" → "Анна обрела уверенность"

ФОРМАТ ОТВЕТА (строго JSON):
{{
    "title": "Общий заголовок истории",
    "episodes": [
        {{"order": 1, "title": "Заголовок эпизода 1"}},
        {{"order": 2, "title": "Заголовок эпизода 2"}},
        ...
        {{"order": {episode_count}, "title": "Заголовок эпизода {episode_count}"}}
    ]
}}

Ответь ТОЛЬКО JSON, без дополнительных комментариев."""

            logger.info(f"Генерация истории на основе тренда: {trend_title[:50]}")

            # Используем специальную модель для историй
            original_model = self.model
            self.model = "tngtech/tng-r1t-chimera:free"

            try:
                # Запрос к AI
                ai_response = self.get_ai_response(prompt, max_tokens=2000, temperature=0.8)

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
                    if "title" not in result or "episodes" not in result:
                        logger.error(f"Invalid AI response structure: {clean_response}")
                        return {
                            "success": False,
                            "error": "Invalid response structure from AI"
                        }

                    # Проверка количества эпизодов
                    if not isinstance(result["episodes"], list) or len(result["episodes"]) != episode_count:
                        logger.warning(f"Expected {episode_count} episodes, got {len(result.get('episodes', []))}")

                    # Добавить флаг успеха
                    result["success"] = True

                    logger.info(f"Успешно сгенерирована история: {result['title'][:50]} ({len(result['episodes'])} эпизодов)")
                    return result

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse AI response as JSON: {clean_response}")
                    return {
                        "success": False,
                        "error": f"JSON parsing error: {str(e)}",
                        "raw_response": clean_response
                    }

            finally:
                # Восстановить оригинальную модель
                self.model = original_model

        except Exception as e:
            logger.error(f"Error generating story episodes: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def generate_post_from_episode(
        self,
        story_title: str,
        episode_title: str,
        episode_number: int,
        total_episodes: int,
        topic_name: str,
        template_config: Dict[str, Any],
        client_info: Dict[str, str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a full post from a story episode

        Args:
            story_title: Overall story title
            episode_title: Episode title/headline
            episode_number: Episode number (1-indexed)
            total_episodes: Total number of episodes in story
            topic_name: Topic name (e.g., "студия танцев")
            template_config: Template configuration (same as generate_post_text)
            client_info: Optional client info dict with avatar/pains/desires/objections

        Returns:
            Dict with generated content (same format as generate_post_text)
        """
        try:
            # Извлечь параметры из конфигурации
            tone = template_config.get('tone', 'professional')
            length = template_config.get('length', 'medium')
            language = template_config.get('language', 'ru')
            include_hashtags = template_config.get("include_hashtags", True)
            max_hashtags = template_config.get("max_hashtags", 5)
            additional_instructions = template_config.get("additional_instructions", "")

            # Информация о клиенте
            client_info = client_info or {}
            avatar = client_info.get("avatar", "")
            pains = client_info.get("pains", "")
            desires = client_info.get("desires", "")
            objections = client_info.get("objections", "")

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

            prompt = f"""
Ты - профессиональный копирайтер для социальных сетей.

ЗАДАЧА: Создай {length_ru} пост для социальных сетей в {tone_ru} стиле на {lang_name} языке.

КОНТЕКСТ ИСТОРИИ:
- Общий заголовок истории: {story_title}
- Эпизод {episode_number} из {total_episodes}: {episode_title}

ТЕМА БИЗНЕСА: {topic_name}

ДАННЫЕ О ЦЕЛЕВОЙ АУДИТОРИИ:
Аватар: {avatar}
Боли: {pains}
Хотелки: {desires}
Возражения: {objections}

ИНСТРУКЦИИ:
1. Создай привлекательный заголовок поста (до 100 символов)
2. Напиши основной текст, который:
   - Развивает сюжет эпизода "{episode_title}"
   - Связан с общей историей "{story_title}"
   - Учитывает желания и боли аудитории
   - Связан с темой бизнеса "{topic_name}"
   - Имеет {tone_ru} тон
   - Соответствует длине: {length_ru}
   - Создаёт эмоциональную связь с читателем
   - Если это не последний эпизод, создаёт интригу для продолжения
"""

            if episode_number == 1:
                prompt += """   - Это первый эпизод - заинтригуй читателя и представь главного героя
"""
            elif episode_number == total_episodes:
                prompt += """   - Это финальный эпизод - создай удовлетворяющую концовку
"""
            else:
                prompt += """   - Это промежуточный эпизод - развивай сюжет и поддерживай интригу
"""

            if include_hashtags:
                prompt += f"""3. Добавь {max_hashtags} релевантных хэштега
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

            logger.info(f"Генерация поста для эпизода {episode_number}/{total_episodes}: {episode_title[:50]}")

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

                logger.info(f"Успешно сгенерирован пост для эпизода {episode_number}: {result['title'][:50]}")
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {clean_response}")
                return {
                    "success": False,
                    "error": f"JSON parsing error: {str(e)}",
                    "raw_response": clean_response
                }

        except Exception as e:
            logger.error(f"Error generating post from episode: {e}", exc_info=True)
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
