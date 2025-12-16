"""Content-related mixins for AIContentGenerator."""

from __future__ import annotations

import ast
import json
import random
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ai_generator_base import logger

_COMMENTED_VALUE_RE = re.compile(r'#\s*(?=")')
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def _normalize_ai_json_response(raw_response: str) -> str:
    text = (raw_response or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _add_json_candidate(attempts: List[str], text: str):
    candidate = (text or "").strip()
    if not candidate:
        return
    if candidate not in attempts:
        attempts.append(candidate)
    sanitized = _COMMENTED_VALUE_RE.sub("", candidate)
    if sanitized and sanitized not in attempts:
        attempts.append(sanitized)


def _parse_ai_json_response(
    raw_response: str,
) -> Tuple[Optional[Dict[str, Any]], str, Optional[json.JSONDecodeError]]:
    clean_response = _normalize_ai_json_response(raw_response)
    attempts: List[str] = []
    _add_json_candidate(attempts, clean_response)

    for block in _CODE_BLOCK_RE.findall(raw_response):
        _add_json_candidate(attempts, block)

    last_error: Optional[json.JSONDecodeError] = None
    last_text = clean_response
    decoder = json.JSONDecoder()

    for candidate in attempts:
        try:
            return json.loads(candidate), candidate, None
        except json.JSONDecodeError as exc:
            last_error = exc
            last_text = candidate
            try:
                parsed_obj, end_index = decoder.raw_decode(candidate)
                if parsed_obj is not None:
                    truncated = candidate[:end_index]
                    return parsed_obj, truncated, None
            except json.JSONDecodeError:
                continue

    return None, last_text, last_error


class ContentGenerationMixin:
    """Methods for hooks, posts, SEO artifacts and related helpers."""

    def _repair_json_structure(
        self,
        broken_text: str,
        schema_hint: str,
        max_tokens: int = 600,
    ) -> Optional[Dict[str, Any]]:
        """Attempt to repair malformed AI output to the expected JSON schema."""
        if not broken_text or not broken_text.strip():
            return None

        repair_prompt = f"""
Ты получил ответ модели, который не соответствует ожидаемому JSON-формату.
Приведи текст ниже к строго валидному JSON согласно схеме:
{schema_hint}

ВАЖНО:
- Верни только JSON без комментариев.
- Сохрани исходный смысл и данные.

Текст для исправления:
<<<{broken_text}>>>
"""

        repaired_response = self.get_ai_response(
            repair_prompt,
            max_tokens=max_tokens,
            temperature=0.1,
        )
        if not repaired_response:
            return None

        repaired_json, _, parse_error = _parse_ai_json_response(repaired_response)
        if parse_error:
            logger.error("JSON repair attempt failed: %s", parse_error)
            return None
        return repaired_json

    def generate_hook_title(
        self,
        trend_title: str,
        trend_description: str,
        topic_name: str,
        template_config: Dict[str, Any],
        seo_keywords: Dict[str, list] = None,
    ) -> Optional[str]:
        """Generate a catchy mini-title (hook title) for a post."""
        try:
            tone = template_config.get("tone", "professional")
            language = template_config.get("language", "ru")
            post_type = template_config.get("type", "")
            avatar = template_config.get("avatar", "")

            first_keyword = ""
            if seo_keywords and isinstance(seo_keywords, dict):
                for _, keywords_list in seo_keywords.items():
                    if (
                        keywords_list
                        and isinstance(keywords_list, list)
                        and len(keywords_list) > 0
                    ):
                        first_keyword = random.choice(keywords_list)
                        break

            tone_map = {
                "professional": "профессиональный",
                "friendly": "дружественный",
                "informative": "информационный",
                "casual": "непринуждённый",
                "enthusiastic": "восторженный",
            }
            tone_ru = tone_map.get(tone, tone)

            type_descriptions = {
                "selling": "продающий (продвигает продукт/услугу)",
                "expert": "экспертный (демонстрирует экспертизу)",
                "trigger": "триггерный (вызывает эмоции, задает вопросы)",
                "educational": "образовательный (учит чему-то)",
                "entertainment": "развлекательный (забавляет)",
                "news": "новостной (сообщает новости)",
                "motivational": "мотивирующий (вдохновляет на действие)",
            }
            type_description = type_descriptions.get(post_type, "универсальный")

            if language.lower() == "ru":
                prompt = f"""Создай короткий цепляющий заголовок (максимум 3 слова) для поста в соцсетях.

Тема: {topic_name}
Тренд: {trend_title}
Описание тренда: {trend_description}

Стиль: {tone_ru}
Тип поста: {type_description}
Целевая аудитория: {avatar[:200] if avatar else 'широкая аудитория'}

Требования к заголовку:
- Максимум 3 слова на русском языке
- Должен быть коротким и привлекательным
- Вызывать интерес или эмоции
- Использовать восклицательные знаки, вопросы или прямое обращение
- Быть релевантным теме

Примеры цепляющих заголовков:
• "Это работает!"
• "Секрет успеха!"
• "Внимание!"
• "Почему именно?"
• "Узнайте сейчас!"

Создай только заголовок из 1-3 слов, без кавычек и дополнительного текста:"""
            else:
                prompt = f"""Create a short catchy hook title (5-10 words) for a social media post.

Topic: {topic_name}
Trend: {trend_title}
Trend description: {trend_description}

Style: {tone}
Post type: {type_description}
Target audience: {avatar[:200] if avatar else 'general audience'}

Title requirements:
- Must be short and attractive
- Should provoke interest or emotions
- Use exclamation marks, questions, or direct address
- Maximum 10 words
- Be relevant to the topic

Examples of catchy titles:
• "This will change your life!"
• "The secret few people know"
• "Breaking: Important news!"
• "Why this works?"
• "Learn the truth right now!"

Create only the title, without quotes or additional text:"""

            if first_keyword:
                prompt += f"\n\nSEO keyword to include: {first_keyword}"

            response = self.get_ai_response(
                prompt=prompt,
                max_tokens=50,
                temperature=0.9,
            )

            if response and response.strip():
                hook_title = response.strip().strip('"').strip("'").strip()
                words = hook_title.split()
                if len(words) > 3:
                    words = words[:3]
                    hook_title = " ".join(words)
                if len(hook_title) > 30:
                    hook_title = hook_title[:27] + "..."
                logger.info("Generated hook title: '%s'", hook_title)
                return hook_title

            logger.warning("Failed to generate hook title")
            return None

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating hook title: %s", exc, exc_info=True)
            return None

    def generate_post_text(
        self,
        trend_title: str,
        trend_description: str,
        topic_name: str,
        template_config: Dict[str, Any],
        seo_keywords: Dict[str, list] = None,
        trend_url: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Generate post text from trend using AI."""
        try:
            tone = template_config.get("tone", "professional")
            length = template_config.get("length", "medium")
            language = template_config.get("language", "ru")
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
            books = template_config.get("books", "")

            import random

            selected_seo_keywords: List[str] = []
            first_keyword = ""
            if seo_keywords:
                if isinstance(seo_keywords, dict):
                    for group_name, keywords_list in seo_keywords.items():
                        if keywords_list and isinstance(keywords_list, list):
                            valid_keywords = [kw.strip() for kw in keywords_list if isinstance(kw, str) and kw.strip()]
                            if not valid_keywords:
                                continue
                            random_keyword = random.choice(valid_keywords)
                            display_group = group_name or "keywords"
                            selected_seo_keywords.append(f"{random_keyword} ({display_group})")
                            if not first_keyword:
                                first_keyword = random_keyword
                elif isinstance(seo_keywords, list):
                    clean_list = [str(kw).strip() for kw in seo_keywords if str(kw).strip()]
                    if clean_list:
                        random_keyword = random.choice(clean_list)
                        selected_seo_keywords.append(random_keyword)
                        first_keyword = random_keyword
                elif isinstance(seo_keywords, str):
                    keyword_value = seo_keywords.strip()
                    if keyword_value:
                        selected_seo_keywords.append(keyword_value)
                        first_keyword = keyword_value

                logger.info("Выбраны SEO-ключи для поста: %s", selected_seo_keywords)
            seo_keywords_for_prompt = ", ".join(selected_seo_keywords)

            tone_map = {
                "professional": "профессиональный",
                "friendly": "дружественный",
                "informative": "информационный",
                "casual": "непринуждённый",
                "enthusiastic": "восторженный",
            }

            length_map = {
                "short": "короткий (500-1000 символов)",
                "medium": "средний (1000-1500 символов)",
                "long": "длинный (1500-2000 символов)",
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
                "books": books,
                "seo_keywords": seo_keywords_for_prompt or "",
                "keyword": first_keyword or "",
            }

            if prompt_template:
                try:
                    prompt = prompt_template.format(**format_kwargs)
                except KeyError as exc:
                    missing = exc.args[0]
                    logger.warning(
                        "В промпте отсутствует значение для плейсхолдера '%s'. Используем дефолтный промпт.",
                        missing,
                    )
                    prompt_template = ""
            if not prompt_template:
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

            if "{keyword}" in prompt:
                prompt = prompt.replace("{keyword}", first_keyword or "")
            if "{seo_keywords}" in prompt:
                prompt = prompt.replace("{seo_keywords}", seo_keywords_for_prompt or "")

            logger.info("Генерация поста: %s", trend_title[:80])

            post_model = (self.post_model or self.model).strip() or None
            ai_response = self.get_ai_response(
                prompt,
                max_tokens=2000,
                temperature=0.7,
                model=post_model,
            )

            if not ai_response:
                return {
                    "success": False,
                    "error": "Failed to get response from AI",
                }

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error:
                logger.error("Failed to parse AI response as JSON: %s", normalized_text)
                schema_hint = """
{
  "title": "string, заголовок поста",
  "text": "string, основной текст поста",
  "hashtags": ["string", ...]
}
"""
                repaired_result = self._repair_json_structure(normalized_text, schema_hint)
                parsed_result = repaired_result
                if not repaired_result:
                    return {
                        "success": False,
                        "error": f"JSON parsing error: {str(parse_error)}",
                        "raw_response": normalized_text,
                    }

            result = (parsed_result or {}).copy()

            if "title" not in result or "text" not in result:
                logger.error("Invalid AI response structure: %s", normalized_text)
                return {
                    "success": False,
                    "error": "Invalid response structure from AI",
                }

            if "hashtags" not in result:
                result["hashtags"] = []

            hook_title = self.generate_hook_title(
                trend_title=trend_title,
                trend_description=trend_description,
                topic_name=topic_name,
                template_config=template_config,
                seo_keywords=seo_keywords,
            )
            result["hook_title"] = hook_title or ""
            result["success"] = True

            logger.info("Успешно сгенерирован пост: %s", result["title"][:50])
            return result

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating post text: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
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
        on_group_generated: Optional[Callable[[str, list], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate 5 SEO artifacts (pains, desires, objections, avatars, keywords)."""
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
                    var_index = cleaned.find(variable)
                    eq_index = cleaned.find("=", var_index)
                    if eq_index != -1:
                        cleaned = cleaned[eq_index + 1 :].strip()
                start = cleaned.find("[")
                end = cleaned.rfind("]")
                if start == -1:
                    list_text = cleaned
                elif end == -1 or end <= start:
                    list_text = cleaned[start:]
                else:
                    list_text = cleaned[start : end + 1]

                def _normalize_sequence(seq):
                    normalized_items = [
                        str(item).strip() for item in seq if str(item).strip()
                    ]
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
                        logger.warning(
                            f"Невозможно распарсить {variable} через literal_eval, пытаемся fallback"
                        )

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
                        logger.warning(
                            f"Используем fallback-парсинг для {variable}, элементов: {len(fallback_items)}"
                        )
                    return fallback_items

                raise ValueError(f"Не удалось распарсить {variable}")

            logger.info(
                "Генерация SEO-групп для темы: %s / бренд: %s",
                topic_name,
                brand_name,
            )

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
""",
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
""",
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
""",
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
""",
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
""",
                },
            ]

            seo_results = {}
            for spec in prompt_specs:
                logger.info("Генерация блока %s для темы '%s'", spec["key"], topic_name)
                ai_response = self.get_ai_response(
                    spec["prompt"],
                    max_tokens=spec.get("max_tokens", 1200),
                    temperature=0.55,
                )

                if not ai_response:
                    logger.error("Не удалось получить ответ для группы %s", spec["key"])
                    return {
                        "success": False,
                        "error": f"Failed to get response for {spec['key']}",
                    }

                try:
                    parsed_list = _parse_list(ai_response, spec["variable"])
                    seo_results[spec["key"]] = parsed_list
                    logger.info("%s: получено %s элементов", spec["key"], len(parsed_list))
                    if on_group_generated:
                        try:
                            on_group_generated(spec["key"], parsed_list)
                        except Exception as cb_exc:
                            logger.warning(
                                "on_group_generated callback failed for %s: %s",
                                spec["key"],
                                cb_exc,
                            )
                except Exception as exc:
                    logger.error(
                        "Ошибка парсинга ответа для %s: %s; raw=%s",
                        spec["key"],
                        exc,
                        ai_response[:200],
                    )
                    return {
                        "success": False,
                        "error": f"Failed to parse {spec['key']}: {str(exc)}",
                        "raw_response": ai_response,
                    }

            total_items = sum(len(items) for items in seo_results.values())
            logger.info(
                "Успешно сгенерированы SEO группы (%s), всего элементов: %s",
                ", ".join(seo_results.keys()),
                total_items,
            )

            return {
                "keyword_groups": seo_results,
                "success": True,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating SEO keywords: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def generate_book_recommendations(
        self,
        pains: str = "",
        desires: str = "",
        avatar: str = "",
        brand: str = "",
        language: str = "ru",
    ) -> Dict[str, Any]:
        """Подобрать книги, подходящие под боли и желания аудитории."""
        try:
            lang_name = "русском" if language == "ru" else "английском"
            pains_text = (pains or "").strip() or "не указаны"
            desires_text = (desires or "").strip() or "не указаны"
            avatar_text = (avatar or "").strip() or "не описан"
            brand_text = (brand or "").strip() or "без названия"

            prompt = f"""
Ты — эксперт по персонализированным подборкам книг для предпринимателей и экспертов.

БРЕНД/ПРОЕКТ: {brand_text}
ОПИСАНИЕ АВАТАРА: {avatar_text}
КЛЮЧЕВЫЕ БОЛИ: {pains_text}
КЛЮЧЕВЫЕ ЖЕЛАНИЯ: {desires_text}

Найди 10 книг (на русском или в переводе), которые помогут этой аудитории решить проблемы и достичь желаемого.

ТРЕБОВАНИЯ:
- Указывай точное название и автора книги.
- Добавь 1–2 предложения, почему книга пригодится именно этой аудитории.
- Ориентируйся на практические, прикладные и вдохновляющие издания.
- Пиши на {lang_name} языке.

ФОРМАТ ОТВЕТА, СТРОГО JSON:
{{
  "books": [
    {{"title": "Название", "author": "Автор", "reason": "Почему книга полезна"}},
    ...
  ]
}}

Верни ровно 10 элементов. Никаких пояснений вне JSON.
"""

            ai_response = self.get_ai_response(prompt, max_tokens=1800, temperature=0.4)
            if not ai_response:
                return {"success": False, "error": "Не удалось получить ответ от AI"}

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error:
                logger.error("Failed to parse book recommendations: %s", normalized_text)
                return {
                    "success": False,
                    "error": f"Ошибка разбора JSON: {str(parse_error)}",
                    "raw_response": normalized_text,
                }

            result = parsed_result or {}
            raw_books = result.get("books")
            if not isinstance(raw_books, list):
                return {
                    "success": False,
                    "error": "AI не вернул список книг",
                    "raw_response": result,
                }

            cleaned_books = []
            for item in raw_books:
                if isinstance(item, dict):
                    title = str(item.get("title", "")).strip()
                    author = str(item.get("author", "")).strip()
                    reason = str(item.get("reason", "")).strip()
                else:
                    text_value = str(item).strip()
                    parts = text_value.split("—", 1)
                    title = parts[0].strip()
                    author = parts[1].strip() if len(parts) > 1 else ""
                    reason = ""
                if not title:
                    continue
                cleaned_books.append(
                    {
                        "title": title,
                        "author": author,
                        "reason": reason or "Помогает проработать ключевые задачи аудитории",
                    }
                )
                if len(cleaned_books) >= 10:
                    break

            if not cleaned_books:
                return {
                    "success": False,
                    "error": "AI вернул пустой список книг",
                    "raw_response": result,
                }

            lines = [
                f"{idx + 1}. {book['title']}"
                + (f" — {book['author']}" if book["author"] else "")
                + (f": {book['reason']}" if book["reason"] else "")
                for idx, book in enumerate(cleaned_books)
            ]

            return {
                "success": True,
                "books": cleaned_books,
                "text": "\n".join(lines),
                "raw_response": result,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating book recommendations: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }


class StoryGenerationMixin:
    """Helper mixin for multi-episode story formats."""

    def generate_story_episodes(
        self,
        trend_title: str,
        trend_description: str,
        topic_name: str,
        episode_count: int,
        client_desires: str = "",
        language: str = "ru",
    ) -> Optional[Dict[str, Any]]:
        """Generate story episodes from trend using AI."""
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
        ...
        {{"order": {episode_count}, "title": "Заголовок эпизода {episode_count}"}}
    ]
}}

Ответь ТОЛЬКО JSON, без дополнительных комментариев."""

            logger.info("Генерация истории на основе тренда: %s", trend_title[:50])

            original_model = self.model
            self.model = "tngtech/tng-r1t-chimera:free"

            try:
                ai_response = self.get_ai_response(prompt, max_tokens=2000, temperature=0.8)

                if not ai_response:
                    return {
                        "success": False,
                        "error": "Failed to get response from AI",
                    }

                parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
                if parse_error:
                    logger.error("Failed to parse AI response as JSON: %s", normalized_text)
                    return {
                        "success": False,
                        "error": f"JSON parsing error: {str(parse_error)}",
                        "raw_response": normalized_text,
                    }

                result = parsed_result or {}

                if "title" not in result or "episodes" not in result:
                    logger.error("Invalid AI response structure: %s", normalized_text)
                    return {
                        "success": False,
                        "error": "Invalid response structure from AI",
                    }

                if not isinstance(result["episodes"], list) or len(result["episodes"]) != episode_count:
                    logger.warning(
                        "Expected %s episodes, got %s",
                        episode_count,
                        len(result.get("episodes", [])),
                    )

                result["success"] = True

                logger.info(
                    "Успешно сгенерирована история: %s (%s эпизодов)",
                    result["title"][:50],
                    len(result["episodes"]),
                )
                return result

            finally:
                self.model = original_model

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating story episodes: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def generate_post_from_episode(
        self,
        story_title: str,
        episode_title: str,
        episode_number: int,
        total_episodes: int,
        topic_name: str,
        template_config: Dict[str, Any],
        client_info: Dict[str, str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate a full post from a story episode."""
        try:
            tone = template_config.get("tone", "professional")
            length = template_config.get("length", "medium")
            language = template_config.get("language", "ru")
            include_hashtags = template_config.get("include_hashtags", True)
            max_hashtags = template_config.get("max_hashtags", 5)
            additional_instructions = template_config.get("additional_instructions", "")

            client_info = client_info or {}
            avatar = client_info.get("avatar", "")
            pains = client_info.get("pains", "")
            desires = client_info.get("desires", "")
            objections = client_info.get("objections", "")

            tone_map = {
                "professional": "профессиональный",
                "friendly": "дружественный",
                "informative": "информационный",
                "casual": "непринуждённый",
                "enthusiastic": "восторженный",
            }

            length_map = {
                "short": "короткий (500-1000 символов)",
                "medium": "средний (1000-1500 символов)",
                "long": "длинный (1500-2000 символов)",
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

            logger.info(
                "Генерация поста для эпизода %s/%s: %s",
                episode_number,
                total_episodes,
                episode_title[:50],
            )

            post_model = (self.post_model or self.model).strip() or None
            ai_response = self.get_ai_response(
                prompt,
                max_tokens=2000,
                temperature=0.7,
                model=post_model,
            )

            if not ai_response:
                return {
                    "success": False,
                    "error": "Failed to get response from AI",
                }

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error:
                logger.error("Failed to parse AI response as JSON: %s", normalized_text)
                return {
                    "success": False,
                    "error": f"JSON parsing error: {str(parse_error)}",
                    "raw_response": normalized_text,
                }

            result = parsed_result or {}

            if "title" not in result or "text" not in result:
                logger.error("Invalid AI response structure: %s", normalized_text)
                return {
                    "success": False,
                    "error": "Invalid response structure from AI",
                }

            if "hashtags" not in result:
                result["hashtags"] = []

            hook_title = self.generate_hook_title(
                trend_title=episode_title,
                trend_description=f"{story_title}. {episode_title}",
                topic_name=topic_name,
                template_config=template_config,
            )
            result["hook_title"] = hook_title or ""
            result["success"] = True

            logger.info(
                "Успешно сгенерирован пост для эпизода %s: %s",
                episode_number,
                result["title"][:50],
            )
            return result

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating post from episode: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }


__all__ = [
    "ContentGenerationMixin",
    "StoryGenerationMixin",
    "_parse_ai_json_response",
]
