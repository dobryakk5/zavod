"""Media-related mixins for AIContentGenerator."""

from __future__ import annotations

import os
import random
from typing import Any, Callable, Dict, List, Optional

from . import foto_video_gen
from .ai_generator_base import logger
from .system_settings import get_photo_prompt_instructions, get_video_prompt_instructions


def _get_video_prompt_max_length(default: int = 1900) -> int:
    env_value = os.getenv("VEO_PROMPT_MAX_LENGTH") or os.getenv("VIDEO_PROMPT_MAX_LENGTH")
    if not env_value:
        return default
    try:
        value = int(env_value)
        return value if value > 0 else default
    except ValueError:
        logger.warning("Некорректное значение VEO_PROMPT_MAX_LENGTH/VIDEO_PROMPT_MAX_LENGTH: %s", env_value)
        return default


def _limit_video_prompt_length(prompt: str, max_length: Optional[int] = None) -> str:
    """Trim video prompts to avoid downstream truncation."""
    if not prompt:
        return ""
    limit = max_length if max_length and max_length > 0 else _get_video_prompt_max_length()
    if limit and len(prompt) > limit:
        logger.info("Промпт для видео превышает лимит %s символов (длина=%s) — обрезаем", limit, len(prompt))
        return prompt[:limit]
    return prompt


def merge_video_prompt_with_additional(
    base_prompt: Optional[str],
    additional_prompt: Optional[str],
    max_length: Optional[int] = None,
) -> str:
    """
    Append client-specific technical instructions to the base video prompt.

    Base prompt отвечает за творческую часть, а additional_prompt содержит
    технические ограничения (например, язык, тип персонажей).
    """
    base = (base_prompt or "").strip()
    additional = (additional_prompt or "").strip()
    if additional:
        if base:
            combined = f"{base}\n\n{additional}"
        else:
            combined = additional
    else:
        combined = base
    return _limit_video_prompt_length(combined, max_length=max_length)


class MediaGenerationMixin:
    """Functions for prompts, images, and short-form video generation."""

    def generate_image_prompt(self, post_title: str, post_text: str) -> Optional[str]:
        """Generate an optimized image prompt from post content using AI."""
        try:
            extra_photo_instructions = get_photo_prompt_instructions().strip()
            admin_instructions_block = ""
            if extra_photo_instructions:
                admin_instructions_block = (
                    "\nДополнительные пожелания от администратора (учти их в ответе):\n"
                    f"{extra_photo_instructions}\n"
                )

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
{admin_instructions_block}
ФОРМАТ ОТВЕТА: Только промпт на английском языке, без дополнительных комментариев.

Пример хорошего промпта:
"A professional, modern office space with a diverse team collaborating around a sleek conference table, warm natural lighting through large windows, minimalist contemporary design, corporate photography style, high quality, focused composition"
"""

            logger.info("Генерация промпта для изображения поста: %s", post_title[:50])

            ai_response = self.get_ai_response(prompt, max_tokens=200, temperature=0.7)

            if not ai_response:
                logger.error("Не удалось получить промпт для изображения")
                return None

            image_prompt = ai_response.strip()
            logger.info("Сгенерирован промпт для изображения: %s", image_prompt[:100])

            return image_prompt

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating image prompt: %s", exc, exc_info=True)
            return None

    def generate_video_prompt(
        self,
        post_title: str,
        post_text: str,
        language: str = "ru",
        extra_instructions: Optional[str] = None,
        base_instructions: Optional[str] = None,
    ) -> Optional[str]:
        """Сгенерировать промпт для короткого вовлекающего видео по тексту поста."""
        try:
            lang_name = "русском" if language == "ru" else "английском"
            extra_video_instructions = (extra_instructions or "").strip()
            if not extra_video_instructions:
                extra_video_instructions = get_video_prompt_instructions().strip()
            admin_instructions_block = ""
            if extra_video_instructions:
                admin_instructions_block = (
                    "\nДополнительные пожелания от администратора (учти их в ответе):\n"
                    f"{extra_video_instructions}\n"
                )

            if not base_instructions:
                base_instructions = """Ты — режиссёр и сценарист коротких вертикальных видео TikTok/Reels. На входе у тебя текст поста.

1. Сделай вовлекающий, визуально насыщенный prompt на английском языке.
2. Описывай сцену, настроение, движения камеры, переходы, ключевые визуальные объекты.
3. Стиль — современный, динамичный, вдохновляющий. Максимум 3 предложения.
4. Не добавляй хештеги, кавычки и технические команды."""

            prompt = f"""{base_instructions}
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
            return _limit_video_prompt_length(video_prompt)

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating video prompt: %s", exc, exc_info=True)
            return None

    def generate_image(
        self,
        prompt: str,
        output_path: str,
        model: str = "openrouter",
    ) -> Optional[Dict[str, Any]]:
        """Генерация изображения с использованием вынесенного фото/видео модуля."""
        return foto_video_gen.generate_image(
            prompt=prompt,
            output_path=output_path,
            model=model,
            api_key=self.api_key,
            api_url=self.api_url,
            hf_client=self.hf_client,
        )

    def generate_video_from_image(
        self,
        image_path: str,
        prompt: str,
        method: str = "wan",
        negative_prompt: Optional[str] = None,
        **options: Any,
    ) -> Dict[str, Any]:
        """Создать видео из изображения, поддерживая WAN и VEO методы."""
        return foto_video_gen.generate_video_from_image(
            image_path=image_path,
            prompt=prompt,
            method=method,
            negative_prompt=negative_prompt,
            **options,
        )

    def generate_video_from_text(
        self,
        prompt: str,
        method: str = "veo",
        **options: Any,
    ) -> Dict[str, Any]:
        """Создать видео только по тексту (доступно для VEO)."""
        return foto_video_gen.generate_video_from_text(
            prompt=prompt,
            method=method,
            **options,
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
        on_post_generated: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Сгенерировать серию постов по SEO-группе и по каждому посту создать несколько VEO-видео."""

        if not seo_group_name:
            return {
                "success": False,
                "error": "Название SEO-группы обязательно",
            }

        if not seo_keywords or not isinstance(seo_keywords, list):
            return {
                "success": False,
                "error": "Список SEO-ключей должен быть непустым",
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
                "error": "Список SEO-ключей пуст после фильтрации",
            }

        try:
            posts_per_group = max(1, int(posts_per_group))
            videos_per_post = max(1, int(videos_per_post))
        except (TypeError, ValueError):
            return {
                "success": False,
                "error": "posts_per_group и videos_per_post должны быть числами",
            }

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
        template_copy.setdefault("type", "selling")
        client_video_prompt = (template_copy.get("video_prompt") or "").strip()

        logger.info(
            "Старт пакетной генерации: группа=%s, постов=%s, видео_на_пост=%s",
            seo_group_name,
            posts_per_group,
            videos_per_post,
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
                seo_keywords=per_post_keywords,
            )

            if not post_result or not post_result.get("success"):
                error_message = (post_result or {}).get("error", "Не удалось сгенерировать пост")
                logger.error("Ошибка генерации поста для ключа '%s': %s", keyword, error_message)
                summary["errors"].append(
                    {
                        "index": index,
                        "step": "post",
                        "seo_keyword": keyword,
                        "error": error_message,
                    }
                )
                summary["posts"].append(
                    {
                        "index": index,
                        "seo_keyword": keyword,
                        "success": False,
                        "error": error_message,
                        "videos": [],
                    }
                )
                summary["success"] = False
                continue

            base_video_prompt = self.generate_video_prompt(
                post_title=post_result.get("title", ""),
                post_text=post_result.get("text", ""),
                language=language,
                extra_instructions=client_video_prompt,
            )
            if not base_video_prompt:
                base_video_prompt = self._build_fallback_video_prompt(
                    post_result.get("title", keyword),
                    post_result.get("text", ""),
                    language,
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
                final_prompt = merge_video_prompt_with_additional(
                    variation_prompt,
                    client_video_prompt,
                )

                logger.info(
                    "[%s/%s] Генерация видео %s/%s через VEO (%s)",
                    index,
                    posts_per_group,
                    video_idx,
                    videos_per_post,
                    video_params.get("bot_username"),
                )

                video_result = self.generate_video_from_text(
                    prompt=final_prompt,
                    method=requested_method,
                    **video_params,
                )

                video_entry = {
                    "index": video_idx,
                    "prompt": final_prompt,
                    "success": bool(video_result.get("success")),
                    "video_path": video_result.get("video_path"),
                    "error": video_result.get("error"),
                    "model": video_result.get("model"),
                }

                if video_entry["success"]:
                    summary["video_successes"] += 1
                else:
                    summary["errors"].append(
                        {
                            "index": index,
                            "step": "video",
                            "video_index": video_idx,
                            "seo_keyword": keyword,
                            "error": video_entry["error"],
                        }
                    )
                    summary["success"] = False

                videos_info.append(video_entry)

            summary["posts"].append(
                {
                    "index": index,
                    "seo_keyword": keyword,
                    "success": True,
                    "post": post_result,
                    "videos": videos_info,
                }
            )

            if on_post_generated:
                try:
                    on_post_generated(
                        {
                            "post": post_result,
                            "videos": videos_info,
                            "keyword": keyword,
                            "index": index,
                        }
                    )
                except Exception as cb_exc:
                    logger.warning("on_post_generated callback failed: %s", cb_exc)

        summary["generated_posts"] = len(summary["posts"])

        if summary["errors"]:
            logger.warning(
                "Завершено с ошибками: %s/%s успешных видео",
                summary["video_successes"],
                summary["video_attempts"],
            )
        else:
            logger.info(
                "Успешно завершено: %s постов, %s видео",
                summary["generated_posts"],
                summary["video_successes"],
            )

        return summary

    @staticmethod
    def _build_fallback_video_prompt(
        post_title: str,
        post_text: str,
        language: str = "ru",
    ) -> str:
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


__all__ = ["MediaGenerationMixin", "merge_video_prompt_with_additional"]
