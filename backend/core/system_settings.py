import logging

from django.core.cache import cache

from .models import SystemSetting

logger = logging.getLogger(__name__)

DEFAULT_AI_MODEL_CACHE_KEY = "core:default_ai_model"
DEFAULT_AI_MODEL_CACHE_TIMEOUT = 60  # seconds


def _fetch_default_ai_model_from_db() -> str:
    try:
        setting = SystemSetting.get_solo()
        return setting.default_ai_model or SystemSetting.DEFAULT_AI_MODEL
    except Exception as exc:
        logger.warning("Failed to load SystemSetting: %s", exc)
        return SystemSetting.DEFAULT_AI_MODEL


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


def invalidate_system_settings_cache():
    cache.delete(DEFAULT_AI_MODEL_CACHE_KEY)
