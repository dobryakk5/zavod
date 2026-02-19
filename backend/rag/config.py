from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from django.conf import settings


def _get_setting_value(key: str, default: Any) -> Any:
    cfg = getattr(settings, "RAG_CONFIG", {})
    if key in cfg and cfg[key] is not None:
        return cfg[key]
    return os.getenv(f"RAG_{key}", default)


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


BASE_DIR = Path(getattr(settings, "BASE_DIR", Path(__file__).resolve().parents[1]))


class RagConfig:
    # RAG_E5* is used only for embedding generation.
    e5_model_path = str(
        _get_setting_value(
            "E5_MODEL_PATH",
            str(BASE_DIR / "models" / "multilingual-e5-small"),
        )
    )
    chunk_size = _as_int(_get_setting_value("CHUNK_SIZE", 512), 512)
    chunk_overlap = _as_int(_get_setting_value("CHUNK_OVERLAP", 64), 64)
    top_k = _as_int(_get_setting_value("TOP_K", 10), 10)
    rrf_k = _as_int(_get_setting_value("RRF_K", 60), 60)
    ts_language = str(_get_setting_value("TS_LANGUAGE", "russian"))

    context_enabled = _as_bool(_get_setting_value("CONTEXT_ENABLED", True), True)
    context_concurrency = _as_int(_get_setting_value("CONTEXT_CONCURRENCY", 4), 4)
    context_max_tokens = _as_int(_get_setting_value("CONTEXT_MAX_TOKENS", 300), 300)
    context_temperature = _as_float(_get_setting_value("CONTEXT_TEMPERATURE", 0.0), 0.0)
    context_timeout_seconds = _as_float(
        _get_setting_value("CONTEXT_TIMEOUT_SECONDS", 120.0),
        120.0,
    )


config = RagConfig()

