import json
import logging
import re
from typing import Dict, Optional

from .ai_generator import AIContentGenerator

logger = logging.getLogger(__name__)

AUDIENCE_FIELDS = ("avatar", "pains", "desires", "objections")
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)
_LINE_NORMALIZER = re.compile(r"\s+")
_MAX_FIELD_LENGTH = 2000


def _clean_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) > _MAX_FIELD_LENGTH:
        text = text[:_MAX_FIELD_LENGTH]
    return text.strip()


def _normalize_profile(data: Optional[Dict[str, str]]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    source = data if isinstance(data, dict) else {}
    for field in AUDIENCE_FIELDS:
        normalized[field] = _clean_value(source.get(field)) if hasattr(source, "get") else ""
    return normalized


def _parse_ai_json(raw_response: Optional[str]) -> Optional[Dict[str, str]]:
    if not raw_response:
        return None

    candidates: list[str] = []

    def _add_candidate(text: Optional[str]):
        candidate = (text or "").strip()
        if not candidate:
            return
        if candidate not in candidates:
            candidates.append(candidate)

    _add_candidate(raw_response)
    for block in _CODE_BLOCK_RE.findall(raw_response):
        _add_candidate(block)

    for candidate in candidates:
        match = _JSON_RE.search(candidate)
        payload = match.group(0) if match else candidate
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return {field: data.get(field, "") for field in AUDIENCE_FIELDS}
    return None


def _merge_field_text(current: str, addition: str) -> str:
    current_clean = current.strip()
    addition_clean = addition.strip()

    if not current_clean:
        return addition_clean
    if not addition_clean:
        return current_clean

    existing_lines = [
        _LINE_NORMALIZER.sub(" ", line.strip().lower())
        for line in current_clean.splitlines()
        if line.strip()
    ]
    existing_set = set(existing_lines)
    new_parts: list[str] = []
    for line in addition_clean.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        normalized = _LINE_NORMALIZER.sub(" ", candidate.lower())
        if normalized in existing_set:
            continue
        existing_set.add(normalized)
        new_parts.append(candidate)

    if not new_parts:
        return current_clean

    return f"{current_clean}\n\n" + "\n".join(new_parts)


def _format_profile_for_prompt(title: str, profile: Dict[str, str]) -> str:
    labels = {
        "avatar": "Аватар",
        "pains": "Боли",
        "desires": "Хотелки",
        "objections": "Возражения",
    }
    lines = [title]
    for key in AUDIENCE_FIELDS:
        value = profile.get(key) or "—"
        lines.append(f"{labels[key]}: {value}")
    return "\n".join(lines)


def _merge_with_ai(existing: Dict[str, str], addition: Dict[str, str]) -> Optional[Dict[str, str]]:
    try:
        generator = AIContentGenerator()
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("Не удалось инициализировать AI генератор: %s", exc)
        return None

    prompt = f"""Ты — маркетинговый аналитик. Тебе даны два описания одной и той же целевой аудитории:
1) Текущий профиль клиента (основан на предыдущих исследованиях)
2) Новые наблюдения из анализа конкретного канала

Нужно обновить профиль клиента, объединив данные и устранив повторы. Для каждого блока (avatar, pains, desires, objections):
- сохрани всё ценное из текущего профиля
- добавь только новые мысли из канала, избегая дублирования формулировок
- пиши на русском языке, оформляя текст короткими абзацами или пунктами, разделёнными переносами строк
- если в новых данных поле пустое, просто верни существующий текст
- при сомнениях лучше оставить обе формулировки, но не копируй одинаковые предложения

Верни ЧИСТЫЙ JSON строго следующей структуры:
{{
  "avatar": "обновлённое описание аудитории",
  "pains": "обновлённый список болей",
  "desires": "обновлённый список хотелок",
  "objections": "обновлённый список возражений"
}}

{_format_profile_for_prompt("Текущий профиль клиента:", existing)}

{_format_profile_for_prompt("Новые данные из канала:", addition)}
"""

    response = generator.get_ai_response(prompt, max_tokens=900, temperature=0.35)
    parsed = _parse_ai_json(response)
    if not parsed:
        logger.warning("AI не вернула корректный JSON при объединении профиля. Ответ: %s", response)
        return None

    normalized = _normalize_profile(parsed)
    result: Dict[str, str] = {}
    for key in AUDIENCE_FIELDS:
        result[key] = normalized.get(key) or existing.get(key) or addition.get(key) or ""
    return result


def merge_audience_profiles(existing_data: Optional[Dict[str, str]], new_data: Optional[Dict[str, str]]) -> Dict[str, str]:
    """
    Объединить описание целевой аудитории клиента с новыми данными из анализа канала.
    AI пытается убрать дубликаты и добавить только недостающие мысли.
    В случае ошибки используется наивное объединение по строкам.
    """

    existing = _normalize_profile(existing_data)
    addition = _normalize_profile(new_data)

    if not any(addition.values()):
        return existing
    if not any(existing.values()):
        return addition

    ai_result = _merge_with_ai(existing, addition)
    if ai_result:
        return ai_result

    logger.info("Используем резервное объединение профиля аудитории без AI")
    fallback: Dict[str, str] = {}
    for key in AUDIENCE_FIELDS:
        fallback[key] = _merge_field_text(existing.get(key, ""), addition.get(key, ""))
    return fallback
