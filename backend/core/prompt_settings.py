import logging
from string import Template
from typing import Optional

from django.core.cache import cache

from .models import GeneratorPrompt
from .system_settings import DEFAULT_AI_MODEL_CACHE_TIMEOUT

logger = logging.getLogger(__name__)

PROMPT_CACHE_PREFIX = "core:generator_prompt:"


def get_generator_prompt(code: str, use_cache: bool = True) -> str:
    if not code:
        return ""
    cache_key = f"{PROMPT_CACHE_PREFIX}{code}"
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    try:
        prompt = (
            GeneratorPrompt.objects.filter(code=code)
            .values_list("prompt", flat=True)
            .first()
        )
    except Exception as exc:
        logger.warning("Failed to load generator prompt %s: %s", code, exc)
        prompt = ""

    prompt = (prompt or "").strip()
    if use_cache:
        cache.set(cache_key, prompt, DEFAULT_AI_MODEL_CACHE_TIMEOUT)
    return prompt


def render_generator_prompt(code: str, use_cache: bool = True, **kwargs: str) -> str:
    template = get_generator_prompt(code, use_cache=use_cache)
    if not template:
        logger.error("Generator prompt '%s' is missing", code)
        return ""
    try:
        return Template(template).safe_substitute(**kwargs)
    except ValueError as exc:
        logger.error("Failed to render generator prompt '%s': %s", code, exc)
        return template


def invalidate_generator_prompt_cache(code: Optional[str] = None) -> None:
    if code:
        cache.delete(f"{PROMPT_CACHE_PREFIX}{code}")
