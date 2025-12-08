import logging

from django.core.cache import cache

from .models import SystemSetting

logger = logging.getLogger(__name__)

DEFAULT_AI_MODEL_CACHE_KEY = "core:default_ai_model"
FALLBACK_AI_MODEL_CACHE_KEY = "core:fallback_ai_model"
VIDEO_PROMPT_INSTRUCTIONS_CACHE_KEY = "core:video_prompt_instructions"
IMAGE_TIMEOUT_CACHE_KEY = "core:image_generation_timeout"
VIDEO_TIMEOUT_CACHE_KEY = "core:video_generation_timeout"
DEFAULT_AI_MODEL_CACHE_TIMEOUT = 60  # seconds


def _fetch_default_ai_model_from_db() -> str:
    try:
        setting = SystemSetting.get_solo()
        return setting.default_ai_model or SystemSetting.DEFAULT_AI_MODEL
    except Exception as exc:
        logger.warning("Failed to load SystemSetting: %s", exc)
        return SystemSetting.DEFAULT_AI_MODEL


def _fetch_fallback_ai_model_from_db() -> str:
    try:
        setting = SystemSetting.get_solo()
        return setting.fallback_ai_model or SystemSetting.DEFAULT_FALLBACK_AI_MODEL
    except Exception as exc:
        logger.warning("Failed to load SystemSetting fallback: %s", exc)
        return SystemSetting.DEFAULT_FALLBACK_AI_MODEL


def _fetch_video_prompt_instructions_from_db() -> str:
    try:
        setting = SystemSetting.get_solo()
        return (setting.video_prompt_instructions or "").strip()
    except Exception as exc:
        logger.warning("Failed to load SystemSetting: %s", exc)
        return ""


def _fetch_image_generation_timeout_from_db() -> int:
    try:
        setting = SystemSetting.get_solo()
        timeout = setting.image_generation_timeout or SystemSetting.DEFAULT_IMAGE_TIMEOUT
        return max(5, int(timeout))
    except Exception as exc:
        logger.warning("Failed to load SystemSetting: %s", exc)
        return SystemSetting.DEFAULT_IMAGE_TIMEOUT


def _fetch_video_generation_timeout_from_db() -> int:
    try:
        setting = SystemSetting.get_solo()
        timeout = setting.video_generation_timeout or SystemSetting.DEFAULT_VIDEO_TIMEOUT
        return max(30, int(timeout))
    except Exception as exc:
        logger.warning("Failed to load SystemSetting: %s", exc)
        return SystemSetting.DEFAULT_VIDEO_TIMEOUT


def get_default_ai_model(use_cache: bool = True) -> str:
    """Return default AI model string with optional cache usage."""
    if use_cache:
        cached = cache.get(DEFAULT_AI_MODEL_CACHE_KEY)
        if cached:
            return cached

    model_name = _fetch_default_ai_model_from_db()

    if use_cache:
        cache.set(DEFAULT_AI_MODEL_CACHE_KEY, model_name, DEFAULT_AI_MODEL_CACHE_TIMEOUT)

    return model_name


def get_fallback_ai_model(use_cache: bool = True) -> str:
    """Return fallback AI model string with optional cache usage."""
    if use_cache:
        cached = cache.get(FALLBACK_AI_MODEL_CACHE_KEY)
        if cached:
            return cached

    model_name = _fetch_fallback_ai_model_from_db()

    if use_cache:
        cache.set(FALLBACK_AI_MODEL_CACHE_KEY, model_name, DEFAULT_AI_MODEL_CACHE_TIMEOUT)

    return model_name


def get_video_prompt_instructions(use_cache: bool = True) -> str:
    """Return additional instructions for video prompts."""
    if use_cache:
        cached = cache.get(VIDEO_PROMPT_INSTRUCTIONS_CACHE_KEY)
        if cached is not None:
            return cached

    instructions = _fetch_video_prompt_instructions_from_db()
    if use_cache:
        cache.set(VIDEO_PROMPT_INSTRUCTIONS_CACHE_KEY, instructions, DEFAULT_AI_MODEL_CACHE_TIMEOUT)
    return instructions


def get_image_generation_timeout(use_cache: bool = True) -> int:
    """Return timeout (seconds) for image generation workflows."""
    if use_cache:
        cached = cache.get(IMAGE_TIMEOUT_CACHE_KEY)
        if cached is not None:
            return cached
    timeout = _fetch_image_generation_timeout_from_db()
    if use_cache:
        cache.set(IMAGE_TIMEOUT_CACHE_KEY, timeout, DEFAULT_AI_MODEL_CACHE_TIMEOUT)
    return timeout


def get_video_generation_timeout(use_cache: bool = True) -> int:
    """Return timeout (seconds) for video generation workflows."""
    if use_cache:
        cached = cache.get(VIDEO_TIMEOUT_CACHE_KEY)
        if cached is not None:
            return cached
    timeout = _fetch_video_generation_timeout_from_db()
    if use_cache:
        cache.set(VIDEO_TIMEOUT_CACHE_KEY, timeout, DEFAULT_AI_MODEL_CACHE_TIMEOUT)
    return timeout


def invalidate_system_settings_cache():
    cache.delete(DEFAULT_AI_MODEL_CACHE_KEY)
    cache.delete(FALLBACK_AI_MODEL_CACHE_KEY)
    cache.delete(VIDEO_PROMPT_INSTRUCTIONS_CACHE_KEY)
    cache.delete(IMAGE_TIMEOUT_CACHE_KEY)
    cache.delete(VIDEO_TIMEOUT_CACHE_KEY)
