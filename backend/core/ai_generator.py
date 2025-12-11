"""
AI-powered content generator for social media posts
Uses OpenRouter API to generate engaging content from trends
Based on the architecture from ai_entity_matcher.py
"""

import os
import requests
import json
import logging
import ast
import re
from typing import Dict, Any, Optional, Callable, List, Tuple

from . import foto_video_gen
from .system_settings import (
    get_default_ai_model,
    get_post_ai_model,
    get_fallback_ai_model,
    get_video_prompt_instructions,
)

try:
    from huggingface_hub import InferenceClient
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False

logger = logging.getLogger(__name__)

_COMMENTED_VALUE_RE = re.compile(r'#\s*(?=")')
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _normalize_ai_json_response(raw_response: str) -> str:
    text = (raw_response or "").strip()
    if text.startswith('```json'):
        text = text[7:]
    if text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()


def _add_json_candidate(attempts: List[str], text: str):
    candidate = (text or "").strip()
    if not candidate:
        return
    if candidate not in attempts:
        attempts.append(candidate)
    sanitized = _COMMENTED_VALUE_RE.sub('', candidate)
    if sanitized and sanitized not in attempts:
        attempts.append(sanitized)


def _parse_ai_json_response(raw_response: str) -> Tuple[Optional[Dict[str, Any]], str, Optional[json.JSONDecodeError]]:
    clean_response = _normalize_ai_json_response(raw_response)
    attempts: List[str] = []
    _add_json_candidate(attempts, clean_response)

    for block in _CODE_BLOCK_RE.findall(raw_response):
        _add_json_candidate(attempts, block)

    last_error: Optional[json.JSONDecodeError] = None
    last_text = clean_response

    for candidate in attempts:
        try:
            return json.loads(candidate), candidate, None
        except json.JSONDecodeError as exc:
            last_error = exc
            last_text = candidate

    return None, last_text, last_error


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

        self.model = get_default_ai_model()
        self.post_model = get_post_ai_model()
        self.fallback_model = get_fallback_ai_model()
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

    def _call_openrouter(self, model: str, prompt: str, max_tokens: int, temperature: float) -> Optional[str]:
        """Call OpenRouter chat completions API and return text."""
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
                    "model": model,
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
                logger.error(
                    "OpenRouter API Error (%s) for model %s - %s",
                    response.status_code,
                    model,
                    response.text,
                )
                return None

        except requests.exceptions.Timeout:
            logger.error("OpenRouter API request timed out for model %s", model)
            return None
        except Exception as e:
            logger.error(f"Error calling OpenRouter API for model {model}: {e}", exc_info=True)
            return None

    def get_ai_response(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Optional[str]:
        """
        Send request to OpenRouter API with automatic fallback model.

        Args:
            prompt: Text prompt for AI
            max_tokens: Maximum tokens in response
            temperature: Creativity level (0.0-1.0)
            model: Preferred model name (defaults to self.model)

        Returns:
            AI response text or None if error
        """

        selected_model = (model or self.model or "").strip()
        if not selected_model:
            selected_model = get_default_ai_model()

        primary_response = self._call_openrouter(selected_model, prompt, max_tokens, temperature)
        if primary_response:
            return primary_response

        fallback_model = self.fallback_model.strip() if self.fallback_model else ""
        if fallback_model and fallback_model != selected_model:
            logger.info("Primary model %s failed, trying fallback %s", selected_model, fallback_model)
            return self._call_openrouter(fallback_model, prompt, max_tokens, temperature)

        return None

    def generate_post_text(
        self,
        trend_title: str,
        trend_description: str,
        topic_name: str,
        template_config: Dict[str, Any],
        seo_keywords: Dict[str, list] = None,
        trend_url: str = ""
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
                - trend_prompt_template: кастомный промпт под тренды
                - seo_prompt_template: кастомный промпт под SEO генерацию
                - prompt_type: "trend" (по умолчанию) или "seo"
                - prompt_template: legacy поле для обратной совместимости
                - additional_instructions: extra instructions
                - include_hashtags: bool
                - max_hashtags: int

                Переменные доступные в кастомных промптах:
                {topic_name}, {tone}, {length}, {language}, {type}, {avatar},
                {pains}, {desires}, {objections}, {seo_keywords}, {keyword},
                {trend_title}, {trend_description}, {trend_url}
            seo_keywords: Optional dict with keyword groups:
                - commercial: ["купить ...", ...]
                - general: ["топик москва", ...]
                - informational: ["как ...", ...]
                - long_tail: ["длинные фразы", ...]
            trend_url: Optional URL источника тренда

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
            prompt_type = template_config.get("prompt_type", "trend")
            trend_prompt_template = template_config.get("trend_prompt_template", "")
            seo_prompt_template = template_config.get("seo_prompt_template", "")
            legacy_prompt_template = template_config.get("prompt_template", "")
            prompt_template = (
                seo_prompt_template if str(prompt_type).lower() == "seo" else trend_prompt_template
            ) or legacy_prompt_template
            additional_instructions = template_config.get("additional_instructions", "")
            include_hashtags = template_config.get("include_hashtags", True)
            max_hashtags = template_config.get("max_hashtags", 5)
            post_type = template_config.get("type", "")
            avatar = template_config.get("avatar", "")
            brand = template_config.get("brand", "")
            pains = template_config.get("pains", "")
            desires = template_config.get("desires", "")
            objections = template_config.get("objections", "")

            # Извлечь случайные SEO-ключи из каждой группы
            import random
            selected_seo_keywords = []
            first_keyword = ""  # Основной ключ для переменной {keyword}
            if seo_keywords and isinstance(seo_keywords, dict):
                for group_name, keywords_list in seo_keywords.items():
                    if keywords_list and isinstance(keywords_list, list) and len(keywords_list) > 0:
                        # Выбрать случайный ключ из группы
                        random_keyword = random.choice(keywords_list)
                        selected_seo_keywords.append(f"{random_keyword} ({group_name})")
                        # Запомнить первый ключ как основной
                        if not first_keyword:
                            first_keyword = random_keyword

                logger.info(f"Выбраны SEO-ключи для поста: {selected_seo_keywords}")
            seo_keywords_for_prompt = ", ".join(selected_seo_keywords)

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
                "short": "короткий (500-1000 символов)",
                "medium": "средний (1000-1500 символов)",
                "long": "длинный (1500-2000 символов)"
            }

            tone_ru = tone_map.get(tone, tone)
            length_ru = length_map.get(length, length)
            lang_name = "русском" if language == "ru" else "английском"

            format_kwargs = {
                "trend_title": trend_title,
                "trend_description": trend_description,
                "trend_url": trend_url or "",
                "topic_name": topic_name,
                "tone": tone_ru,
                "length": length_ru,
                "language": lang_name,
                "type": post_type,
                "avatar": avatar,
                "brand": brand,
                "pains": pains,
                "desires": desires,
                "objections": objections,
                "seo_keywords": seo_keywords_for_prompt or "",
                "keyword": first_keyword or "",
            }

            # Если есть кастомный промпт-шаблон, используем его
            if prompt_template:
                try:
                    prompt = prompt_template.format(**format_kwargs)
                except KeyError as exc:
                    missing = exc.args[0]
                    logger.warning(
                        f"В промпте отсутствует значение для плейсхолдера '{missing}'. "
                        "Используем дефолтный промпт."
                    )
                    prompt_template = ""
            if not prompt_template:
                # Дефолтные промпты
                if str(prompt_type).lower() == "seo":
                    prompt = f"""
Ты - SEO-копирайтер и SMM-стратег, который создаёт контент для социальных сетей.

ДАННЫЕ О ЦЕЛЕВОЙ АУДИТОРИИ:
Аватар: {avatar}
Боли: {pains}
Хотелки: {desires}
Возражения: {objections}

ЗАДАЧА: Создай {length_ru} пост для социальных сетей в {tone_ru} стиле на {lang_name} языке,
используя SEO-ключевые фразы: {seo_keywords_for_prompt or "ключи отсутствуют"}.

ТЕМА БИЗНЕСА: {topic_name}

ИНСТРУКЦИИ:
1. Сформируй цепляющий заголовок (до 100 символов)
2. Напиши основной текст, который:
   - Связывает SEO-ключи с продуктом/услугой
   - Отражает боли и желания целевой аудитории
   - Выстраивает логичную структуру для {post_type} типа контента
   - Соответствует требуемой длине: {length_ru}
"""
                else:
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
Источник: {trend_url}

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
            post_model = (self.post_model or self.model)
            ai_response = self.get_ai_response(prompt, max_tokens=2000, temperature=0.7, model=post_model)

            if not ai_response:
                return {
                    "success": False,
                    "error": "Failed to get response from AI"
                }

            # Парсинг JSON ответа
            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error:
                logger.error(f"Failed to parse AI response as JSON: {normalized_text}")
                return {
                    "success": False,
                    "error": f"JSON parsing error: {str(parse_error)}",
                    "raw_response": normalized_text
                }

            result = parsed_result or {}

            # Валидация структуры ответа
            if "title" not in result or "text" not in result:
                logger.error(f"Invalid AI response structure: {normalized_text}")
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
        language: str = "ru",
        brand: str = "",
        avatar: str = "",
        pains: str = "",
        desires: str = "",
        objections: str = "",
        on_group_generated: Optional[Callable[[str, list], None]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate 5 SEO artifacts (pains, desires, objections, avatar self-descriptions, keyword mixes)
        for a topic/client combination using AI.

        Args:
            topic_name: Topic name (e.g., "студия танцев")
            keywords: Existing keywords list for the topic
            language: Language code (ru/en)
            brand: Client/brand name
            avatar: Client avatar description
            pains: Audience pains
            desires: Audience desires
            objections: Audience objections/fears

        Returns:
            Dict with generated keyword groups:
            {
                "keyword_groups": {
                    "seo_pains": [...],
                    "seo_desires": [...],
                    "seo_objections": [...],
                    "seo_avatar": [...],
                    "seo_keywords": [...]
                },
                "success": True/False,
                "error": "error message if failed"
            }
        """
        try:
            lang_name = "русском" if language == "ru" else "английском"
            keywords_str = ", ".join(keywords) if keywords else "не указаны"

            def _cleanup_value(value: str, fallback: str = "не указано") -> str:
                if value:
                    stripped = value.strip()
                    if stripped:
                        return stripped
                return fallback

            brand_name = _cleanup_value(brand or topic_name, topic_name)
            avatar_desc = _cleanup_value(avatar)
            pains_desc = _cleanup_value(pains)
            desires_desc = _cleanup_value(desires)
            objections_desc = _cleanup_value(objections)

            def _strip_code_fence(text: str) -> str:
                stripped = text.strip()
                if stripped.startswith("```"):
                    stripped = stripped[3:]
                    stripped = stripped.lstrip()
                    if "\n" in stripped:
                        first_line, rest = stripped.split("\n", 1)
                        first_line_clean = first_line.strip().lower()
                        if first_line_clean and first_line_clean.isalpha():
                            stripped = rest
                        else:
                            stripped = first_line + "\n" + rest
                    if stripped.endswith("```"):
                        stripped = stripped[:-3]
                return stripped.strip()

            def _parse_list(text: str, variable: str) -> list:
                cleaned = _strip_code_fence(text)
                if variable in cleaned:
                    # оставить только часть после первого "="
                    var_index = cleaned.find(variable)
                    eq_index = cleaned.find("=", var_index)
                    if eq_index != -1:
                        cleaned = cleaned[eq_index + 1:].strip()
                start = cleaned.find("[")
                end = cleaned.rfind("]")
                if start == -1:
                    list_text = cleaned
                elif end == -1 or end <= start:
                    list_text = cleaned[start:]
                else:
                    list_text = cleaned[start:end + 1]

                def _normalize_sequence(seq):
                    normalized_items = [str(item).strip() for item in seq if str(item).strip()]
                    return normalized_items

                literal_eval_attempted = False
                if start != -1:
                    try:
                        literal_eval_attempted = True
                        parsed = ast.literal_eval(list_text)
                        if isinstance(parsed, list):
                            normalized = _normalize_sequence(parsed)
                            if normalized:
                                return normalized
                    except (ValueError, SyntaxError):
                        logger.warning(f"Невозможно распарсить {variable} через literal_eval, пытаемся fallback")

                quotes_pattern = re.compile(r'"([^"]+)"|\'([^\']+)\'')
                quoted_matches = []
                for match in quotes_pattern.finditer(list_text):
                    quoted_matches.append(match.group(1) or match.group(2))

                fallback_items = [item.strip() for item in quoted_matches if item and item.strip()]
                if not fallback_items:
                    bullet_items = []
                    for line in cleaned.splitlines():
                        line = line.strip()
                        if not line or line.startswith(variable):
                            continue
                        line = line.lstrip("-•*0123456789. \t")
                        line = line.strip()
                        if len(line) > 2:
                            bullet_items.append(line)
                    fallback_items = bullet_items

                if fallback_items:
                    if literal_eval_attempted:
                        logger.warning(f"Используем fallback-парсинг для {variable}, элементов: {len(fallback_items)}")
                    return fallback_items

                raise ValueError(f"Не удалось распарсить {variable}")

            logger.info(f"Генерация SEO-групп для темы: {topic_name} / бренд: {brand_name}")

            prompt_specs = [
                {
                    "key": "seo_pains",
                    "variable": "seo_pains",
                    "max_tokens": 1200,
                    "prompt": f"""
Ты — стратег по контенту и SEO-аналитике бренда {brand_name}.
Тема бизнеса: {topic_name}.
Проанализируй следующую аудиторию:

Аватар: {avatar_desc}
Боли: {pains_desc}
Возражения: {objections_desc}
Хотелки: {desires_desc}

Задача:
Сформируй список из 15–25 SEO-поисковых болей — фраз, которые люди реально могут вводить в Google/Yandex, пытаясь решить свои проблемы.
Формулируй так, как пишет сам клиент, максимально приближенно к естественному поисковому запросу.
Создавай запросы на {lang_name} языке.

Выведи результат в формате Python-переменной:
seo_pains = [ ... ]
"""
                },
                {
                    "key": "seo_desires",
                    "variable": "seo_desires",
                    "max_tokens": 1200,
                    "prompt": f"""
Ты — SEO-стратег бренда {brand_name}.
Тема бизнеса: {topic_name}.
На основе данных о целевой аудитории:

Аватар: {avatar_desc}
Хотелки: {desires_desc}
Боли: {pains_desc}

Создай список из 15–25 желаний, которые люди ищут в поиске (ключевые запросы, связанные с ростом, мечтами, результатами) на {lang_name} языке.

Выведи результат в формате Python-переменной:
seo_desires = [ ... ]
"""
                },
                {
                    "key": "seo_objections",
                    "variable": "seo_objections",
                    "max_tokens": 1000,
                    "prompt": f"""
Ты — маркетолог бренда {brand_name}.
Тема бизнеса: {topic_name}.
Используя данные:

Боли: {pains_desc}
Возражения: {objections_desc}
Страхи: {objections_desc}

Сгенерируй список из 10–20 поисковых возражений — фраз, которые человек ищет, сомневаясь или опасаясь купить. Используй формулировки, которые звучат как реальные запросы на {lang_name} языке.

Выведи в формате:
seo_objections = [ ... ]
"""
                },
                {
                    "key": "seo_avatar",
                    "variable": "seo_avatar",
                    "max_tokens": 1000,
                    "prompt": f"""
Ты — SEO-аналитик бренда {brand_name}.
Тема бизнеса: {topic_name}.
Используя данные об аудитории (аватар, профессия, стиль мышления, боли, хотелки), сформируй 10–15 формулировок того, как человек может описывать себя в поиске.

Аватар: {avatar_desc}
Боли: {pains_desc}
Хотелки: {desires_desc}
Возражения: {objections_desc}

Пример: "психолог который хочет клиентов через Instagram".
Генерируй формулировки на {lang_name} языке.

Выведи в формате:
seo_avatar = [ ... ]
"""
                },
                {
                    "key": "seo_keywords",
                    "variable": "seo_keywords",
                    "max_tokens": 1500,
                    "prompt": f"""
Ты — специалист по SEO-структурам для бренда {brand_name}.
Тема бизнеса: {topic_name}.
Используя данные:

Аватар: {avatar_desc}
Боли: {pains_desc}
Хотелки: {desires_desc}
Возражения: {objections_desc}
Существующие ключевые слова: {keywords_str}

Создай список из 20–40 SEO ключей (низкочастотных, среднечастотных и ключей-модификаторов), которые можно использовать для блога, соцсетей, лендинга, рилс и автогенерации контента.
Обязательно включай комбинации:
- [боль + решение]
- [хотелка + инструмент]
- [ниша + контент]
- [бренд + категория продукта]

Фразы должны быть записаны как реальные поисковые запросы на {lang_name} языке.

Выведи в формате:
seo_keywords = [ ... ]
"""
                },
            ]

            seo_results = {}
            for spec in prompt_specs:
                logger.info(f"Генерация блока {spec['key']} для темы '{topic_name}'")
                ai_response = self.get_ai_response(
                    spec["prompt"],
                    max_tokens=spec.get("max_tokens", 1200),
                    temperature=0.55
                )

                if not ai_response:
                    logger.error(f"Не удалось получить ответ для группы {spec['key']}")
                    return {
                        "success": False,
                        "error": f"Failed to get response for {spec['key']}"
                    }

                try:
                    parsed_list = _parse_list(ai_response, spec["variable"])
                    seo_results[spec["key"]] = parsed_list
                    logger.info(f"{spec['key']}: получено {len(parsed_list)} элементов")
                    if on_group_generated:
                        try:
                            on_group_generated(spec["key"], parsed_list)
                        except Exception as cb_exc:
                            logger.warning(
                                f"on_group_generated callback failed for {spec['key']}: {cb_exc}"
                            )
                except Exception as e:
                    logger.error(
                        f"Ошибка парсинга ответа для {spec['key']}: {e}; raw={ai_response[:200]}"
                    )
                    return {
                        "success": False,
                        "error": f"Failed to parse {spec['key']}: {str(e)}",
                        "raw_response": ai_response
                    }

            total_items = sum(len(items) for items in seo_results.values())
            logger.info(
                f"Успешно сгенерированы SEO группы ({', '.join(seo_results.keys())}), всего элементов: {total_items}"
            )

            return {
                "keyword_groups": seo_results,
                "success": True
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
            extra_video_instructions = get_video_prompt_instructions().strip()
            admin_instructions_block = ""
            if extra_video_instructions:
                admin_instructions_block = (
                    "\nДополнительные пожелания от администратора (учти их в ответе):\n"
                    f"{extra_video_instructions}\n"
                )
            prompt = f"""
Ты — режиссёр и сценарист коротких вертикальных видео TikTok/Reels. На входе у тебя текст поста.

1. Сделай вовлекающий, визуально насыщенный prompt на английском языке.
2. Описывай сцену, настроение, движения камеры, переходы, ключевые визуальные объекты.
3. Стиль — современный, динамичный, вдохновляющий. Максимум 3 предложения.
4. Не добавляй хештеги, кавычки и технические команды.
{admin_instructions_block}

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

    def generate_posts_with_videos_from_seo_group(
        self,
        seo_group_name: str,
        seo_keywords: List[str],
        topic_name: str,
        template_config: Dict[str, Any],
        posts_per_group: int = 10,
        videos_per_post: int = 3,
        video_method: str = "veo",
        video_options: Optional[Dict[str, Any]] = None,
        on_post_generated: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """Сгенерировать серию постов по SEO-группе и по каждому посту создать несколько VEO-видео."""

        if not seo_group_name:
            return {
                "success": False,
                "error": "Название SEO-группы обязательно"
            }

        if not seo_keywords or not isinstance(seo_keywords, list):
            return {
                "success": False,
                "error": "Список SEO-ключей должен быть непустым"
            }

        clean_keywords = []
        for keyword in seo_keywords:
            if isinstance(keyword, str):
                trimmed = keyword.strip()
                if trimmed:
                    clean_keywords.append(trimmed)

        if not clean_keywords:
            return {
                "success": False,
                "error": "Список SEO-ключей пуст после фильтрации"
            }

        try:
            posts_per_group = max(1, int(posts_per_group))
            videos_per_post = max(1, int(videos_per_post))
        except (TypeError, ValueError):
            return {
                "success": False,
                "error": "posts_per_group и videos_per_post должны быть числами"
            }

        import random

        shuffled_keywords = clean_keywords.copy()
        random.shuffle(shuffled_keywords)
        selected_keywords = shuffled_keywords[:posts_per_group]
        if len(selected_keywords) < posts_per_group:
            while len(selected_keywords) < posts_per_group:
                selected_keywords.append(random.choice(clean_keywords))

        requested_method = (video_method or "veo").lower()
        if requested_method != "veo":
            logger.warning("Поддерживается только метод 'veo'. Переопределяем на VEO.")
            requested_method = "veo"

        video_params = dict(video_options or {})
        video_params.setdefault("bot_username", "syntxaibot")

        template_config = template_config or {}
        language = template_config.get("language", "ru")

        summary = {
            "success": True,
            "seo_group": seo_group_name,
            "topic": topic_name,
            "requested_posts": posts_per_group,
            "videos_per_post": videos_per_post,
            "posts": [],
            "errors": [],
            "video_attempts": 0,
            "video_successes": 0,
        }

        template_copy = dict(template_config)
        template_copy.setdefault("prompt_type", "seo")
        template_copy.setdefault("type", "selling")  # Дефолтный тип для SEO-постов

        logger.info(
            "Старт пакетной генерации: группа=%s, постов=%s, видео_на_пост=%s",
            seo_group_name,
            posts_per_group,
            videos_per_post
        )

        for index, keyword in enumerate(selected_keywords, start=1):
            per_post_keywords = {seo_group_name: [keyword]}
            logger.info("[%s/%s] Генерация поста по ключу '%s'", index, posts_per_group, keyword)

            post_result = self.generate_post_text(
                trend_title=f"SEO keyword: {keyword}",
                trend_description=f"Autogenerated from SEO group {seo_group_name}",
                trend_url="",
                topic_name=topic_name,
                template_config=template_copy,
                seo_keywords=per_post_keywords
            )

            if not post_result or not post_result.get("success"):
                error_message = (post_result or {}).get("error", "Не удалось сгенерировать пост")
                logger.error("Ошибка генерации поста для ключа '%s': %s", keyword, error_message)
                summary["errors"].append({
                    "index": index,
                    "step": "post",
                    "seo_keyword": keyword,
                    "error": error_message
                })
                summary["posts"].append({
                    "index": index,
                    "seo_keyword": keyword,
                    "success": False,
                    "error": error_message,
                    "videos": []
                })
                summary["success"] = False
                continue

            base_video_prompt = self.generate_video_prompt(
                post_title=post_result.get("title", ""),
                post_text=post_result.get("text", ""),
                language=language
            )
            if not base_video_prompt:
                base_video_prompt = self._build_fallback_video_prompt(
                    post_result.get("title", keyword),
                    post_result.get("text", ""),
                    language
                )

            videos_info = []
            for video_idx in range(1, videos_per_post + 1):
                summary["video_attempts"] += 1
                variation_prompt = base_video_prompt
                if videos_per_post > 1:
                    variation_prompt = (
                        f"{base_video_prompt}\nVariation #{video_idx}: offer a distinct cinematic take,"
                        " pacing and camera work."
                    )

                logger.info(
                    "[%s/%s] Генерация видео %s/%s через VEO (%s)",
                    index,
                    posts_per_group,
                    video_idx,
                    videos_per_post,
                    video_params.get("bot_username")
                )

                video_result = self.generate_video_from_text(
                    prompt=variation_prompt,
                    method=requested_method,
                    **video_params
                )

                video_entry = {
                    "index": video_idx,
                    "prompt": variation_prompt,
                    "success": bool(video_result.get("success")),
                    "video_path": video_result.get("video_path"),
                    "error": video_result.get("error"),
                    "model": video_result.get("model")
                }

                if video_entry["success"]:
                    summary["video_successes"] += 1
                else:
                    summary["success"] = False
                    summary["errors"].append({
                        "index": index,
                        "step": "video",
                        "seo_keyword": keyword,
                        "video_index": video_idx,
                        "error": video_entry["error"] or "Неизвестная ошибка VEO"
                    })

                videos_info.append(video_entry)

            post_payload = {
                "index": index,
                "seo_keyword": keyword,
                "post": post_result,
                "videos": videos_info,
                "success": all(video["success"] for video in videos_info)
            }
            summary["posts"].append(post_payload)

            if on_post_generated:
                try:
                    on_post_generated(post_payload)
                except Exception as cb_exc:
                    logger.warning("on_post_generated callback failed: %s", cb_exc)

        summary["generated_posts"] = len(summary["posts"])

        if summary["errors"]:
            logger.warning(
                "Завершено с ошибками: %s/%s успешных видео",
                summary["video_successes"],
                summary["video_attempts"]
            )
        else:
            logger.info(
                "Успешно завершено: %s постов, %s видео",
                summary["generated_posts"],
                summary["video_successes"]
            )

        return summary

    @staticmethod
    def _build_fallback_video_prompt(post_title: str, post_text: str, language: str = "ru") -> str:
        """Создать простой промпт на английском для видео по тексту поста."""
        snippet = (post_text or "").strip()
        if len(snippet) > 900:
            snippet = snippet[:900] + "..."

        lang_label = "Russian" if language == "ru" else "English"
        return (
            "Create a vertical 9:16 short-form social media video with cinematic motion.\n"
            f"Base language of the provided script: {lang_label}.\n"
            f"Title: {post_title}.\n"
            f"Script idea: {snippet}"
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

                parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
                if parse_error:
                    logger.error(f"Failed to parse AI response as JSON: {normalized_text}")
                    return {
                        "success": False,
                        "error": f"JSON parsing error: {str(parse_error)}",
                        "raw_response": normalized_text
                    }

                result = parsed_result or {}

                # Валидация структуры ответа
                if "title" not in result or "episodes" not in result:
                    logger.error(f"Invalid AI response structure: {normalized_text}")
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
                "short": "короткий (500-1000 символов)",
                "medium": "средний (1000-1500 символов)",
                "long": "длинный (1500-2000 символов)"
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
            post_model = (self.post_model or self.model)
            ai_response = self.get_ai_response(prompt, max_tokens=2000, temperature=0.7, model=post_model)

            if not ai_response:
                return {
                    "success": False,
                    "error": "Failed to get response from AI"
                }

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error:
                logger.error(f"Failed to parse AI response as JSON: {normalized_text}")
                return {
                    "success": False,
                    "error": f"JSON parsing error: {str(parse_error)}",
                    "raw_response": normalized_text
                }

            result = parsed_result or {}

            # Валидация структуры ответа
            if "title" not in result or "text" not in result:
                logger.error(f"Invalid AI response structure: {normalized_text}")
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
