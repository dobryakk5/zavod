"""Shared base logic for AI content generator."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import List, Optional

import requests

from .openrouter_utils import build_openrouter_headers
from .system_settings import (
    get_default_ai_model,
    get_post_ai_model,
    get_fallback_ai_model,
)

try:
    from huggingface_hub import InferenceClient

    HF_HUB_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    HF_HUB_AVAILABLE = False
    InferenceClient = None  # type: ignore

logger = logging.getLogger("backend.core.ai_generator")


def _openrouter_debug_enabled() -> bool:
    flag = (os.getenv("OPENROUTER_DEBUG") or "1").strip().lower()
    return flag in {"1", "true", "yes", "on"}


if _openrouter_debug_enabled():
    logger.setLevel(logging.DEBUG)
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_ANSWER_BLOCK_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL | re.IGNORECASE)
_OPENROUTER_RETRYABLE_STATUS = {500, 502, 503, 504}


def _coerce_text(value: object, *, strip: bool = True) -> str:
    if isinstance(value, str):
        return value.strip() if strip else value
    if isinstance(value, dict):
        for key in ("text", "content", "value"):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip() if strip else candidate
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            text = _coerce_text(item, strip=strip)
            if text:
                parts.append(text)
        joined = "\n".join(parts)
        return joined.strip() if strip else joined
    return ""


def _iter_openrouter_candidate_texts(data: object) -> List[str]:
    if not isinstance(data, dict):
        return []
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return []

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return []

    candidates: List[str] = []
    message = first_choice.get("message")
    if isinstance(message, dict):
        candidates.append(_coerce_text(message.get("content")))
        candidates.append(_coerce_text(message.get("text")))
        candidates.append(_coerce_text(message.get("reasoning")))
        candidates.append(_coerce_text(message.get("reasoning_details")))
    else:
        candidates.append(_coerce_text(message))

    delta = first_choice.get("delta")
    if isinstance(delta, dict):
        candidates.append(_coerce_text(delta.get("content")))

    candidates.append(_coerce_text(first_choice.get("text")))

    return [item for item in candidates if item]


def _extract_json_payload(text: str) -> str:
    if not text:
        return ""
    text = _THINK_BLOCK_RE.sub("", text).strip()
    answer_match = _ANSWER_BLOCK_RE.search(text)
    if answer_match:
        candidate = (answer_match.group(1) or "").strip()
        if candidate:
            return candidate
    match = _JSON_BLOCK_RE.search(text)
    if match:
        candidate = (match.group(1) or "").strip()
        if candidate:
            return candidate
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        return stripped
    start_obj = stripped.find("{")
    end_obj = stripped.rfind("}")
    if start_obj != -1 and end_obj > start_obj:
        return stripped[start_obj : end_obj + 1].strip()
    start_arr = stripped.find("[")
    end_arr = stripped.rfind("]")
    if start_arr != -1 and end_arr > start_arr:
        return stripped[start_arr : end_arr + 1].strip()
    return ""


def _extract_openrouter_json(data: object) -> Optional[str]:
    for candidate in _iter_openrouter_candidate_texts(data):
        extracted = _extract_json_payload(candidate)
        if extracted:
            return extracted
    return None


def _extract_openrouter_stream_parts(data: object) -> tuple[str, str]:
    if not isinstance(data, dict):
        return "", ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return "", ""

    content_piece = ""
    reasoning_piece = ""

    delta = first_choice.get("delta")
    if isinstance(delta, dict):
        content_piece = _coerce_text(delta.get("content"), strip=False) or _coerce_text(delta.get("text"), strip=False)
        reasoning_piece = _coerce_text(delta.get("reasoning"), strip=False) or _coerce_text(
            delta.get("reasoning_details"),
            strip=False,
        )

    message = first_choice.get("message")
    if isinstance(message, dict):
        if not content_piece:
            content_piece = _coerce_text(message.get("content"), strip=False) or _coerce_text(
                message.get("text"),
                strip=False,
            )
        if not reasoning_piece:
            reasoning_piece = _coerce_text(message.get("reasoning"), strip=False) or _coerce_text(
                message.get("reasoning_details"),
                strip=False,
            )

    text_value = first_choice.get("text")
    if not content_piece and isinstance(text_value, str) and text_value:
        content_piece = text_value

    return content_piece, reasoning_piece


def _extract_openrouter_stream_text(data: object, *, include_reasoning: bool = True) -> str:
    content_piece, reasoning_piece = _extract_openrouter_stream_parts(data)
    if content_piece:
        return content_piece
    if reasoning_piece and include_reasoning:
        cleaned = _THINK_BLOCK_RE.sub("", reasoning_piece).strip()
        return cleaned
    return ""


def _extract_openrouter_text(data: object) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None
    choice_error = first_choice.get("error")
    if isinstance(choice_error, dict):
        message = choice_error.get("message")
        code = choice_error.get("code")
        logger.warning("OpenRouter choice error (code=%s): %s", code, message)
        return None

    message = first_choice.get("message")
    if isinstance(message, dict):
        content_text = _coerce_text(message.get("content"))
        if content_text:
            cleaned = _THINK_BLOCK_RE.sub("", content_text).strip()
            if cleaned:
                return cleaned
        message_text = _coerce_text(message.get("text"))
        if message_text:
            return message_text
        reasoning_text = _coerce_text(message.get("reasoning"))
        if reasoning_text:
            cleaned = _THINK_BLOCK_RE.sub("", reasoning_text).strip()
            if cleaned:
                return cleaned
        reasoning_details_text = _coerce_text(message.get("reasoning_details"))
        if reasoning_details_text:
            cleaned = _THINK_BLOCK_RE.sub("", reasoning_details_text).strip()
            if cleaned:
                return cleaned
    else:
        message_text = _coerce_text(message)
        if message_text:
            return message_text

    delta = first_choice.get("delta")
    if isinstance(delta, dict):
        delta_text = _coerce_text(delta.get("content"))
        if delta_text:
            return delta_text

    choice_text = _coerce_text(first_choice.get("text"))
    if choice_text:
        return choice_text

    return None


def _should_dump_openrouter_debug() -> bool:
    return False


def _dump_openrouter_payload(data: object, model: str, tag: str) -> Optional[Path]:
    return None


def _get_openrouter_max_retries() -> int:
    try:
        return max(0, int(os.getenv("OPENROUTER_MAX_RETRIES", "2")))
    except (TypeError, ValueError):
        return 2


def _compute_backoff(attempt: int, base: float = 1.0, cap: float = 6.0) -> float:
    return min(base * (2 ** attempt), cap)


def _compute_retry_delay(response: requests.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after and retry_after.isdigit():
        return min(float(retry_after), 10.0)
    return _compute_backoff(attempt)


def _should_retry_on_429() -> bool:
    flag = (os.getenv("OPENROUTER_RETRY_ON_429") or "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


class BaseAIContentGenerator:
    """Transport helpers and API configuration shared by specialized mixins."""

    api_url = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")

        self.model = get_default_ai_model()
        self.post_model = get_post_ai_model()
        self.fallback_model = get_fallback_ai_model()

        self.hf_client = None
        if HF_HUB_AVAILABLE:
            hf_token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
            if hf_token:
                try:
                    self.hf_client = InferenceClient(
                        provider="nebius",
                        api_key=hf_token,  # type: ignore[arg-type]
                    )
                    logger.debug("HuggingFace Nebius client initialized successfully")
                except Exception as exc:  # pragma: no cover - log only
                    logger.warning("Failed to initialize HuggingFace client: %s", exc)
            else:
                logger.debug(
                    "HuggingFace token not found, HF image generation will be unavailable"
                )

    def _call_openrouter(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        response_format: Optional[dict] = None,
        plugins: Optional[List[dict]] = None,
        stream: bool = False,
        stop: Optional[List[str]] = None,
        extra_body: Optional[dict] = None,
        timeout_seconds: float = 60.0,
    ) -> Optional[str]:
        """Call OpenRouter chat completions API and return text."""
        effective_max_tokens = max_tokens
        model_lower = (model or "").lower()
        is_reasoning_model = any(
            keyword in model_lower for keyword in ("r1", "reasoning", "deepseek-r", "qwq")
        )
        if is_reasoning_model and max_tokens < 4000:
            effective_max_tokens = max(max_tokens * 2, 4000)
            logger.debug(
                "Increased max_tokens from %s to %s for reasoning model %s",
                max_tokens,
                effective_max_tokens,
                model,
            )
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "max_tokens": effective_max_tokens,
            "temperature": temperature,
        }

        if response_format:
            payload["response_format"] = response_format
        if plugins:
            payload["plugins"] = plugins
        if stream:
            payload["stream"] = True
        if stop:
            payload["stop"] = stop
        if extra_body:
            payload.update(extra_body)

        max_retries = _get_openrouter_max_retries()
        attempt = 0
        while True:
            try:
                response = requests.post(
                    self.api_url,
                    headers=build_openrouter_headers(
                        self.api_key,
                        default_title="Content Factory AI Generator",
                    ),
                    json=payload,
                    timeout=timeout_seconds,
                    stream=stream,
                )
                if stream:
                    response.encoding = "utf-8"
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                if attempt < max_retries:
                    delay = _compute_backoff(attempt)
                    logger.warning(
                        "OpenRouter request failed for model %s (attempt %s/%s): %s. Retrying in %.1fs",
                        model,
                        attempt + 1,
                        max_retries + 1,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue
                logger.error("OpenRouter API request failed for model %s: %s", model, exc)
                return None
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.error(
                    "Error calling OpenRouter API for model %s: %s",
                    model,
                    exc,
                    exc_info=True,
                )
                return None

            if response.status_code == 429 and _should_retry_on_429() and attempt < max_retries:
                delay = _compute_retry_delay(response, attempt)
                logger.warning(
                    "OpenRouter API rate-limited for model %s (attempt %s/%s). Retrying in %.1fs",
                    model,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                time.sleep(delay)
                attempt += 1
                continue

            if response.status_code in _OPENROUTER_RETRYABLE_STATUS and attempt < max_retries:
                delay = _compute_retry_delay(response, attempt)
                logger.warning(
                    "OpenRouter API error %s for model %s (attempt %s/%s). Retrying in %.1fs",
                    response.status_code,
                    model,
                    attempt + 1,
                    max_retries + 1,
                    delay,
                )
                time.sleep(delay)
                attempt += 1
                continue

            if response.status_code == 200:
                if stream:
                    content_parts: List[str] = []
                    reasoning_parts: List[str] = []
                    last_log_time = time.monotonic()
                    last_log_content_len = 0
                    last_log_reasoning_len = 0
                    stream_start = time.monotonic()
                    finish_reason: Optional[str] = None
                    try:
                        for raw_line in response.iter_lines(decode_unicode=True):
                            if time.monotonic() - stream_start >= timeout_seconds:
                                logger.warning(
                                    "OpenRouter stream timeout (%.1fs) for model %s",
                                    timeout_seconds,
                                    model,
                                )
                                break
                            if not raw_line:
                                continue
                            line = raw_line.strip()
                            if not line.startswith("data:"):
                                continue
                            data_str = line[5:].strip()
                            if not data_str:
                                continue
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                            except ValueError:
                                continue
                            if isinstance(chunk, dict):
                                choices = chunk.get("choices")
                                if isinstance(choices, list) and choices:
                                    first_choice = choices[0]
                                    if isinstance(first_choice, dict):
                                        chunk_finish_reason = first_choice.get("finish_reason")
                                        if chunk_finish_reason:
                                            finish_reason = chunk_finish_reason
                            content_piece, reasoning_piece = _extract_openrouter_stream_parts(chunk)
                            if content_piece:
                                content_parts.append(content_piece)
                            if reasoning_piece:
                                reasoning_parts.append(reasoning_piece)

                            if _openrouter_debug_enabled():
                                now = time.monotonic()
                                if now - last_log_time >= 1.0:
                                    content_text = "".join(content_parts)
                                    reasoning_text = "".join(reasoning_parts)
                                    content_delta = content_text[last_log_content_len:]
                                    reasoning_delta = reasoning_text[last_log_reasoning_len:]
                                    if content_delta or reasoning_delta:
                                        logger.debug(
                                            "OpenRouter stream (1s) content=%r reasoning=%r",
                                            content_delta[-400:],
                                            reasoning_delta[-400:],
                                        )
                                    last_log_content_len = len(content_text)
                                    last_log_reasoning_len = len(reasoning_text)
                                    last_log_time = now
                    except Exception as exc:
                        logger.error("OpenRouter stream decode failed for model %s: %s", model, exc)
                        return None

                    streamed_text = "".join(content_parts).strip()
                    reasoning_text = "".join(reasoning_parts).strip()
                    if finish_reason == "length":
                        logger.warning(
                            "OpenRouter stream truncated by token limit for model %s (content=%s, reasoning=%s)",
                            model,
                            len(streamed_text),
                            len(reasoning_text),
                        )
                    if not streamed_text:
                        if _openrouter_debug_enabled():
                            if reasoning_text:
                                logger.debug(
                                    "OpenRouter stream ended without content (reasoning length=%s)",
                                    len(reasoning_text),
                                )
                        return None
                    if response_format:
                        extracted = _extract_json_payload(streamed_text)
                        if extracted:
                            return extracted
                        logger.warning(
                            "OpenRouter response for model %s ignored: expected JSON but none found (stream)",
                            model,
                        )
                        return None
                    return streamed_text
                try:
                    data = response.json()
                except ValueError:
                    if _should_dump_openrouter_debug():
                        _dump_openrouter_payload(
                            {"status": response.status_code, "text": response.text},
                            model=model,
                            tag="invalid_json",
                        )
                    logger.error(
                        "OpenRouter API response for model %s is not valid JSON: %s",
                        model,
                        response.text,
                    )
                    return None

                if _openrouter_debug_enabled():
                    try:
                        logger.debug(
                            "OpenRouter response JSON for model %s: %s",
                            model,
                            json.dumps(data, ensure_ascii=False),
                        )
                    except (TypeError, ValueError):
                        logger.debug("OpenRouter response JSON for model %s: <unserializable>", model)

                if response_format:
                    extracted_json = _extract_openrouter_json(data)
                    if extracted_json:
                        return extracted_json
                    logger.warning(
                        "OpenRouter response for model %s ignored: expected JSON but none found",
                        model,
                    )
                    return None
                else:
                    content_text = _extract_openrouter_text(data)
                    if content_text:
                        return content_text

                choices = data.get("choices")
                if isinstance(choices, list) and choices:
                    dump_path = _dump_openrouter_payload(
                        data,
                        model=model,
                        tag="missing_content",
                    )
                    if dump_path:
                        logger.warning(
                            "OpenRouter debug payload saved to %s",
                            dump_path,
                        )
                    logger.error(
                        "OpenRouter API response for model %s is missing message content: %s",
                        model,
                        data,
                    )
                    return None

                logger.error(
                    "OpenRouter API response for model %s missing choices: %s",
                    model,
                    data,
                )
                return None

            logger.error(
                "OpenRouter API Error (%s) for model %s - %s",
                response.status_code,
                model,
                response.text,
            )
            if _should_dump_openrouter_debug():
                _dump_openrouter_payload(
                    {"status": response.status_code, "text": response.text},
                    model=model,
                    tag="error",
                )
            return None

    def _generate_text_with_fallback(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        primary_model: Optional[str] = None,
        fallback_models: Optional[List[str]] = None,
        response_format: Optional[dict] = None,
        plugins: Optional[List[dict]] = None,
        stream: bool = False,
        stop: Optional[List[str]] = None,
        extra_body: Optional[dict] = None,
        timeout_seconds: float = 60.0,
        retry_without_format: bool = True,
    ) -> Optional[str]:
        """Try a primary model and optional fallback models sequentially."""

        fallback_models = fallback_models or []
        models_to_try: List[str] = []

        normalized_primary = (primary_model or self.model or "").strip()
        if not normalized_primary:
            normalized_primary = get_default_ai_model()
        if normalized_primary:
            models_to_try.append(normalized_primary)

        for candidate in fallback_models:
            normalized = (candidate or "").strip()
            if normalized and normalized not in models_to_try:
                models_to_try.append(normalized)

        if not models_to_try:
            logger.error("No models configured for AI request")
            return None

        def _try_models(with_response_format: Optional[dict]) -> Optional[str]:
            for index, model_name in enumerate(models_to_try):
                response = self._call_openrouter(
                    model_name,
                    prompt,
                    max_tokens,
                    temperature,
                    response_format=with_response_format,
                    plugins=plugins,
                    stream=stream,
                    stop=stop,
                    extra_body=extra_body,
                    timeout_seconds=timeout_seconds,
                )
                if response:
                    return response
                if index + 1 < len(models_to_try):
                    logger.info(
                        "Model %s failed, trying fallback %s",
                        model_name,
                        models_to_try[index + 1],
                    )
            return None

        response = _try_models(response_format)
        if response:
            return response

        if response_format and retry_without_format:
            logger.info("Retrying AI call without response_format enforcement")
            return _try_models(None)

        return None

    def get_ai_response(
        self,
        prompt: str,
        max_tokens: int = 2000,
        temperature: float = 0.7,
        model: Optional[str] = None,
        allow_fallback: bool = True,
        response_format: Optional[dict] = None,
        plugins: Optional[List[dict]] = None,
        stream: bool = False,
        stop: Optional[List[str]] = None,
        extra_body: Optional[dict] = None,
        timeout_seconds: float = 60.0,
        retry_without_format: bool = True,
    ) -> Optional[str]:
        """Send request to OpenRouter API with automatic fallback model."""

        selected_model = (model or self.model or "").strip()
        fallback_model = self.fallback_model.strip() if self.fallback_model else ""
        fallback_models: List[str] = []
        if allow_fallback and fallback_model and fallback_model != selected_model:
            fallback_models.append(fallback_model)
        if allow_fallback and response_format:
            json_fallback_env = os.getenv("OPENROUTER_JSON_FALLBACK_MODEL") or ""
            for candidate in json_fallback_env.split(","):
                normalized = candidate.strip()
                if normalized and normalized != selected_model and normalized not in fallback_models:
                    fallback_models.append(normalized)

        return self._generate_text_with_fallback(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            primary_model=selected_model,
            fallback_models=fallback_models,
            response_format=response_format,
            plugins=plugins,
            stream=stream,
            stop=stop,
            extra_body=extra_body,
            timeout_seconds=timeout_seconds,
            retry_without_format=retry_without_format,
        )

    def test_connection(self) -> bool:
        """Quick health check for OpenRouter connectivity."""
        try:
            response = self.get_ai_response("Ответь одним словом: 'готов'", max_tokens=10)
            return response is not None
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Connection test failed: %s", exc)
            return False


__all__ = ["BaseAIContentGenerator", "logger"]
