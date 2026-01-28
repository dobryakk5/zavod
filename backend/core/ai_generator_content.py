"""Content-related mixins for AIContentGenerator."""

from __future__ import annotations

import ast
import json
import os
import random
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .ai_generator_base import logger
from .prompt_settings import render_generator_prompt

_COMMENTED_VALUE_RE = re.compile(r'#\s*(?=")')
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_SMART_QUOTES_MAP = {
    "“": '"',
    "”": '"',
    "„": '"',
    "‟": '"',
    "«": '"',
    "»": '"',
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
}


def _should_dump_ai_json_debug() -> bool:
    flag = (os.getenv("AI_JSON_DEBUG_DUMP") or "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    return bool(os.getenv("AI_JSON_DEBUG_DIR") or os.getenv("AI_JSON_DEBUG_PATH"))


def _dump_ai_json_debug(raw_response: str, normalized: str, tag: str) -> Optional[Path]:
    if not _should_dump_ai_json_debug():
        return None

    path_override = (os.getenv("AI_JSON_DEBUG_PATH") or "").strip()
    if path_override:
        path = Path(path_override)
    else:
        base_dir = os.getenv("AI_JSON_DEBUG_DIR")
        if base_dir:
            dir_path = Path(base_dir)
        else:
            dir_path = Path(__file__).resolve().parents[1] / "logs" / "ai_json"
        dir_path.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{tag}_{timestamp}.json"
        path = dir_path / filename

    payload = {
        "raw_response": raw_response,
        "normalized": normalized,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
        return path
    except Exception as exc:  # pragma: no cover - best effort logging
        logger.warning("Failed to dump AI JSON debug payload: %s", exc)
        return None


def _escape_newlines_in_strings(text: str) -> str:
    if not text:
        return text
    result: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if in_string:
            if escaped:
                result.append(ch)
                escaped = False
                continue
            if ch == "\\":
                result.append(ch)
                escaped = True
                continue
            if ch == '"':
                result.append(ch)
                in_string = False
                continue
            if ch == "\n":
                result.append("\\n")
                continue
            if ch == "\r":
                result.append("\\r")
                continue
            result.append(ch)
        else:
            result.append(ch)
            if ch == '"':
                in_string = True
                escaped = False
    return "".join(result)


def _strip_trailing_commas(text: str) -> str:
    if not text:
        return text
    return re.sub(r",\s*([}\]])", r"\1", text)


def _replace_smart_quotes(text: str) -> str:
    if not text:
        return text
    return "".join(_SMART_QUOTES_MAP.get(ch, ch) for ch in text)


def _escape_unescaped_quotes_in_strings(text: str) -> str:
    if not text:
        return text
    result: list[str] = []
    in_string = False
    escaped = False
    for idx, ch in enumerate(text):
        if in_string:
            if escaped:
                result.append(ch)
                escaped = False
                continue
            if ch == "\\":
                result.append(ch)
                escaped = True
                continue
            if ch == '"':
                # Treat as closing quote if next non-space char is a structural delimiter.
                j = idx + 1
                while j < len(text) and text[j].isspace():
                    j += 1
                if j >= len(text) or text[j] in {",", "}", "]", ":"}:
                    result.append(ch)
                    in_string = False
                else:
                    result.append('\\"')
                continue
            if ch == "\n":
                result.append("\\n")
                continue
            if ch == "\r":
                result.append("\\r")
                continue
            result.append(ch)
        else:
            result.append(ch)
            if ch == '"':
                in_string = True
                escaped = False
    return "".join(result)


def _insert_missing_commas(text: str) -> str:
    if not text:
        return text

    def previous_non_space(buffer: list[str]) -> str:
        for item in reversed(buffer):
            if not item.isspace():
                return item
        return ""

    result: list[str] = []
    in_string = False
    escaped = False
    last_token_value = False
    idx = 0

    def is_boundary(pos: int) -> bool:
        if pos < 0 or pos >= len(text):
            return True
        return not (text[pos].isalnum() or text[pos] == "_")

    while idx < len(text):
        ch = text[idx]
        if in_string:
            result.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
                last_token_value = True
            idx += 1
            continue

        if ch.isspace():
            result.append(ch)
            idx += 1
            continue

        starts_token = ch in {'"', "{", "["} or ch.isdigit() or ch == "-" or ch in {"t", "f", "n"}
        if starts_token and last_token_value:
            prev = previous_non_space(result)
            if prev and prev not in {",", "{", "[", ":"}:
                result.append(",")

        if ch == '"':
            in_string = True
            escaped = False
            result.append(ch)
            idx += 1
            continue

        if ch in {"{", "["}:
            last_token_value = False
            result.append(ch)
            idx += 1
            continue

        if ch in {"}", "]"}:
            last_token_value = True
            result.append(ch)
            idx += 1
            continue

        if ch == ",":
            last_token_value = False
            result.append(ch)
            idx += 1
            continue

        if ch == ":":
            last_token_value = False
            result.append(ch)
            idx += 1
            continue

        if ch.isdigit() or ch == "-":
            start = idx
            idx += 1
            while idx < len(text) and text[idx] not in " \t\r\n,]}":
                idx += 1
            result.append(text[start:idx])
            last_token_value = True
            continue

        if (
            text.startswith("true", idx)
            and is_boundary(idx - 1)
            and is_boundary(idx + 4)
        ) or (
            text.startswith("false", idx)
            and is_boundary(idx - 1)
            and is_boundary(idx + 5)
        ) or (
            text.startswith("null", idx)
            and is_boundary(idx - 1)
            and is_boundary(idx + 4)
        ):
            if text.startswith("true", idx):
                token = "true"
            elif text.startswith("false", idx):
                token = "false"
            else:
                token = "null"
            result.append(token)
            idx += len(token)
            last_token_value = True
            continue

        result.append(ch)
        idx += 1

    return "".join(result)


def _replace_json_literals_for_python(text: str) -> str:
    if not text:
        return text
    result: list[str] = []
    in_string = False
    escaped = False
    quote_char = '"'
    idx = 0
    def is_boundary(pos: int) -> bool:
        if pos < 0 or pos >= len(text):
            return True
        return not (text[pos].isalnum() or text[pos] == "_")

    while idx < len(text):
        ch = text[idx]
        if in_string:
            result.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote_char:
                in_string = False
            idx += 1
            continue

        if ch in {"'", '"'}:
            in_string = True
            quote_char = ch
            result.append(ch)
            idx += 1
            continue

        if text.startswith("true", idx) and is_boundary(idx - 1) and is_boundary(idx + 4):
            result.append("True")
            idx += 4
            continue
        if text.startswith("false", idx) and is_boundary(idx - 1) and is_boundary(idx + 5):
            result.append("False")
            idx += 5
            continue
        if text.startswith("null", idx) and is_boundary(idx - 1) and is_boundary(idx + 4):
            result.append("None")
            idx += 4
            continue

        result.append(ch)
        idx += 1
    return "".join(result)


def _try_literal_eval(candidate: str) -> Optional[Dict[str, Any]]:
    if not candidate:
        return None
    try:
        cleaned = _replace_json_literals_for_python(candidate)
        parsed = ast.literal_eval(cleaned)
    except (SyntaxError, ValueError):
        return None
    if isinstance(parsed, dict):
        return parsed
    return None


def _extract_json_object(text: str) -> str:
    if not text:
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return text
    return text[start : end + 1]


def _extract_json_array_by_key(text: str, key: str) -> str:
    if not text or not key:
        return ""
    needle = f"\"{key}\""
    idx = text.find(needle)
    if idx == -1:
        return ""
    idx = text.find("[", idx + len(needle))
    if idx == -1:
        return ""
    depth = 0
    in_string = False
    escaped = False
    start = idx
    for pos in range(idx, len(text)):
        ch = text[pos]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            escaped = False
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start : pos + 1]
    return text[start:]


def _split_top_level_json_objects(array_text: str) -> List[str]:
    if not array_text:
        return []
    text = array_text.strip()
    if text.startswith("["):
        text = text[1:]
    if text.endswith("]"):
        text = text[:-1]

    objects: list[str] = []
    in_string = False
    escaped = False
    depth = 0
    start: Optional[int] = None
    for idx, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            escaped = False
            continue

        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
            continue
        if ch == "}":
            depth = max(depth - 1, 0)
            if depth == 0 and start is not None:
                objects.append(text[start : idx + 1])
                start = None
            continue

    return objects


def _try_parse_json_object(candidate: str) -> Optional[Dict[str, Any]]:
    if not candidate:
        return None
    sanitized = _extract_json_object(candidate)
    sanitized = _replace_smart_quotes(sanitized)
    sanitized = _escape_unescaped_quotes_in_strings(sanitized)
    sanitized = _escape_newlines_in_strings(sanitized)
    sanitized = _insert_missing_commas(sanitized)
    sanitized = _strip_trailing_commas(sanitized)
    try:
        parsed = json.loads(sanitized)
    except json.JSONDecodeError:
        parsed = _try_literal_eval(sanitized)
    if isinstance(parsed, dict):
        return parsed
    return None


def _salvage_json_objects_for_key(text: str, key: str) -> Optional[list[Dict[str, Any]]]:
    array_text = _extract_json_array_by_key(text, key)
    if not array_text:
        return None
    objects = _split_top_level_json_objects(array_text)
    if not objects:
        return None
    parsed_items: list[Dict[str, Any]] = []
    for item in objects:
        parsed = _try_parse_json_object(item)
        if parsed:
            parsed_items.append(parsed)
    if parsed_items:
        return parsed_items
    return None


def _normalize_ai_json_response(raw_response: str) -> str:
    text = (raw_response or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _strip_code_fences(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```json"):
        value = value[7:]
    if value.startswith("```"):
        value = value[3:]
    if value.endswith("```"):
        value = value[:-3]
    return value.strip()


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
                sanitized = _extract_json_object(candidate)
                sanitized = _replace_smart_quotes(sanitized)
                sanitized = _escape_unescaped_quotes_in_strings(sanitized)
                sanitized = _escape_newlines_in_strings(sanitized)
                sanitized = _insert_missing_commas(sanitized)
                sanitized = _strip_trailing_commas(sanitized)
                if sanitized and sanitized != candidate:
                    try:
                        return json.loads(sanitized), sanitized, None
                    except json.JSONDecodeError as inner_exc:
                        last_error = inner_exc
                        last_text = sanitized
                parsed = _try_literal_eval(sanitized)
                if parsed is not None:
                    return parsed, sanitized, None
                continue

    if last_error:
        dump_path = _dump_ai_json_debug(raw_response, last_text, tag="parse_failed")
        if dump_path:
            logger.warning("AI JSON debug payload saved to %s", dump_path)

    return None, last_text, last_error


def _format_length_value(length: Any, default_length: int = 1200) -> str:
    """
    Convert numeric or legacy length values to a human-friendly string for prompts.
    Accepts old enum values (short/medium/long) and raw numbers.
    """
    legacy_map = {"short": 800, "medium": 1200, "long": 1800}

    if isinstance(length, str):
        normalized = length.strip().lower()
        if normalized in legacy_map:
            length = legacy_map[normalized]
        else:
            try:
                length = int(float(normalized))
            except (TypeError, ValueError):
                length = default_length

    try:
        length_int = int(length)
        if length_int <= 0:
            raise ValueError
    except (TypeError, ValueError):
        length_int = default_length

    return f"{length_int} символов"


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

        repair_prompt = render_generator_prompt(
            "repair_json_structure",
            schema_hint=schema_hint,
            broken_text=broken_text,
        )
        if not repair_prompt:
            logger.error("Missing generator prompt: repair_json_structure")
            return None

        repaired_response = self.get_ai_response(
            repair_prompt,
            max_tokens=max_tokens,
            temperature=0.1,
            response_format={"type": "json_object"},
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

            seo_keyword_line = ""
            if first_keyword:
                seo_keyword_line = render_generator_prompt(
                    "hook_title_seo_keyword_line",
                    first_keyword=first_keyword,
                )

            prompt_code = "hook_title_ru" if language.lower() == "ru" else "hook_title_en"
            avatar_label = avatar[:200] if avatar else ("широкая аудитория" if language.lower() == "ru" else "general audience")
            prompt = render_generator_prompt(
                prompt_code,
                topic_name=topic_name,
                trend_title=trend_title,
                trend_description=trend_description,
                tone_ru=tone_ru,
                tone=tone,
                type_description=type_description,
                avatar=avatar_label,
                seo_keyword_line=seo_keyword_line,
            )
            if not prompt:
                logger.warning("Missing generator prompt: %s", prompt_code)
                return None

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
        wordstat_phrases: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Generate post text from trend using AI."""
        try:
            tone = template_config.get("tone", "professional")
            length = template_config.get("length", 1200)
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
            wordstat_phrases_clean: List[str] = []
            if wordstat_phrases:
                for phrase in wordstat_phrases:
                    if not isinstance(phrase, str):
                        continue
                    cleaned = phrase.strip()
                    if cleaned and cleaned not in wordstat_phrases_clean:
                        wordstat_phrases_clean.append(cleaned)
                        if len(wordstat_phrases_clean) >= 2:
                            break

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

            tone_ru = tone_map.get(tone, tone)
            length_ru = _format_length_value(length)
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
                "wordstat_phrases": ", ".join(wordstat_phrases_clean),
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
                prompt_code = "post_text_seo_base" if str(prompt_type).lower() == "seo" else "post_text_trend_base"
                seo_keywords_display = seo_keywords_for_prompt or "ключи отсутствуют"

                hashtags_block = ""
                if include_hashtags:
                    hashtags_block = render_generator_prompt(
                        "post_text_hashtags_block",
                        max_hashtags=max_hashtags,
                    )

                seo_block = ""
                if selected_seo_keywords:
                    seo_keywords_str = "\n   - ".join(selected_seo_keywords)
                    seo_block = render_generator_prompt(
                        "post_text_seo_block",
                        seo_keywords_str=seo_keywords_str,
                    )

                wordstat_block = ""
                if wordstat_phrases_clean:
                    wordstat_block = render_generator_prompt(
                        "post_text_wordstat_block",
                        wordstat_phrases=", ".join(wordstat_phrases_clean),
                    )

                additional_block = ""
                if additional_instructions:
                    additional_block = render_generator_prompt(
                        "post_text_additional_block",
                        additional_instructions=additional_instructions,
                    )

                response_format_block = render_generator_prompt("post_text_response_format_block")

                prompt = render_generator_prompt(
                    prompt_code,
                    avatar=avatar,
                    pains=pains,
                    desires=desires,
                    objections=objections,
                    length_ru=length_ru,
                    tone_ru=tone_ru,
                    lang_name=lang_name,
                    topic_name=topic_name,
                    trend_title=trend_title,
                    trend_description=trend_description,
                    trend_url=trend_url or "",
                    post_type=post_type,
                    seo_keywords_for_prompt=seo_keywords_display,
                    hashtags_block=hashtags_block,
                    seo_block=seo_block,
                    wordstat_block=wordstat_block,
                    additional_block=additional_block,
                    response_format_block=response_format_block,
                )
                if not prompt:
                    return {
                        "success": False,
                        "error": f"Missing generator prompt: {prompt_code}",
                    }

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
                response_format={"type": "json_object"},
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
                schema_hint = """
{
  "title": "string, заголовок поста",
  "text": "string, основной текст поста",
  "hashtags": ["string", ...]
}
"""
                repaired_result = self._repair_json_structure(normalized_text, schema_hint)
                if repaired_result and "title" in repaired_result and "text" in repaired_result:
                    result = repaired_result
                else:
                    logger.error("Invalid AI response structure: %s", normalized_text)
                    return {
                        "success": False,
                        "error": "Invalid response structure from AI",
                        "raw_response": normalized_text,
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
            result["wordstat_phrases_used"] = wordstat_phrases_clean
            result["success"] = True

            logger.info("Успешно сгенерирован пост: %s", result["title"][:50])
            return result

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating post text: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def refine_text_with_wordstat(
        self,
        title: str,
        text: str,
        phrases: List[str],
        language: str = "ru",
    ) -> Dict[str, Any]:
        """
        Уточнить готовый текст поста, естественно добавив точные Wordstat-фразы.
        """
        def _extract_jsonish_fields(raw: str) -> Optional[Dict[str, Any]]:
            """Try to pull title/text from almost-JSON with multiline strings."""
            if not raw:
                return None
            match = re.search(
                r'"title"\s*:\s*"(?P<title>.*?)"\s*,\s*"text"\s*:\s*"(?P<text>.*?)"\s*}',
                raw,
                re.DOTALL,
            )
            if not match:
                return None
            return {
                "title": match.group("title"),
                "text": match.group("text"),
            }

        cleaned_phrases: List[str] = []
        for phrase in phrases or []:
            if not isinstance(phrase, str):
                continue
            normalized = phrase.strip()
            if normalized and normalized not in cleaned_phrases:
                cleaned_phrases.append(normalized)
            if len(cleaned_phrases) >= 2:
                break

        base_text = (text or "").strip()
        if not cleaned_phrases or not base_text:
            return {"success": False, "error": "no_phrases_or_text"}

        max_text_len = 4000
        text_for_prompt = base_text
        if len(base_text) > max_text_len:
            text_for_prompt = base_text[:max_text_len] + "..."

        prompt = render_generator_prompt(
            "refine_text_wordstat",
            language=language,
            phrases=", ".join(cleaned_phrases),
            title=title,
            text_for_prompt=text_for_prompt,
        )
        if not prompt:
            return {"success": False, "error": "Missing generator prompt: refine_text_wordstat"}

        try:
            post_model = (self.post_model or self.model).strip() or None
        except Exception:
            post_model = None

        ai_response = self.get_ai_response(
            prompt,
            max_tokens=1200,
            temperature=0.35,
            model=post_model,
            response_format={"type": "json_object"},
        )
        if not ai_response:
            return {"success": False, "error": "no_response"}

        parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
        if parse_error:
            logger.warning("Failed to parse refine response as JSON: %s", normalized_text)
            parsed_result = _extract_jsonish_fields(normalized_text)
            schema_hint = """
{
  "title": "string, заголовок поста",
  "text": "string, текст поста"
}
"""
            if not parsed_result:
                repaired_result = self._repair_json_structure(normalized_text, schema_hint)
                parsed_result = repaired_result

        result = (parsed_result or {}).copy()
        if "title" not in result or "text" not in result:
            return {"success": False, "error": "invalid_refine_structure", "raw_response": normalized_text}

        result["success"] = True
        result["wordstat_phrases_used"] = cleaned_phrases
        return result

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
                    "prompt_code": "seo_keywords_pains",
                },
                {
                    "key": "seo_desires",
                    "variable": "seo_desires",
                    "max_tokens": 1200,
                    "prompt_code": "seo_keywords_desires",
                },
                {
                    "key": "seo_objections",
                    "variable": "seo_objections",
                    "max_tokens": 1000,
                    "prompt_code": "seo_keywords_objections",
                },
                {
                    "key": "seo_avatar",
                    "variable": "seo_avatar",
                    "max_tokens": 1000,
                    "prompt_code": "seo_keywords_avatar",
                },
                {
                    "key": "seo_keywords",
                    "variable": "seo_keywords",
                    "max_tokens": 1500,
                    "prompt_code": "seo_keywords_list",
                },
            ]

            seo_results = {}
            prompt_values = {
                "brand_name": brand_name,
                "topic_name": topic_name,
                "avatar_desc": avatar_desc,
                "pains_desc": pains_desc,
                "desires_desc": desires_desc,
                "objections_desc": objections_desc,
                "lang_name": lang_name,
                "keywords_str": keywords_str,
            }
            for spec in prompt_specs:
                logger.info("Генерация блока %s для темы '%s'", spec["key"], topic_name)
                prompt = render_generator_prompt(spec["prompt_code"], **prompt_values)
                if not prompt:
                    return {
                        "success": False,
                        "error": f"Missing generator prompt: {spec['prompt_code']}",
                    }
                ai_response = self.get_ai_response(
                    prompt,
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

            prompt = render_generator_prompt(
                "book_recommendations",
                brand_text=brand_text,
                avatar_text=avatar_text,
                pains_text=pains_text,
                desires_text=desires_text,
                lang_name=lang_name,
            )
            if not prompt:
                return {"success": False, "error": "Missing generator prompt: book_recommendations"}

            ai_response = self.get_ai_response(
                prompt,
                max_tokens=1800,
                temperature=0.4,
                response_format={"type": "json_object"},
            )
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

    def generate_project_semantics_from_books(
        self,
        books_text: str,
        brand: str = "",
        language: str = "ru",
    ) -> Dict[str, Any]:
        """Сформировать семантику проекта на основе списка экспертных книг."""
        try:
            books_value = (books_text or "").strip()
            if not books_value:
                return {"success": False, "error": "Книги не указаны"}

            lang_name = "русском" if language == "ru" else "английском"
            brand_text = (brand or "").strip() or "без названия"

            prompt = render_generator_prompt(
                "project_semantics_from_books",
                books_text=books_value,
                brand_text=brand_text,
                lang_name=lang_name,
            )
            if not prompt:
                return {"success": False, "error": "Missing generator prompt: project_semantics_from_books"}

            ai_response = self.get_ai_response(
                prompt,
                max_tokens=1600,
                temperature=0.35,
                response_format={"type": "json_object"},
            )
            if not ai_response:
                return {"success": False, "error": "Не удалось получить ответ от AI"}

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error or not isinstance(parsed_result, dict):
                repaired = self._repair_json_structure(
                    normalized_text,
                    schema_hint="""
{
  "groups": [
    {"name": "Название кластера", "phrases": ["фраза 1", "фраза 2"]}
  ],
  "keywords": ["ключ 1", "ключ 2"]
}
""",
                )
                if repaired and isinstance(repaired, dict):
                    parsed_result = repaired
                    parse_error = None

            if parse_error or not isinstance(parsed_result, dict):
                logger.error("Failed to parse project semantics: %s", normalized_text)
                return {
                    "success": False,
                    "error": f"Ошибка разбора JSON: {str(parse_error)}",
                    "raw_response": normalized_text,
                }

            whitespace_re = re.compile(r"\s+")

            def _clean_list(items) -> list:
                seen = set()
                cleaned: list[str] = []
                if not isinstance(items, list):
                    items = [items]
                for item in items:
                    value = whitespace_re.sub(" ", str(item or "").strip())
                    if not value:
                        continue
                    key = value.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    cleaned.append(value)
                return cleaned

            def _normalize_groups(payload: Dict[str, Any]) -> Dict[str, List[str]]:
                groups_payload = (
                    payload.get("groups")
                    or payload.get("clusters")
                    or payload.get("themes")
                    or {}
                )
                groups: Dict[str, List[str]] = {}
                if isinstance(groups_payload, dict):
                    for name, phrases in groups_payload.items():
                        group_name = whitespace_re.sub(" ", str(name or "").strip())
                        cleaned = _clean_list(phrases)
                        if group_name and cleaned:
                            groups[group_name] = cleaned[:20]
                elif isinstance(groups_payload, list):
                    for item in groups_payload:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("name") or item.get("group") or item.get("title") or ""
                        phrases = item.get("phrases") or item.get("items") or item.get("keywords") or []
                        group_name = whitespace_re.sub(" ", str(name or "").strip())
                        cleaned = _clean_list(phrases)
                        if group_name and cleaned:
                            groups[group_name] = cleaned[:20]
                return groups

            groups = _normalize_groups(parsed_result)
            keywords = _clean_list(
                parsed_result.get("keywords")
                or parsed_result.get("phrases")
                or parsed_result.get("semantic_core")
                or []
            )

            if not keywords and groups:
                flattened: list[str] = []
                for phrases in groups.values():
                    flattened.extend(phrases)
                keywords = _clean_list(flattened)

            keywords = keywords[:120]

            if not groups and not keywords:
                return {
                    "success": False,
                    "error": "AI вернул пустую семантику",
                    "raw_response": parsed_result,
                }

            return {
                "success": True,
                "groups": groups,
                "keywords": keywords,
                "raw_response": parsed_result,
                "prompt_used": prompt,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating project semantics: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def generate_semantic_groups_from_books(
        self,
        books_text: str,
        niche: str = "",
        audience: str = "",
        product: str = "",
        fragments: str = "",
        language: str = "ru",
    ) -> Dict[str, Any]:
        """Сформировать смысловые группы по книгам экспертов."""
        try:
            books_value = (books_text or "").strip()
            if not books_value:
                return {"success": False, "error": "Книги не указаны"}

            niche_text = (niche or "").strip() or "не указано"
            audience_text = (audience or "").strip() or "не указана"
            product_text = (product or "").strip() or "не указан"
            fragments_text = (fragments or "").strip() or "нет"

            prompt = render_generator_prompt(
                "semantic_groups_from_books",
                niche_text=niche_text,
                audience_text=audience_text,
                product_text=product_text,
                books_text=books_value,
                fragments_text=fragments_text,
            )
            if not prompt:
                return {"success": False, "error": "Missing generator prompt: semantic_groups_from_books"}

            ai_response = self.get_ai_response(
                prompt,
                max_tokens=2000,
                temperature=0.35,
                response_format={"type": "json_object"},
            )
            if not ai_response:
                return {"success": False, "error": "Не удалось получить ответ от AI"}

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error or not isinstance(parsed_result, dict):
                repaired = self._repair_json_structure(
                    normalized_text,
                    schema_hint="""
{
  "groups": [
    {
      "name": "Название",
      "description": "Что входит и что не входит",
      "scope": "narrow|normal|wide",
      "expected_clusters": 12,
      "source_books": ["Книга 1", "Книга 2"],
      "examples": ["пример 1", "пример 2"]
    }
  ]
}
""",
                )
                if repaired and isinstance(repaired, dict):
                    parsed_result = repaired
                    parse_error = None

            if parse_error or not isinstance(parsed_result, dict):
                logger.error("Failed to parse semantic groups: %s", normalized_text)
                return {
                    "success": False,
                    "error": f"Ошибка разбора JSON: {str(parse_error)}",
                    "raw_response": normalized_text,
                }

            groups_payload = (
                parsed_result.get("groups")
                or parsed_result.get("semantic_groups")
                or parsed_result.get("themes")
                or []
            )

            if not isinstance(groups_payload, list):
                return {
                    "success": False,
                    "error": "AI не вернул список смысловых групп",
                    "raw_response": parsed_result,
                }

            whitespace_re = re.compile(r"\s+")
            def normalize_source_books(value: Any) -> list[str]:
                if value is None:
                    return []
                raw_items: list[Any]
                if isinstance(value, list):
                    raw_items = value
                elif isinstance(value, str):
                    value = value.strip()
                    if not value:
                        return []
                    if "\n" in value:
                        raw_items = [item for item in value.splitlines() if item.strip()]
                    elif ";" in value and "," not in value:
                        raw_items = [item for item in value.split(";") if str(item).strip()]
                    else:
                        raw_items = [value]
                else:
                    raw_items = [value]

                cleaned: list[str] = []
                for item in raw_items:
                    text_value = ""
                    if isinstance(item, dict):
                        title = str(item.get("title") or item.get("name") or "").strip()
                        author = str(item.get("author") or "").strip()
                        if title and author:
                            text_value = f"{title} — {author}"
                        else:
                            text_value = title or author
                    else:
                        text_value = str(item or "").strip()
                    text_value = whitespace_re.sub(" ", text_value)
                    if text_value:
                        cleaned.append(text_value)

                seen_books: set[str] = set()
                unique: list[str] = []
                for item in cleaned:
                    key = item.lower()
                    if key in seen_books:
                        continue
                    seen_books.add(key)
                    unique.append(item)
                return unique

            seen = set()
            cleaned_groups: list[Dict[str, Any]] = []
            for item in groups_payload:
                if not isinstance(item, dict):
                    continue
                name = whitespace_re.sub(" ", str(item.get("name") or item.get("title") or "").strip())
                if not name:
                    continue
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                description = whitespace_re.sub(
                    " ",
                    str(item.get("description") or item.get("details") or "").strip(),
                )
                scope = str(item.get("scope") or "").strip().lower()
                if scope not in {"narrow", "normal", "wide"}:
                    scope = "normal"
                expected_raw = item.get("expected_clusters") or item.get("clusters") or None
                expected_clusters = None
                if expected_raw is not None and str(expected_raw).strip():
                    try:
                        expected_clusters = int(expected_raw)
                    except (TypeError, ValueError):
                        expected_clusters = None
                examples = item.get("examples") or []
                if not isinstance(examples, list):
                    examples = [examples]
                cleaned_examples = []
                for example in examples:
                    value = whitespace_re.sub(" ", str(example or "").strip())
                    if value:
                        cleaned_examples.append(value)
                source_books_raw = (
                    item.get("source_books")
                    or item.get("sources")
                    or item.get("books")
                )
                source_books = normalize_source_books(source_books_raw)
                cleaned_groups.append(
                    {
                        "name": name,
                        "description": description,
                        "scope": scope,
                        "expected_clusters": expected_clusters,
                        "source_books": source_books,
                        "examples": cleaned_examples,
                    }
                )

            if not cleaned_groups:
                return {
                    "success": False,
                    "error": "AI вернул пустой список смысловых групп",
                    "raw_response": parsed_result,
                }

            return {
                "success": True,
                "groups": cleaned_groups,
                "raw_response": parsed_result,
                "prompt_used": prompt,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating semantic groups: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def generate_semantic_clusters_from_group(
        self,
        *,
        niche: str,
        audience: str,
        product: str,
        group_name: str,
        group_description: str = "",
        group_scope: str = "",
        expected_clusters: Optional[int] = None,
        examples: Optional[list[str]] = None,
        source_books: Optional[list[str]] = None,
        language: str = "ru",
    ) -> Dict[str, Any]:
        """Сформировать SEO-кластеры (интенты) внутри смысловой группы."""
        try:
            name_value = (group_name or "").strip()
            if not name_value:
                return {"success": False, "error": "semantic_group_name_required"}

            niche_text = (niche or "").strip() or "не указано"
            audience_text = (audience or "").strip() or "не указана"
            product_text = (product or "").strip() or "не указан"
            description_text = (group_description or "").strip()
            scope_text = (group_scope or "").strip() or "normal"
            expected_value = ""
            if expected_clusters is not None:
                expected_value = str(expected_clusters)

            examples_list = examples or []
            if not isinstance(examples_list, list):
                examples_list = [examples_list]
            cleaned_examples = []
            whitespace_re = re.compile(r"\s+")
            for example in examples_list:
                value = whitespace_re.sub(" ", str(example or "").strip())
                if value:
                    cleaned_examples.append(value)
            examples_text = "\n".join(cleaned_examples) if cleaned_examples else "нет"
            if source_books is None:
                source_books_list = []
            elif isinstance(source_books, list):
                source_books_list = source_books
            else:
                source_books_list = [str(source_books)]
            cleaned_sources: list[str] = []
            for item in source_books_list:
                value = whitespace_re.sub(" ", str(item or "").strip())
                if value:
                    cleaned_sources.append(value)
            group_source_books = "; ".join(cleaned_sources) if cleaned_sources else "не указаны"

            prompt = render_generator_prompt(
                "semantic_clusters_from_group",
                niche_text=niche_text,
                audience_text=audience_text,
                product_text=product_text,
                group_name=name_value,
                group_description=description_text or "не указано",
                group_scope=scope_text,
                group_expected_clusters=expected_value or "не указано",
                group_examples=examples_text,
                group_source_books=group_source_books,
                language_note="Пиши на русском языке." if language.lower().startswith("ru") else "",
            )
            if not prompt:
                return {"success": False, "error": "Missing generator prompt: semantic_clusters_from_group"}

            ai_response = self.get_ai_response(
                prompt,
                max_tokens=2400,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            if not ai_response:
                return {"success": False, "error": "Не удалось получить ответ от AI"}

            schema_hint = """
{
  "clusters": [
    {
      "name": "string",
      "description": "string",
      "main_keyword": "string",
      "intent": "info|commercial|navigational|brand",
      "user_goal": "string",
      "cta": "string",
      "priority": "high|medium|low",
      "examples": ["string"]
    }
  ],
  "total_clusters": 0,
  "comment": "string"
}
"""

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error or not isinstance(parsed_result, dict):
                repaired = self._repair_json_structure(normalized_text, schema_hint=schema_hint)
                if repaired and isinstance(repaired, dict):
                    parsed_result = repaired
                    parse_error = None
            if parse_error or not isinstance(parsed_result, dict):
                sanitized = _extract_json_object(normalized_text)
                sanitized = _escape_newlines_in_strings(sanitized)
                sanitized = _strip_trailing_commas(sanitized)
                try:
                    parsed_candidate = json.loads(sanitized)
                except json.JSONDecodeError:
                    parsed_candidate = None
                if isinstance(parsed_candidate, dict):
                    parsed_result = parsed_candidate
                    parse_error = None
            if parse_error or not isinstance(parsed_result, dict):
                salvaged_clusters = _salvage_json_objects_for_key(normalized_text, "clusters")
                if salvaged_clusters:
                    parsed_result = {"clusters": salvaged_clusters}
                    parse_error = None

            if parse_error or not isinstance(parsed_result, dict):
                logger.error("Failed to parse semantic clusters: %s", normalized_text)
                return {
                    "success": False,
                    "error": f"Ошибка разбора JSON: {str(parse_error)}",
                    "raw_response": normalized_text,
                }

            clusters_payload = (
                parsed_result.get("clusters")
                or parsed_result.get("items")
                or parsed_result.get("semantic_clusters")
                or []
            )
            if not isinstance(clusters_payload, list):
                return {
                    "success": False,
                    "error": "AI не вернул список кластеров",
                    "raw_response": parsed_result,
                }

            allowed_intents = {"info", "commercial", "navigational", "brand"}
            priority_map = {"high": 3, "medium": 2, "low": 1}
            seen = set()
            cleaned_clusters: list[Dict[str, Any]] = []
            for item in clusters_payload:
                if not isinstance(item, dict):
                    continue
                name = whitespace_re.sub(" ", str(item.get("name") or item.get("title") or "").strip())
                if not name:
                    continue
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                description = whitespace_re.sub(" ", str(item.get("description") or "").strip())
                main_keyword = whitespace_re.sub(" ", str(item.get("main_keyword") or item.get("keyword") or "").strip())
                intent = str(item.get("intent") or "").strip().lower()
                if intent not in allowed_intents:
                    intent = ""
                user_goal = whitespace_re.sub(" ", str(item.get("user_goal") or "").strip())
                cta = whitespace_re.sub(" ", str(item.get("cta") or "").strip())
                priority_raw = item.get("priority")
                priority_value: Optional[int] = None
                if isinstance(priority_raw, str):
                    priority_value = priority_map.get(priority_raw.strip().lower())
                elif isinstance(priority_raw, (int, float)):
                    priority_value = int(priority_raw)
                if priority_value is not None and priority_value <= 0:
                    priority_value = None
                examples_payload = item.get("examples") or []
                if not isinstance(examples_payload, list):
                    examples_payload = [examples_payload]
                cleaned_examples = []
                for example in examples_payload:
                    value = whitespace_re.sub(" ", str(example or "").strip())
                    if value:
                        cleaned_examples.append(value)

                cleaned_clusters.append(
                    {
                        "name": name,
                        "description": description,
                        "main_keyword": main_keyword,
                        "intent": intent,
                        "user_goal": user_goal,
                        "cta": cta,
                        "priority": priority_value,
                        "examples": cleaned_examples,
                    }
                )

            if not cleaned_clusters:
                return {
                    "success": False,
                    "error": "AI вернул пустой список кластеров",
                    "raw_response": parsed_result,
                }

            return {
                "success": True,
                "clusters": cleaned_clusters,
                "raw_response": parsed_result,
                "prompt_used": prompt,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating semantic clusters: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def generate_semantic_phrases_from_cluster(
        self,
        *,
        niche: str,
        product: str,
        group_name: str,
        group_description: str = "",
        group_source_books: Optional[list[str]] = None,
        cluster_name: str,
        cluster_description: str = "",
        cluster_main_keyword: str = "",
        cluster_intent: str = "",
        cluster_user_goal: str = "",
        cluster_cta: str = "",
        language: str = "ru",
    ) -> Dict[str, Any]:
        """Сформировать список SEO-фраз для кластера."""
        try:
            niche_text = (niche or "").strip() or "не указано"
            product_text = (product or "").strip() or "не указано"
            group_name_text = (group_name or "").strip() or "не указано"
            group_description_text = (group_description or "").strip() or "не указано"
            cluster_name_text = (cluster_name or "").strip() or "не указано"
            cluster_description_text = (cluster_description or "").strip() or "не указано"
            cluster_main_keyword_text = (cluster_main_keyword or "").strip() or "не указано"
            cluster_intent_text = (cluster_intent or "").strip() or "не указано"
            cluster_user_goal_text = (cluster_user_goal or "").strip() or "не указано"
            cluster_cta_text = (cluster_cta or "").strip() or "не указано"

            books_list = group_source_books or []
            cleaned_books = []
            whitespace_re = re.compile(r"\s+")
            for item in books_list:
                value = whitespace_re.sub(" ", str(item or "").strip())
                if value:
                    cleaned_books.append(value)
            books_text = "; ".join(cleaned_books) if cleaned_books else "не указаны"

            prompt = render_generator_prompt(
                "semantic_phrases_from_cluster",
                niche_text=niche_text,
                product_text=product_text,
                group_name=group_name_text,
                group_description=group_description_text,
                group_source_books=books_text,
                cluster_name=cluster_name_text,
                cluster_description=cluster_description_text,
                cluster_main_keyword=cluster_main_keyword_text,
                cluster_intent=cluster_intent_text,
                cluster_user_goal=cluster_user_goal_text,
                cluster_cta=cluster_cta_text,
                language_note="Пиши на русском языке." if language.lower().startswith("ru") else "",
            )
            if not prompt:
                return {"success": False, "error": "Missing generator prompt: semantic_phrases_from_cluster"}

            ai_response = self.get_ai_response(
                prompt,
                max_tokens=2000,
                temperature=0.35,
                response_format={"type": "json_object"},
            )
            if not ai_response:
                return {"success": False, "error": "Не удалось получить ответ от AI"}

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error or not isinstance(parsed_result, dict):
                repaired = self._repair_json_structure(
                    normalized_text,
                    schema_hint="""
{
  "phrases": [
    {
      "phrase": "текст фразы",
      "type": "key",
      "intent": "info|commercial|navigational|brand",
      "comment": "пояснение"
    }
  ]
}
""",
                )
                if repaired and isinstance(repaired, dict):
                    parsed_result = repaired
                    parse_error = None

            if parse_error or not isinstance(parsed_result, dict):
                fallback_text = _strip_code_fences(normalized_text or ai_response or "")
                phrase_pattern = re.compile(r'"phrase"\s*:\s*"((?:[^"\\\\]|\\\\.)+)"')
                intent_pattern = re.compile(r'"intent"\s*:\s*"((?:[^"\\\\]|\\\\.)+)"')
                phrases_list: list[Dict[str, Any]] = []
                matches = list(phrase_pattern.finditer(fallback_text))
                for idx, match in enumerate(matches):
                    raw_phrase = match.group(1)
                    try:
                        phrase_value = json.loads(f"\"{raw_phrase}\"")
                    except json.JSONDecodeError:
                        phrase_value = raw_phrase
                    chunk_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(fallback_text)
                    chunk = fallback_text[match.end():chunk_end]
                    intent_match = intent_pattern.search(chunk)
                    raw_intent = intent_match.group(1) if intent_match else ""
                    try:
                        intent_value = json.loads(f"\"{raw_intent}\"") if raw_intent else ""
                    except json.JSONDecodeError:
                        intent_value = raw_intent
                    phrases_list.append(
                        {
                            "phrase": phrase_value,
                            "type": "key",
                            "intent": intent_value,
                        }
                    )

                if not phrases_list:
                    for line in fallback_text.splitlines():
                        cleaned = line.strip()
                        cleaned = re.sub(r"^[\s\-–—•\*\d\.\)\(]+", "", cleaned).strip()
                        if not cleaned or len(cleaned) < 3:
                            continue
                        phrases_list.append(
                            {
                                "phrase": cleaned,
                                "type": "key",
                                "intent": "",
                            }
                        )

                if phrases_list:
                    parsed_result = {"phrases": phrases_list}
                    parse_error = None

            if parse_error or not isinstance(parsed_result, dict):
                logger.error("Failed to parse semantic phrases: %s", normalized_text)
                return {
                    "success": False,
                    "error": f"Ошибка разбора JSON: {str(parse_error)}",
                    "raw_response": normalized_text,
                }

            phrases_payload = (
                parsed_result.get("phrases")
                or parsed_result.get("items")
                or parsed_result.get("keywords")
                or parsed_result.get("values")
                or []
            )
            if not isinstance(phrases_payload, list):
                return {
                    "success": False,
                    "error": "AI не вернул список фраз",
                    "raw_response": parsed_result,
                }

            whitespace_re = re.compile(r"\s+")
            seen = set()
            cleaned_phrases: list[Dict[str, Any]] = []
            for item in phrases_payload:
                if isinstance(item, dict):
                    raw_phrase = (
                        item.get("phrase")
                        or item.get("keyword")
                        or item.get("name")
                        or item.get("value")
                        or ""
                    )
                    raw_intent = item.get("intent") or ""
                else:
                    raw_phrase = item
                    raw_intent = ""
                phrase_text = whitespace_re.sub(" ", str(raw_phrase or "").strip())
                if not phrase_text:
                    continue
                key = phrase_text.lower()
                if key in seen:
                    continue
                seen.add(key)
                intent_value = whitespace_re.sub(" ", str(raw_intent or "").strip().lower())
                cleaned_phrases.append(
                    {
                        "phrase": phrase_text,
                        "type": "key",
                        "intent": intent_value,
                    }
                )

            if not cleaned_phrases:
                return {
                    "success": False,
                    "error": "AI вернул пустой список фраз",
                    "raw_response": parsed_result,
                }

            return {
                "success": True,
                "phrases": cleaned_phrases,
                "raw_response": parsed_result,
                "prompt_used": prompt,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating semantic phrases: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def generate_semantic_lsi_from_cluster(
        self,
        *,
        niche: str,
        product: str,
        group_name: str,
        group_description: str = "",
        group_source_books: Optional[list[str]] = None,
        cluster_name: str,
        cluster_description: str = "",
        cluster_main_keyword: str = "",
        cluster_intent: str = "",
        cluster_user_goal: str = "",
        language: str = "ru",
    ) -> Dict[str, Any]:
        """Сформировать список LSI-фраз для кластера."""
        try:
            niche_text = (niche or "").strip() or "не указано"
            product_text = (product or "").strip() or "не указано"
            group_name_text = (group_name or "").strip() or "не указано"
            group_description_text = (group_description or "").strip() or "не указано"
            cluster_name_text = (cluster_name or "").strip() or "не указано"
            cluster_description_text = (cluster_description or "").strip() or "не указано"
            cluster_main_keyword_text = (cluster_main_keyword or "").strip() or "не указано"
            cluster_intent_text = (cluster_intent or "").strip() or "не указано"
            cluster_user_goal_text = (cluster_user_goal or "").strip() or "не указано"

            books_list = group_source_books or []
            cleaned_books = []
            whitespace_re = re.compile(r"\s+")
            for item in books_list:
                value = whitespace_re.sub(" ", str(item or "").strip())
                if value:
                    cleaned_books.append(value)
            books_text = "; ".join(cleaned_books) if cleaned_books else "не указаны"

            prompt = render_generator_prompt(
                "semantic_lsi_from_cluster",
                niche_text=niche_text,
                product_text=product_text,
                group_name=group_name_text,
                group_description=group_description_text,
                group_source_books=books_text,
                cluster_name=cluster_name_text,
                cluster_description=cluster_description_text,
                cluster_main_keyword=cluster_main_keyword_text,
                cluster_intent=cluster_intent_text,
                cluster_user_goal=cluster_user_goal_text,
                language_note="Пиши на русском языке." if language.lower().startswith("ru") else "",
            )
            if not prompt:
                return {"success": False, "error": "Missing generator prompt: semantic_lsi_from_cluster"}

            ai_response = self.get_ai_response(
                prompt,
                max_tokens=2400,
                temperature=0.4,
                response_format={"type": "json_object"},
            )
            if not ai_response:
                return {"success": False, "error": "Не удалось получить ответ от AI"}

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error or not isinstance(parsed_result, dict):
                repaired = self._repair_json_structure(
                    normalized_text,
                    schema_hint="""
{
  "phrases": [
    {
      "phrase": "текст фразы",
      "type": "lsi",
      "category": "term|process|tool|problem|result|comparison|question",
      "comment": "пояснение"
    }
  ]
}
""",
                )
                if repaired and isinstance(repaired, dict):
                    parsed_result = repaired
                    parse_error = None

            if parse_error or not isinstance(parsed_result, dict):
                fallback_text = _strip_code_fences(normalized_text or ai_response or "")
                phrase_pattern = re.compile(r'"phrase"\s*:\s*"((?:[^"\\\\]|\\\\.)+)"')
                phrases_list: list[Dict[str, Any]] = []
                matches = list(phrase_pattern.finditer(fallback_text))
                for match in matches:
                    raw_phrase = match.group(1)
                    try:
                        phrase_value = json.loads(f"\"{raw_phrase}\"")
                    except json.JSONDecodeError:
                        phrase_value = raw_phrase
                    phrases_list.append(
                        {
                            "phrase": phrase_value,
                            "type": "lsi",
                        }
                    )

                if not phrases_list:
                    for line in fallback_text.splitlines():
                        cleaned = line.strip()
                        cleaned = re.sub(r"^[\s\-–—•\*\d\.\)\(]+", "", cleaned).strip()
                        if not cleaned or len(cleaned) < 3:
                            continue
                        phrases_list.append(
                            {
                                "phrase": cleaned,
                                "type": "lsi",
                            }
                        )

                if phrases_list:
                    parsed_result = {"phrases": phrases_list}
                    parse_error = None

            if parse_error or not isinstance(parsed_result, dict):
                logger.error("Failed to parse semantic LSI phrases: %s", normalized_text)
                return {
                    "success": False,
                    "error": f"Ошибка разбора JSON: {str(parse_error)}",
                    "raw_response": normalized_text,
                }

            phrases_payload = (
                parsed_result.get("phrases")
                or parsed_result.get("items")
                or parsed_result.get("keywords")
                or parsed_result.get("values")
                or []
            )
            if not isinstance(phrases_payload, list):
                return {
                    "success": False,
                    "error": "AI не вернул список фраз",
                    "raw_response": parsed_result,
                }

            whitespace_re = re.compile(r"\s+")
            seen = set()
            cleaned_phrases: list[Dict[str, Any]] = []
            for item in phrases_payload:
                if isinstance(item, dict):
                    raw_phrase = (
                        item.get("phrase")
                        or item.get("keyword")
                        or item.get("name")
                        or item.get("value")
                        or ""
                    )
                    raw_category = item.get("category") or ""
                    raw_comment = item.get("comment") or ""
                else:
                    raw_phrase = item
                    raw_category = ""
                    raw_comment = ""
                phrase_text = whitespace_re.sub(" ", str(raw_phrase or "").strip())
                if not phrase_text:
                    continue
                key = phrase_text.lower()
                if key in seen:
                    continue
                seen.add(key)
                cleaned_phrases.append(
                    {
                        "phrase": phrase_text,
                        "type": "lsi",
                        "category": whitespace_re.sub(" ", str(raw_category or "").strip().lower()),
                        "comment": whitespace_re.sub(" ", str(raw_comment or "").strip()),
                    }
                )

            if not cleaned_phrases:
                return {
                    "success": False,
                    "error": "AI вернул пустой список фраз",
                    "raw_response": parsed_result,
                }

            return {
                "success": True,
                "phrases": cleaned_phrases,
                "raw_response": parsed_result,
                "prompt_used": prompt,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating semantic LSI phrases: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def generate_tgstat_tag_recommendations(
        self,
        niche: str,
        product_service: str,
        categories_json: str,
        language: str = "ru",
    ) -> Dict[str, Any]:
        """Подобрать TGStat подкатегории под нишу и продукт."""
        try:
            niche_text = (niche or "").strip() or "не указана"
            product_text = (product_service or "").strip() or "не указан"
            categories_text = (categories_json or "").strip()
            lang_name = "русском" if language == "ru" else "английском"

            prompt = render_generator_prompt(
                "tgstat_recommendations",
                niche_value=niche_text,
                product_value=product_text,
                categories_json=categories_text,
                lang_name=lang_name,
            )
            if not prompt:
                return {"success": False, "error": "Missing generator prompt: tgstat_recommendations"}

            ai_response = self.get_ai_response(
                prompt,
                max_tokens=2000,
                temperature=0.4,
                response_format={"type": "json_object"},
            )
            if not ai_response:
                return {"success": False, "error": "Не удалось получить ответ от AI"}

            parsed_result, normalized_text, parse_error = _parse_ai_json_response(ai_response)
            if parse_error:
                schema_hint = """
{
  "recommendations": [
    {
      "category_slug": "string",
      "category_title": "string",
      "tags": [
        {"slug": "string", "title": "string", "reason": "string"}
      ]
    }
  ]
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

            result = parsed_result or {}
            recommendations = result.get("recommendations")
            if not isinstance(recommendations, list):
                return {
                    "success": False,
                    "error": "AI не вернул список рекомендаций",
                    "raw_response": result,
                }

            return {
                "success": True,
                "recommendations": recommendations,
                "raw_response": result,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating TGStat recommendations: %s", exc, exc_info=True)
            return {
                "success": False,
                "error": str(exc),
            }

    def generate_client_product_from_type(
        self,
        product_type_name: str,
        product_type_value: str = "",
        product_type_goal: str = "",
        *,
        avatar: str = "",
        pains: str = "",
        desires: str = "",
        objections: str = "",
        wordstat_favorites: Optional[List[str]] = None,
        brand: str = "",
        language: str = "ru",
        requirements_override: Optional[Dict[str, Any]] = None,
        additional_context: str = "",
    ) -> Dict[str, Any]:
        """Сгенерировать продукт по типу продукта, настройкам клиента и избранному Wordstat."""
        try:
            lang_name = "русском" if language == "ru" else "английском"
            brand_text = (brand or "").strip() or "без названия"

            type_name = (product_type_name or "").strip() or "Тип продукта"
            type_value = (product_type_value or "").strip()
            type_goal = (product_type_goal or "").strip()

            avatar_text = (avatar or "").strip() or "не описан"
            pains_text = (pains or "").strip() or "не указаны"
            desires_text = (desires or "").strip() or "не указаны"
            objections_text = (objections or "").strip() or "не указаны"

            favorites = []
            for phrase in wordstat_favorites or []:
                if not isinstance(phrase, str):
                    continue
                cleaned = phrase.strip()
                if cleaned and cleaned not in favorites:
                    favorites.append(cleaned)
                if len(favorites) >= 40:
                    break

            favorites_text = "\n".join(f"- {p}" for p in favorites) if favorites else "нет избранных фраз"
            extra_context_text = (additional_context or "").strip()
            extra_context_block = (
                f"\n\nКОНТЕКСТ CORE-ПРОДУКТА (если передан)\n{extra_context_text}"
                if extra_context_text
                else ""
            )

            required_keys = [
                "name",
                "packages",
                "audience",
                "transformation",
                "metrics",
                "method",
                "lesson_format",
                "program_modules",
                "packaging",
            ]

            requirements: Dict[str, Any]

            if isinstance(requirements_override, dict):
                requirements = {
                    key: str(requirements_override.get(key) or "").strip()
                    for key in required_keys
                }
            else:
                requirements_schema_hint = """
{
  "requirements": {
    "name": "Требования к названию и краткому описанию",
    "packages": "Требования к пакетам",
    "audience": "Требования к блоку audience",
    "transformation": "Требования к блоку transformation",
    "metrics": "Требования к блоку metrics",
    "method": "Требования к блоку method",
    "lesson_format": "Требования к блоку lesson_format (формат взаимодействия с клиентом)",
    "program_modules": "Требования к блоку program_modules",
    "packaging": "Требования к блоку packaging"
  }
}
"""

                requirements_prompt = render_generator_prompt(
                    "product_requirements_prompt",
                    brand_text=brand_text,
                    type_name=type_name,
                    type_value=type_value or "не указана",
                    type_goal=type_goal or "не указана",
                    avatar_text=avatar_text,
                    pains_text=pains_text,
                    desires_text=desires_text,
                    objections_text=objections_text,
                    favorites_text=favorites_text,
                    extra_context_block=extra_context_block,
                    lang_name=lang_name,
                    requirements_schema_hint=requirements_schema_hint,
                )
                if not requirements_prompt:
                    return {"success": False, "error": "Missing generator prompt: product_requirements_prompt"}

                req_raw = self.get_ai_response(
                    requirements_prompt,
                    max_tokens=1600,
                    temperature=0.25,
                    response_format={"type": "json_object"},
                )
                if not req_raw:
                    return {"success": False, "error": "Не удалось получить требования от AI"}

                req_parsed, req_text, req_err = _parse_ai_json_response(req_raw)
                if req_err or not isinstance(req_parsed, dict):
                    repaired = self._repair_json_structure(req_text, schema_hint=requirements_schema_hint)
                    if repaired and isinstance(repaired, dict):
                        req_parsed = repaired
                        req_err = None
                if req_err or not isinstance(req_parsed, dict):
                    return {
                        "success": False,
                        "error": f"Ошибка разбора JSON (requirements): {str(req_err) if req_err else 'invalid response'}",
                        "raw_response": req_text,
                    }

                requirements = req_parsed.get("requirements")
                if not isinstance(requirements, dict):
                    return {
                        "success": False,
                        "error": "AI не вернул requirements",
                        "raw_response": req_parsed,
                    }

            for key in required_keys:
                if not isinstance(requirements.get(key), str) or not str(requirements.get(key)).strip():
                    requirements[key] = f"Сгенерируй блок '{key}' строго под тип продукта '{type_name}' для аудитории: {avatar_text}."

            common_context = f"""
КОНТЕКСТ
- Бренд: {brand_text}
- Тип продукта: {type_name}
- Ценность типа: {type_value or "не указана"}
- Цель типа: {type_goal or "не указана"}
- Портрет ЦА: {avatar_text}
- Боли: {pains_text}
- Желания: {desires_text}
- Возражения: {objections_text}
WORDSTAT (избранное):
{favorites_text}
{extra_context_block}
"""

            def _generate_block(requirement_key: str, requirement_text: str, schema_hint: str, max_tokens: int = 900) -> Dict[str, Any]:
                prompt = render_generator_prompt(
                    "product_block_prompt",
                    requirement_key=requirement_key,
                    common_context=common_context,
                    requirement_text=requirement_text,
                    lang_name=lang_name,
                    schema_hint=schema_hint,
                )
                if not prompt:
                    return {"success": False, "error": "Missing generator prompt: product_block_prompt"}
                raw = self.get_ai_response(
                    prompt,
                    max_tokens=max_tokens,
                    temperature=0.35,
                    response_format={"type": "json_object"},
                )
                if not raw:
                    return {"success": False, "error": f"Не удалось получить блок {requirement_key} от AI"}
                parsed, normalized_text, parse_error = _parse_ai_json_response(raw)
                if parse_error or not isinstance(parsed, dict):
                    repaired = self._repair_json_structure(normalized_text, schema_hint=schema_hint)
                    if repaired and isinstance(repaired, dict):
                        parsed = repaired
                        parse_error = None
                if parse_error or not isinstance(parsed, dict):
                    return {
                        "success": False,
                        "error": f"Ошибка разбора JSON ({requirement_key}): {str(parse_error) if parse_error else 'invalid response'}",
                        "raw_response": normalized_text,
                    }
                return {"success": True, "data": parsed}

            schemas = {
                "name": """
{
  "name": "string",
  "short_description": "string",
  "phrases_used": ["string"]
}
""",
                "packages": """
{
  "packages": [
    { "name": "string", "description": "string", "price": null }
  ],
  "phrases_used": ["string"]
}
""",
                "audience": """
{
  "audience": [{ "parameter": "string", "value": "string" }],
  "phrases_used": ["string"]
}
""",
                "transformation": """
{
  "transformation": [{ "was": "string", "became": "string" }],
  "phrases_used": ["string"]
}
""",
                "metrics": """
{
  "metrics": [{ "metric": "string", "promise": "string" }],
  "phrases_used": ["string"]
}
""",
                "method": """
{
  "method": [{ "component": "string", "template": "string" }],
  "phrases_used": ["string"]
}
""",
                "lesson_format": """
{
  "lesson_format": [{ "stage": "string", "percent": 0 }],
  "phrases_used": ["string"]
}
""",
                "program_modules": """
{
  "program_modules": [{ "module": "string", "result": "string" }],
  "phrases_used": ["string"]
}
""",
                "packaging": """
{
  "packaging": { "name": "string", "slogan": "string", "promise": "string" },
  "phrases_used": ["string"]
}
""",
            }

            blocks_raw: Dict[str, Any] = {"requirements": requirements}
            phrases_used_all: List[str] = []

            def _merge_phrases(value: Any) -> None:
                if not isinstance(value, list):
                    return
                for item in value:
                    text_value = str(item or "").strip()
                    if text_value and text_value not in phrases_used_all:
                        phrases_used_all.append(text_value)

            block_results: Dict[str, Any] = {}
            for key in required_keys:
                res = _generate_block(key, str(requirements.get(key) or ""), schemas[key])
                if not res.get("success"):
                    res["requirements"] = requirements
                    raw = res.get("raw_response")
                    if raw is not None:
                        res["raw_response"] = {
                            "requirements": requirements,
                            "failed_block": key,
                            "block_raw_response": raw,
                        }
                    return res
                data = res.get("data") or {}
                block_results[key] = data
                _merge_phrases(data.get("phrases_used"))

            name_payload = block_results["name"]
            product_name = str(name_payload.get("name") or "").strip() or type_name
            short_description = str(name_payload.get("short_description") or "").strip()
            if not short_description:
                short_description = f"{type_name}: продукт для аудитории {avatar_text}"
            prefix = f"{type_name}:"
            if not short_description.lower().startswith(prefix.lower()):
                short_description = f"{prefix} {short_description}".strip()

            def _normalize_packages(value: Any) -> List[Dict[str, Any]]:
                if not isinstance(value, list):
                    return []
                cleaned: List[Dict[str, Any]] = []
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    pkg_name = str(item.get("name") or "").strip()
                    if not pkg_name:
                        continue
                    pkg_desc = str(item.get("description") or "").strip() or None
                    raw_price = item.get("price")
                    price = None
                    if isinstance(raw_price, (int, float)):
                        price = float(raw_price)
                    cleaned.append({"name": pkg_name, "description": pkg_desc, "price": price})
                return cleaned

            def _normalize_lesson_format(value: Any) -> List[Dict[str, Any]]:
                if not isinstance(value, list):
                    return []
                cleaned: List[Dict[str, Any]] = []
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    stage = str(item.get("stage") or "").strip()
                    percent_raw = item.get("percent")
                    percent = None
                    if isinstance(percent_raw, (int, float)):
                        percent = float(percent_raw)
                    elif isinstance(percent_raw, str):
                        try:
                            percent = float(percent_raw.replace(",", "."))
                        except ValueError:
                            percent = None
                    cleaned.append({"stage": stage, "percent": percent})
                return cleaned

            structure: Dict[str, Any] = {
                "audience": block_results["audience"].get("audience") if isinstance(block_results["audience"].get("audience"), list) else [],
                "transformation": block_results["transformation"].get("transformation") if isinstance(block_results["transformation"].get("transformation"), list) else [],
                "metrics": block_results["metrics"].get("metrics") if isinstance(block_results["metrics"].get("metrics"), list) else [],
                "method": block_results["method"].get("method") if isinstance(block_results["method"].get("method"), list) else [],
                "lesson_format": _normalize_lesson_format(block_results["lesson_format"].get("lesson_format")),
                "program_modules": block_results["program_modules"].get("program_modules") if isinstance(block_results["program_modules"].get("program_modules"), list) else [],
                "packaging": block_results["packaging"].get("packaging") if isinstance(block_results["packaging"].get("packaging"), dict) else {},
            }

            packages = _normalize_packages(block_results["packages"].get("packages"))

            blocks_raw["blocks"] = block_results

            return {
                "success": True,
                "requirements": requirements,
                "product": {
                    "name": product_name,
                    "short_description": short_description,
                    "packages": packages,
                    "structure": structure,
                },
                "phrases_used": phrases_used_all[:20],
                "raw_response": blocks_raw,
            }

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error generating client product: %s", exc, exc_info=True)
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

            prompt = render_generator_prompt(
                "story_episodes_prompt",
                episode_count=episode_count,
                lang_name=lang_name,
                topic_name=topic_name,
                trend_title=trend_title,
                trend_description=trend_description,
                client_desires=client_desires,
            )
            if not prompt:
                return {"success": False, "error": "Missing generator prompt: story_episodes_prompt"}

            logger.info("Генерация истории на основе тренда: %s", trend_title[:50])

            original_model = self.model
            self.model = "tngtech/tng-r1t-chimera:free"

            try:
                ai_response = self.get_ai_response(
                    prompt,
                    max_tokens=2000,
                    temperature=0.8,
                    response_format={"type": "json_object"},
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

                if "title" not in result or "episodes" not in result:
                    schema_hint = """
{
  "title": "string, общий заголовок истории",
  "episodes": [
    {"order": 1, "title": "Заголовок эпизода 1"},
    {"order": 2, "title": "Заголовок эпизода 2"}
  ]
}
"""
                    repaired_result = self._repair_json_structure(normalized_text, schema_hint)
                    if (
                        repaired_result
                        and "title" in repaired_result
                        and "episodes" in repaired_result
                    ):
                        result = repaired_result
                    else:
                        logger.error("Invalid AI response structure: %s", normalized_text)
                        return {
                            "success": False,
                            "error": "Invalid response structure from AI",
                            "raw_response": normalized_text,
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
            length = template_config.get("length", 1200)
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

            tone_ru = tone_map.get(tone, tone)
            length_ru = _format_length_value(length)
            lang_name = "русском" if language == "ru" else "английском"

            if episode_number == 1:
                episode_extra_line = render_generator_prompt("story_post_episode_first_line")
            elif episode_number == total_episodes:
                episode_extra_line = render_generator_prompt("story_post_episode_last_line")
            else:
                episode_extra_line = render_generator_prompt("story_post_episode_middle_line")

            hashtags_block = ""
            if include_hashtags:
                hashtags_block = render_generator_prompt(
                    "post_text_hashtags_block",
                    max_hashtags=max_hashtags,
                )

            additional_block = ""
            if additional_instructions:
                additional_block = render_generator_prompt(
                    "post_text_additional_block",
                    additional_instructions=additional_instructions,
                )

            response_format_block = render_generator_prompt("post_text_response_format_block")

            prompt = render_generator_prompt(
                "story_post_from_episode_prompt",
                length_ru=length_ru,
                tone_ru=tone_ru,
                lang_name=lang_name,
                story_title=story_title,
                episode_number=episode_number,
                total_episodes=total_episodes,
                episode_title=episode_title,
                topic_name=topic_name,
                avatar=avatar,
                pains=pains,
                desires=desires,
                objections=objections,
                episode_extra_line=episode_extra_line,
                hashtags_block=hashtags_block,
                additional_block=additional_block,
                response_format_block=response_format_block,
            )
            if not prompt:
                return {
                    "success": False,
                    "error": "Missing generator prompt: story_post_from_episode_prompt",
                }

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
                response_format={"type": "json_object"},
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
                schema_hint = """
{
  "title": "string, заголовок поста",
  "text": "string, основной текст поста",
  "hashtags": ["string", ...]
}
"""
                repaired_result = self._repair_json_structure(normalized_text, schema_hint)
                if repaired_result and "title" in repaired_result and "text" in repaired_result:
                    result = repaired_result
                else:
                    logger.error("Invalid AI response structure: %s", normalized_text)
                    return {
                        "success": False,
                        "error": "Invalid response structure from AI",
                        "raw_response": normalized_text,
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
