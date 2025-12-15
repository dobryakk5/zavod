import ast
import asyncio
import base64
import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import urllib.parse
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

import requests

from .system_settings import (
    get_image_generation_model,
    get_image_generation_timeout,
    get_video_generation_timeout,
)

logger = logging.getLogger(__name__)

try:
    from gradio_client import Client as GradioClient, handle_file
    GRADIO_AVAILABLE = True
except ImportError:
    GradioClient = None
    handle_file = None
    GRADIO_AVAILABLE = False

try:
    from telethon import TelegramClient, events
    from telethon.errors import AuthKeyUnregisteredError
    from telethon.tl.functions.messages import GetBotCallbackAnswerRequest
    TELETHON_AVAILABLE = True
except ImportError:
    TelegramClient = None
    events = None
    AuthKeyUnregisteredError = None
    GetBotCallbackAnswerRequest = None
    TELETHON_AVAILABLE = False

try:  # pragma: no cover - зависит от платформы
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows
    fcntl = None

SESSION_THREAD_LOCKS: Dict[str, threading.RLock] = {}
SESSION_THREAD_LOCKS_GUARD = threading.Lock()
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`[\]]+')
BASE64_ALLOWED_CHARS_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")
BASE64_FIELD_PATTERN = re.compile(
    r"(?:image_base64|b64_json|base64)[^A-Za-z0-9+/=]{0,10}([A-Za-z0-9+/=\r\n]+)",
    re.IGNORECASE
)
BASE64_BLOB_PATTERN = re.compile(r"([A-Za-z0-9+/=\r\n]{100,})")
DATA_IMAGE_BASE64_RE = re.compile(r"base64[, ](.+)", re.S)
VIDEO_RESPONSE_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
VIDEO_RESPONSE_CACHE_LOCK = threading.Lock()


def is_probably_base64(value: str) -> bool:
    """Heuristic + strict validator to ensure strings are real base64 blobs."""
    if not value:
        return False
    candidate = value.strip()
    if len(candidate) < 200:
        return False
    if not BASE64_ALLOWED_CHARS_RE.fullmatch(candidate):
        return False
    try:
        base64.b64decode(candidate, validate=True)
        return True
    except Exception:
        return False


def _extract_direct_image_url(text: Optional[str]) -> Optional[str]:
    """Find a direct image URL (png/jpg/webp) inside arbitrary bot text."""
    if not text:
        return None
    for raw_url in URL_PATTERN.findall(text):
        candidate = raw_url.strip("()[]<>., ")
        lowered = candidate.lower()
        base = lowered.split("?", 1)[0]
        if base.endswith((".png", ".jpg", ".jpeg", ".webp")):
            return candidate
    return None


def _download_remote_image(url: str) -> Optional[str]:
    """Download an image by direct link into a temp file and return the path."""
    try:
        timeout = max(5, get_image_generation_timeout())
    except Exception:
        timeout = 120

    try:
        response = requests.get(url, timeout=timeout)
    except Exception as exc:
        logger.error("Не удалось скачать изображение по ссылке %s: %s", url, exc)
        return None

    if response.status_code != 200:
        logger.error("Скачивание изображения %s завершилось с кодом %s", url, response.status_code)
        return None

    parsed = urllib.parse.urlparse(url)
    ext = os.path.splitext(parsed.path)[1]
    if not ext or ext.lower() not in [".png", ".jpg", ".jpeg", ".webp"]:
        ext = ".png"

    fd, temp_path = tempfile.mkstemp(suffix=ext)
    os.close(fd)
    with open(temp_path, "wb") as tmp_file:
        tmp_file.write(response.content)

    logger.info("Изображение скачано из прямой ссылки %s -> %s", url, temp_path)
    return temp_path

WAN_NEGATIVE_PROMPT = (
    "色调艳丽, 过曝, 静态, 细节模糊不清, 字幕, 风格, 作品, 画作, 画面, 静止, 整体发灰, 最差质量, "
    "低质量, JPEG压缩残留, 丑陋的, 残缺的, 多余的手指, 画得不好的手部, 画得不好的脸部, 畸形的, 毁容的, "
    "形态畸形的肢体, 手指融合, 静止不动的画面, 杂乱的背景, 三条腿, 背景人很多, 倒着走"
)


@contextmanager
def _telethon_session_lock(session_file: Optional[str]):
    """Глобальная блокировка для Telethon-сессии (sqlite), чтобы избежать database is locked."""

    normalized = os.path.abspath(session_file or "veo_generator.session")
    lock_file_handle = None
    used_file_lock = False
    thread_lock = None

    if fcntl and session_file:
        lock_path = normalized + ".lock"
        lock_dir = os.path.dirname(lock_path)
        if lock_dir and not os.path.exists(lock_dir):
            os.makedirs(lock_dir, exist_ok=True)
        try:
            lock_file_handle = open(lock_path, "w")
            fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_EX)
            used_file_lock = True
        except OSError as exc:  # pragma: no cover - I/O ошибки маловероятны
            logger.warning("Не удалось установить файловый лок для %s: %s", lock_path, exc)
            if lock_file_handle:
                lock_file_handle.close()
                lock_file_handle = None

    if not used_file_lock:
        lock_key = normalized
        with SESSION_THREAD_LOCKS_GUARD:
            thread_lock = SESSION_THREAD_LOCKS.setdefault(lock_key, threading.RLock())
        thread_lock.acquire()

    try:
        yield
    finally:
        if used_file_lock and lock_file_handle:
            try:
                fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_UN)
            finally:
                lock_file_handle.close()
        elif thread_lock:
            thread_lock.release()


def _cache_video_response(signature: Optional[str], payload: Dict[str, Any]):
    """Сохранить готовый ответ VEO по подписи промпта (макс 4 элемента)."""
    if not signature or not payload:
        return
    with VIDEO_RESPONSE_CACHE_LOCK:
        VIDEO_RESPONSE_CACHE[signature] = payload
        VIDEO_RESPONSE_CACHE.move_to_end(signature)
        while len(VIDEO_RESPONSE_CACHE) > 4:
            old_signature, old_payload = VIDEO_RESPONSE_CACHE.popitem(last=False)
            cleanup_paths = old_payload.get("cleanup_paths") or [old_payload.get("video_path")]
            for path in cleanup_paths:
                if path and isinstance(path, str) and os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass


def _pop_video_response(signature: Optional[str]) -> Optional[Dict[str, Any]]:
    """Получить и удалить ответ VEO из кеша."""
    if not signature:
        return None
    with VIDEO_RESPONSE_CACHE_LOCK:
        return VIDEO_RESPONSE_CACHE.pop(signature, None)


def _take_first_sentences(text: str, limit: int = 3) -> str:
    """Вернуть первые limit предложений (по . ! ?) как строку."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    sentences = SENTENCE_SPLIT_RE.split(cleaned)
    result_parts: List[str] = []
    for sentence in sentences:
        if sentence:
            result_parts.append(sentence)
        if len(result_parts) >= limit:
            break
    if not result_parts:
        return cleaned
    return " ".join(result_parts)


def _normalize_prompt_signature(
    value: Optional[str],
    max_length: int = 500,
    sentence_limit: int = 1,
) -> str:
    """
    Нормализовать промпт для сравнения (без регистра и лишних пробелов).

    Для сопоставления ответов читаем только первые sentence_limit предложений,
    по умолчанию сверяем первое предложение, чтобы не требовать полного промпта.
    """
    if not value:
        return ""
    head = _take_first_sentences(value, limit=sentence_limit)
    normalized = re.sub(r"\s+", " ", head).strip().lower()
    return normalized[:max_length]


def _extract_response_prompt_fragment(text: Optional[str]) -> Optional[str]:
    """Выделить фрагмент промпта из текста ответа VEO (после 'Ваш запрос:')."""
    if not text:
        return None
    match = re.search(r"Ваш запрос:\s*(.+)", text, flags=re.IGNORECASE | re.S)
    if not match:
        return None
    fragment = match.group(1)
    stop_tokens = [
        "\n",
        "🎛",
        "📍",
        "📌",
        "📎",
        "Инструмент",
        "Instrument",
        "▶",
        "🎬",
    ]
    for token in stop_tokens:
        idx = fragment.find(token)
        if idx != -1:
            fragment = fragment[:idx]
            break
    return _take_first_sentences(fragment.strip().strip('"'))


def generate_image(
    prompt: str,
    output_path: str,
    model: str,
    api_key: Optional[str],
    api_url: str,
    hf_client: Any = None
) -> Dict[str, Any]:
    """
    Сгенерировать изображение выбранной моделью.
    """
    normalized_model = (model or "openrouter").lower()
    logger.info("Генерация изображения (%s)", normalized_model)

    if normalized_model in {"nanobanana", "openrouter"}:
        return _generate_image_openrouter(prompt, output_path, api_key, api_url)
    if normalized_model == "huggingface":
        return _generate_image_huggingface(prompt, output_path, hf_client)
    if normalized_model == "flux2":
        return _generate_image_flux2(prompt, output_path)
    if normalized_model == "veo_photo":
        return {
            "success": False,
            "error": "veo_photo доступна только через Telegram бот, используйте generate_image_from_telegram_bot"
        }
    if normalized_model == "pollinations":
        return _generate_image_pollinations(prompt, output_path)
    if normalized_model == "giga_photo":
        return _generate_image_giga(prompt, output_path)
    return _generate_image_pollinations(prompt, output_path)


def generate_video_from_image(
    image_path: str,
    prompt: str,
    method: str = "wan",
    negative_prompt: Optional[str] = None,
    **options: Any
) -> Dict[str, Any]:
    """
    Создать короткое видео по изображению.
    """
    method_name = (method or "wan").lower()
    if method_name == "veo":
        return _generate_video_veo(image_path, prompt, **options)
    return _generate_video_wan(
        image_path=image_path,
        prompt=prompt,
        negative_prompt=negative_prompt,
        **options
    )


def generate_video_from_text(
    prompt: str,
    method: str = "veo",
    **options: Any
) -> Dict[str, Any]:
    """
    Создать видео только по текстовому описанию (сейчас поддерживается VEO).
    """
    method_name = (method or "veo").lower()
    if method_name != "veo":
        return {
            "success": False,
            "error": f"Метод '{method}' не поддерживает генерацию видео из текста"
        }

    return _generate_video_veo(
        image_path=None,
        prompt=prompt,
        text_only=True,
        **options
    )


def generate_image_from_telegram_bot(
    prompt: str,
    bot_username: str,
    **options: Any
) -> Dict[str, Any]:
    """
    Создать изображение через Telegram бота с выбором режима через inline-кнопки.
    
    Процесс:
    1) Открывает меню бота
    2) Выбирает /design
    3) Выбирает inline меню: 🌙 SORA Images
    4) Отправляет промпт и получает изображение
    
    Args:
        prompt: Текстовый промпт для генерации изображения
        bot_username: Username Telegram бота
        **options: Дополнительные параметры:
            - session_path: Путь к файлу сессии
            - session_name: Имя сессии
            - timeout: Таймаут в секундах
            - api_id: Telegram API ID
            - api_hash: Telegram API Hash
    
    Returns:
        Dict с результатом генерации
    """
    if not TELETHON_AVAILABLE:
        return {"success": False, "error": "telethon не установлен. Установите пакет telethon."}

    if not prompt:
        return {"success": False, "error": "Промпт обязателен для генерации изображения"}

    session_path = (
        options.get("session_path")
        or os.getenv("IMAGE_BOT_SESSION_PATH")
        or os.getenv("IMAGE_BOT_SESSION_FILE")
        or os.getenv("TELEGRAM_SESSION_PATH")
    )
    session_name_raw = options.get("session_name") or os.getenv("IMAGE_BOT_SESSION_NAME", "image_generator")
    session_label = session_path or session_name_raw
    
    if session_path:
        expanded_path = os.path.abspath(os.path.expanduser(session_path))
        if expanded_path.endswith(".session"):
            session_name = expanded_path[:-8]
            session_file = expanded_path
        else:
            session_name = expanded_path
            session_file = expanded_path + ".session"
        session_label = session_file
        logger.info("Используется файл сессии Telethon: %s", session_file)
    else:
        session_name = session_name_raw
        session_file = f"{session_name}.session"
    
    session_dir = os.path.dirname(session_name)
    if session_dir and not os.path.exists(session_dir):
        os.makedirs(session_dir, exist_ok=True)
    
    timeout_value = options.get("timeout")
    if timeout_value is None:
        env_timeout = os.getenv("IMAGE_BOT_TIMEOUT")
        if env_timeout:
            try:
                timeout_value = int(env_timeout)
            except ValueError:
                logger.warning("Некорректное значение IMAGE_BOT_TIMEOUT: %s", env_timeout)
                timeout_value = None
        if timeout_value is None:
            timeout_value = get_image_generation_timeout()
    try:
        timeout = max(30, int(timeout_value))
    except (TypeError, ValueError):
        timeout = get_image_generation_timeout()

    api_id = (
        options.get("api_id")
        or os.getenv("TELEGRAM_API_ID")
        or os.getenv("TG_API_ID")
        or os.getenv("API_ID")
    )
    api_hash = (
        options.get("api_hash")
        or os.getenv("TELEGRAM_API_HASH")
        or os.getenv("TG_API_HASH")
        or os.getenv("API_HASH")
    )

    if not api_id or not api_hash:
        return {
            "success": False,
            "error": "TELEGRAM_API_ID (или TG_API_ID/API_ID) и TELEGRAM_API_HASH (TG_API_HASH/API_HASH) обязательны для генерации изображений через Telegram бота"
        }

    try:
        api_id = int(api_id)
    except ValueError:
        return {"success": False, "error": "TELEGRAM_API_ID должен быть числом"}

    expected_prompt_signature = _normalize_prompt_signature(prompt)
    matched_prompt_fragment: Optional[str] = None
    cleanup_session_files: List[str] = []

    async def _image_bot_coroutine() -> Optional[Dict[str, Any]]:
        session_base = session_name[:-8] if session_name.endswith('.session') else session_name
        thread_id = threading.get_ident()
        unique_suffix = uuid.uuid4().hex[:6]
        thread_session_name = f"{session_base}_thread_{thread_id}_{unique_suffix}"
        thread_session_file = f"{thread_session_name}.session"
        cleanup_session_files.clear()
        cleanup_session_files.extend([
            thread_session_file,
            f"{thread_session_file}-journal",
            f"{thread_session_file}-wal",
        ])

        source_session_file = f"{session_base}.session"

        logger.info("[IMAGE BOT Thread %s] Начало инициализации клиента", thread_id)
        logger.info("[IMAGE BOT Thread %s] Базовая сессия: %s", thread_id, source_session_file)
        logger.info("[IMAGE BOT Thread %s] Сессия потока: %s", thread_id, thread_session_file)

        thread_session_dir = os.path.dirname(thread_session_file)
        if thread_session_dir:
            os.makedirs(thread_session_dir, exist_ok=True)

        def _take_cached_payload(stage: str) -> Optional[Dict[str, Any]]:
            # Для изображений пока не используем кеш, так как каждый промпт уникален
            return None

        with _telethon_session_lock(source_session_file):
            if os.path.exists(source_session_file):
                try:
                    shutil.copy2(source_session_file, thread_session_file)
                    logger.info(
                        "[IMAGE BOT Thread %s] Скопирована сессия: %s -> %s",
                        thread_id,
                        source_session_file,
                        thread_session_file
                    )
                except Exception as e:
                    logger.warning("[IMAGE BOT Thread %s] Не удалось скопировать сессию: %s", thread_id, e)
            else:
                logger.warning("[IMAGE BOT Thread %s] Исходная сессия не найдена: %s", thread_id, source_session_file)

        logger.info("[IMAGE BOT Thread %s] Создание TelegramClient с сессией: %s", thread_id, thread_session_name)
        client = TelegramClient(thread_session_name, api_id, api_hash)

        try:
            cached_before_connect = _take_cached_payload("before connect")
            if cached_before_connect:
                return cached_before_connect
            
            logger.info("[IMAGE BOT Thread %s] Попытка подключения к Telegram...", thread_id)
            await client.connect()
            logger.info("[IMAGE BOT Thread %s] Успешно подключено к Telegram", thread_id)

            logger.info("[IMAGE BOT Thread %s] Проверка авторизации...", thread_id)
            if not await client.is_user_authorized():
                raise RuntimeError(
                    f"Telethon session '{session_label}' не авторизована. "
                    "Запустите backend/core/foto_video_gen.py (или scripts/authorize_telegram.py) и пройдите вход в Telegram."
                )
            logger.info("[IMAGE BOT Thread %s] Авторизация подтверждена", thread_id)

            try:
                logger.info("[IMAGE BOT Thread %s] Получение бота %s...", thread_id, bot_username)
                bot = await client.get_entity(bot_username)
                logger.info("[IMAGE BOT Thread %s] Бот получен: %s", thread_id, bot_username)
            except AuthKeyUnregisteredError as auth_err:
                raise RuntimeError(
                    f"Telethon session '{session_label}' требует повторной авторизации: {auth_err}. "
                    "Удалите файл сессии и выполните вход снова через backend/core/foto_video_gen.py или scripts/authorize_telegram.py."
                ) from auth_err
            except Exception:
                raise

            try:
                logger.info("[IMAGE BOT Thread %s] Начало разговора с ботом (timeout=%s)...", thread_id, timeout)
                async with client.conversation(bot, timeout=timeout) as conv:
                    # Шаг 1: Отправляем команду /design
                    logger.info("[IMAGE BOT Thread %s] Отправка команды /design...", thread_id)
                    await conv.send_message("/design")
                    
                    # Ждем ответа с кнопками
                    try:
                        response = await conv.get_response(timeout=5)
                        logger.info("[IMAGE BOT Thread %s] Получен ответ на /design", thread_id)
                    except asyncio.TimeoutError:
                        logger.warning("[IMAGE BOT Thread %s] Таймаут ожидания ответа на /design", thread_id)
                        return None

                    # Шаг 2: Ищем и нажимаем кнопку "🌙 SORA Images"
                    if response.reply_markup:
                        sora_button = None
                        for row in response.reply_markup.rows:
                            for button in row.buttons:
                                if "SORA" in button.text or "🌙" in button.text:
                                    sora_button = button
                                    break
                            if sora_button:
                                break
                        
                        if sora_button:
                            logger.info("[IMAGE BOT Thread %s] Нажимаю кнопку: %s", thread_id, sora_button.text)
                            button_data = getattr(sora_button, "data", None)
                            if button_data:
                                await client(GetBotCallbackAnswerRequest(
                                    peer=bot_username,
                                    msg_id=response.id,
                                    data=button_data
                                ))
                            else:
                                # Некоторые боты отправляют обычные клавиатурные кнопки.
                                await conv.send_message(sora_button.text)
                            logger.info("[IMAGE BOT Thread %s] Кнопка SORA Images нажата", thread_id)
                        else:
                            logger.error("[IMAGE BOT Thread %s] Кнопка SORA Images не найдена", thread_id)
                            return None
                    else:
                        logger.error("[IMAGE BOT Thread %s] Нет inline-кнопок в ответе на /design", thread_id)
                        return None

                    # Шаг 3: Ждем подтверждение выбора режима и отправляем промпт
                    try:
                        mode_response = await conv.get_response(timeout=5)
                        logger.info("[IMAGE BOT Thread %s] Получено подтверждение выбора режима", thread_id)
                    except asyncio.TimeoutError:
                        logger.warning("[IMAGE BOT Thread %s] Таймаут ожидания подтверждения режима", thread_id)
                        return None

                    # Шаг 4: Отправляем промпт
                    logger.info("[IMAGE BOT Thread %s] Отправка промпта: %s", thread_id, prompt[:100])
                    await conv.send_message(prompt)
                    logger.info("[IMAGE BOT Thread %s] Промпт отправлен, ожидание изображения...", thread_id)

                    # Шаг 5: Получаем ответы бота и ждём изображение или прямую ссылку
                    followup_attempts = 6
                    for attempt in range(followup_attempts):
                        try:
                            image_response = await conv.get_response(timeout=timeout)
                        except asyncio.TimeoutError:
                            logger.error("Бот не ответил с изображением в течение %s секунд", timeout)
                            return None

                        response_text = (image_response.raw_text or "").strip()
                        if response_text:
                            logger.info(
                                "[IMAGE BOT Thread %s] Ответ бота (%s/%s): %s",
                                thread_id,
                                attempt + 1,
                                followup_attempts,
                                response_text[:120],
                            )

                        if image_response.media:
                            fd, temp_path = tempfile.mkstemp(suffix=".png")
                            os.close(fd)
                            downloaded = await client.download_media(image_response.media, file=temp_path)
                            logger.info("[IMAGE BOT Thread %s] Изображение успешно скачано: %s", thread_id, downloaded)
                            return {
                                "success": True,
                                "image_path": downloaded,
                                "model": "veo_photo",
                                "cleanup_paths": [downloaded],
                                "response_text": response_text,
                            }

                        direct_url = _extract_direct_image_url(response_text)
                        if direct_url:
                            logger.info("[IMAGE BOT Thread %s] Найдена прямая ссылка на изображение: %s", thread_id, direct_url)
                            downloaded = _download_remote_image(direct_url)
                            if not downloaded:
                                return {
                                    "success": False,
                                    "error": f"Не удалось скачать изображение по ссылке: {direct_url}",
                                    "response_text": response_text,
                                }
                            return {
                                "success": True,
                                "image_path": downloaded,
                                "model": "veo_photo",
                                "cleanup_paths": [downloaded],
                                "response_text": response_text,
                            }

                        if response_text:
                            continue

                        logger.info("[IMAGE BOT Thread %s] Получено пустое сообщение без медиа, ждем дальше", thread_id)

                    logger.error("[IMAGE BOT Thread %s] Бот не прислал изображение после %s сообщений", thread_id, followup_attempts)
                    return {"success": False, "error": "Bot did not send an image"}

            except asyncio.TimeoutError:
                logger.error("Бот не ответил в течение %s секунд (conversation)", timeout)
                return None

        finally:
            await client.disconnect()
            if os.path.exists(thread_session_file):
                try:
                    with _telethon_session_lock(source_session_file):
                        shutil.copy2(thread_session_file, source_session_file)
                        logger.info(
                            "[IMAGE BOT Thread %s] Сессия потока синхронизирована обратно в базовую",
                            thread_id
                        )
                except Exception as sync_exc:
                    logger.warning(
                        "[IMAGE BOT Thread %s] Не удалось обновить базовую сессию: %s",
                        thread_id,
                        sync_exc
                    )

    try:
        image_payload = asyncio.run(_image_bot_coroutine())
    except Exception as exc:
        logger.error("Ошибка общения с Telegram ботом для генерации изображения: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}
    finally:
        for temp_path in cleanup_session_files:
            if not temp_path:
                continue
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    if temp_path.endswith(".session"):
                        logger.info("[IMAGE BOT] Удалена временная сессия: %s", temp_path)
                except OSError:
                    pass

    if not image_payload:
        return {"success": False, "error": "Не удалось получить изображение от Telegram бота"}

    image_path = image_payload.get("image_path")
    if not image_path or not os.path.exists(image_path):
        return {"success": False, "error": "Не удалось получить изображение от Telegram бота"}

    return {
        "success": True,
        "image_path": image_path,
        "model": "veo_photo",
        "cleanup_paths": image_payload.get("cleanup_paths") or [image_path],
        "response_text": image_payload.get("response_text", ""),
    }


def _generate_image_pollinations(prompt: str, output_path: str) -> Dict[str, Any]:
    try:
        image_timeout = get_image_generation_timeout()
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true"
        logger.info("Pollinations запрос: %s", image_url)

        response = requests.get(image_url, timeout=image_timeout)
        if response.status_code != 200:
            logger.error("Ошибка Pollinations HTTP %s", response.status_code)
            return {"success": False, "error": f"HTTP error {response.status_code}"}

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        return {
            "success": True,
            "image_path": output_path,
            "image_url": image_url,
            "model": "pollinations"
        }
    except requests.exceptions.Timeout:
        logger.error("Таймаут Pollinations")
        return {"success": False, "error": "Request timeout"}
    except Exception as exc:
        logger.error("Ошибка Pollinations: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_image_giga(prompt: str, output_path: str) -> Dict[str, Any]:
    """Генерация изображений через Giga API (предполагаемый сервис)."""
    try:
        image_timeout = get_image_generation_timeout()

        # Для Giga фото будем использовать Pollinations как fallback пока
        # TODO: Заменить на реальный Giga API когда будет доступен
        encoded_prompt = urllib.parse.quote(prompt)
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=1024&nologo=true&style=giga"
        logger.info("Giga фото запрос: %s", image_url)

        response = requests.get(image_url, timeout=image_timeout)
        if response.status_code != 200:
            logger.error("Ошибка Giga фото HTTP %s", response.status_code)
            return {"success": False, "error": f"HTTP error {response.status_code}"}

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)

        return {
            "success": True,
            "image_path": output_path,
            "image_url": image_url,
            "model": "giga_photo"
        }
    except requests.exceptions.Timeout:
        logger.error("Таймаут Giga фото")
        return {"success": False, "error": "Request timeout"}
    except Exception as exc:
        logger.error("Ошибка Giga фото: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _extract_openrouter_image_payload(payload: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return first found image URL or base64 string from OpenRouter-like payloads."""
    image_url: Optional[str] = None
    image_base64: Optional[str] = None

    def parse_structured_string(value: str) -> Optional[Any]:
        if not value:
            return None
        stripped_value = value.strip()
        if not stripped_value or stripped_value[0] not in "{[":
            return None
        for parser in (json.loads, ast.literal_eval):
            try:
                return parser(stripped_value)
            except Exception:
                continue
        return None

    def assign_base64(value: Optional[str]):
        nonlocal image_base64
        if image_base64 or not isinstance(value, str):
            return
        stripped = value.strip()
        if stripped and is_probably_base64(stripped):
            image_base64 = stripped

    def try_assign_data_uri(value: Optional[str]) -> bool:
        if not isinstance(value, str):
            return False
        stripped = value.strip()
        if not stripped.startswith("data:image"):
            return False
        match = DATA_IMAGE_BASE64_RE.search(stripped)
        if not match:
            return False
        candidate = match.group(1).strip()
        if is_probably_base64(candidate):
            assign_base64(candidate)
            return True
        return False

    def assign_url(value: Optional[str]):
        nonlocal image_url
        if image_url or not isinstance(value, str):
            return
        stripped = value.strip()
        if not stripped:
            return
        if try_assign_data_uri(stripped):
            return
        if stripped.startswith("http://") or stripped.startswith("https://"):
            image_url = stripped
        elif is_probably_base64(stripped):
            assign_base64(stripped)

    def assign_image_value(value: Any):
        if image_url or image_base64:
            return
        if isinstance(value, dict):
            for key in ("url", "b64_json", "base64", "image_base64", "data"):
                if key in value:
                    assign_image_value(value[key])
                    if image_url or image_base64:
                        return
        elif isinstance(value, list):
            for entry in value:
                assign_image_value(entry)
                if image_url or image_base64:
                    return
        else:
            assign_url(value)

    def walk(node: Any):
        if image_url or image_base64 or node is None:
            return
        if isinstance(node, dict):
            node_type = node.get("type")
            if node_type in {"output_image", "image"}:
                assign_image_value(node.get("image_url"))
                assign_image_value(node.get("image_base64"))
                assign_image_value(node.get("b64_json"))
                assign_image_value(node.get("base64"))
                assign_image_value(node.get("image"))

                if image_url or image_base64:
                    return
            if "image_url" in node:
                assign_image_value(node["image_url"])
                if image_url or image_base64:
                    return
            for key in ("image_base64", "b64_json", "base64"):
                if key in node:
                    assign_image_value(node[key])
                    if image_url or image_base64:
                        return
            if "images" in node:
                walk(node["images"])
                if image_url or image_base64:
                    return
            for key in ("content", "data", "message", "choices", "result", "outputs", "response"):
                if key in node:
                    walk(node[key])
                    if image_url or image_base64:
                        return
            if node_type in {"tool_result", "tool_response"} and "content" in node:
                walk(node["content"])
                if image_url or image_base64:
                    return
            if "text" in node and isinstance(node["text"], str):
                urls = URL_PATTERN.findall(node["text"])
                if urls:
                    assign_url(urls[0])
        elif isinstance(node, list):
            for entry in node:
                walk(entry)
                if image_url or image_base64:
                    break
        elif isinstance(node, str):
            stripped_node = node.strip()
            if not stripped_node:
                return
            if try_assign_data_uri(stripped_node):
                return

            structured = parse_structured_string(stripped_node)
            if structured is not None:
                walk(structured)
                if image_url or image_base64:
                    return

            urls = URL_PATTERN.findall(stripped_node)
            if urls:
                assign_url(urls[0])
                if image_url or image_base64:
                    return

            keyword_match = BASE64_FIELD_PATTERN.search(stripped_node)
            if keyword_match:
                assign_base64(keyword_match.group(1).strip())
                if image_url or image_base64:
                    return

            blob_match = BASE64_BLOB_PATTERN.search(stripped_node)
            if blob_match:
                assign_base64(blob_match.group(1))

    walk(payload)
    return image_url, image_base64


def _generate_image_openrouter(
    prompt: str,
    output_path: str,
    api_key: Optional[str],
    api_url: str
) -> Dict[str, Any]:
    if not api_key:
        return {"success": False, "error": "OPENROUTER_API_KEY не задан"}

    try:
        image_timeout = get_image_generation_timeout()
        model = get_image_generation_model()
        logger.info("Генерация через OpenRouter (%s)", model)
        request_payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": f"Generate an image: {prompt}"
                }
            ],
            "modalities": ["image", "text"]
        }

        response = requests.post(
            api_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://zavod-content-factory.com",
                "X-Title": "Content Factory Image Generator"
            },
            json=request_payload,
            timeout=image_timeout
        )

        if response.status_code != 200:
            logger.error("OpenRouter ошибка %s: %s", response.status_code, response.text)
            return {
                "success": False,
                "error": f"API error {response.status_code}: {response.text}"
            }

        data = response.json()
        message = None
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first_choice = choices[0] or {}
            if not isinstance(first_choice, dict):
                first_choice = {}
            message = first_choice.get("message") or {}

        if isinstance(message, dict):
            images_block = message.get("images")
            if isinstance(images_block, list) and images_block:
                for idx, image_entry in enumerate(images_block, start=1):
                    url_preview = None
                    if isinstance(image_entry, dict):
                        image_url_obj = image_entry.get("image_url")
                        if isinstance(image_url_obj, dict):
                            url_preview = image_url_obj.get("url")
                        elif isinstance(image_url_obj, str):
                            url_preview = image_url_obj
                    if url_preview:
                        logger.info(
                            "OpenRouter вернул изображение %s: %s...",
                            idx,
                            url_preview[:60]
                        )

        image_url, image_base64 = _extract_openrouter_image_payload(data)

        if image_base64:
            base64_data = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
            base64_data = "".join(base64_data.split())
            try:
                image_bytes = base64.b64decode(base64_data)
            except Exception as decode_exc:  # pragma: no cover - unexpected data shape
                logger.error("Не удалось декодировать base64 изображение: %s", decode_exc)
                return {"success": False, "error": "Invalid base64 data from OpenRouter"}

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_bytes)
            return {
                "success": True,
                "image_path": output_path,
                "image_url": None,
                "image_base64": image_base64,
                "model": "nanobanana"
            }

        if image_url:
            img_response = requests.get(image_url, timeout=image_timeout)
            if img_response.status_code != 200:
                logger.error("Ошибка скачивания изображения %s", img_response.status_code)
                return {
                    "success": False,
                    "error": f"Image download HTTP error {img_response.status_code}"
                }

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(img_response.content)

            return {
                "success": True,
                "image_path": output_path,
                "image_url": image_url,
                "image_base64": None,
                "model": "nanobanana"
            }

        logger.error("Не удалось извлечь изображение из ответа: %s", data)
        return {"success": False, "error": "No image URL or base64 data in response"}

    except requests.exceptions.Timeout:
        logger.error("Таймаут OpenRouter")
        return {"success": False, "error": "Request timeout"}
    except Exception as exc:
        logger.error("Ошибка OpenRouter: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_image_flux2(prompt: str, output_path: str) -> Dict[str, Any]:
    if not GRADIO_AVAILABLE:
        return {"success": False, "error": "gradio_client not installed. Run pip install gradio_client."}

    try:
        def _env_bool(name: str, default: bool) -> bool:
            value = os.getenv(name)
            if value is None:
                return default
            return value.strip().lower() in ("1", "true", "yes", "on")

        space_name = os.getenv("FLUX2_SPACE", "black-forest-labs/FLUX.2-dev")
        api_name = os.getenv("FLUX2_API_NAME", "/infer")
        width = int(os.getenv("FLUX2_WIDTH", "1024"))
        height = int(os.getenv("FLUX2_HEIGHT", "1024"))
        seed = float(os.getenv("FLUX2_SEED", "0"))
        randomize_seed = _env_bool("FLUX2_RANDOMIZE_SEED", True)
        steps = float(os.getenv("FLUX2_STEPS", "30"))
        guidance_scale = float(os.getenv("FLUX2_GUIDANCE", "4"))
        prompt_upsampling = _env_bool("FLUX2_PROMPT_UPSAMPLING", True)

        client = GradioClient(space_name)
        result = client.predict(
            prompt=prompt,
            input_images=[],
            seed=seed,
            randomize_seed=randomize_seed,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            prompt_upsampling=prompt_upsampling,
            api_name=api_name
        )

        image_entry: Optional[Dict[str, Any]] = None
        if isinstance(result, (list, tuple)) and result:
            candidate = result[0]
            if isinstance(candidate, dict):
                image_entry = candidate
        elif isinstance(result, dict):
            image_entry = result

        path_candidate = None
        url_candidate = None

        if image_entry:
            path_candidate = image_entry.get("path")
            url_candidate = image_entry.get("url")
            meta = image_entry.get("meta")
            if isinstance(meta, dict):
                url_candidate = url_candidate or meta.get("url")
            nested_image = image_entry.get("image")
            if isinstance(nested_image, dict):
                path_candidate = path_candidate or nested_image.get("path")
                url_candidate = url_candidate or nested_image.get("url")

        if isinstance(result, str) and not path_candidate:
            path_candidate = result

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        saved = False

        if path_candidate and os.path.exists(path_candidate):
            shutil.copyfile(path_candidate, output_path)
            saved = True
        else:
            download_url = None
            if path_candidate and str(path_candidate).startswith("http"):
                download_url = path_candidate
            elif url_candidate:
                download_url = url_candidate

            if download_url:
                image_timeout = get_image_generation_timeout()
                response = requests.get(download_url, timeout=image_timeout)
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(response.content)
                saved = True

        if not saved:
            logger.error("FLUX.2 Space не вернуло путь или URL")
            return {"success": False, "error": "Unable to retrieve generated image from FLUX.2 space"}

        return {
            "success": True,
            "image_path": output_path,
            "image_url": url_candidate,
            "model": "flux2"
        }
    except Exception as exc:
        logger.error("Ошибка FLUX.2: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_image_huggingface(prompt: str, output_path: str, hf_client: Any) -> Dict[str, Any]:
    if not hf_client:
        return {
            "success": False,
            "error": "HuggingFace client not available. Install huggingface_hub and set HF_TOKEN."
        }

    try:
        image = hf_client.text_to_image(prompt=prompt)
        img_bytes = BytesIO()
        image.save(img_bytes, format="PNG")
        img_bytes = img_bytes.getvalue()

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(img_bytes)

        return {
            "success": True,
            "image_path": output_path,
            "image_url": None,
            "model": "huggingface"
        }
    except Exception as exc:
        logger.error("Ошибка HuggingFace: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_video_wan(
    image_path: str,
    prompt: str,
    negative_prompt: Optional[str],
    **options: Any
) -> Dict[str, Any]:
    if not GRADIO_AVAILABLE or not handle_file:
        return {"success": False, "error": "gradio_client not installed. Run pip install gradio_client."}

    gradio_space = options.get("gradio_space") or os.getenv("WAN_VIDEO_SPACE", "zerogpu-aoti/wan2-2-fp8da-aoti-faster")
    api_name = options.get("api_name") or os.getenv("WAN_VIDEO_API", "/generate_video")
    steps = options.get("steps", int(os.getenv("WAN_VIDEO_STEPS", "6")))
    duration_seconds = options.get("duration_seconds", float(os.getenv("WAN_VIDEO_DURATION", "3.5")))
    guidance_scale = options.get("guidance_scale", float(os.getenv("WAN_VIDEO_GUIDANCE", "1")))
    guidance_scale_2 = options.get("guidance_scale_2", float(os.getenv("WAN_VIDEO_GUIDANCE_2", "1")))
    seed = options.get("seed", int(os.getenv("WAN_VIDEO_SEED", "42")))
    randomize_seed_opt = options.get("randomize_seed")
    if randomize_seed_opt is None:
        randomize_seed = os.getenv("WAN_VIDEO_RANDOMIZE_SEED", "true").lower() in ("1", "true", "yes", "on")
    else:
        randomize_seed = bool(randomize_seed_opt)

    negative_prompt = negative_prompt or WAN_NEGATIVE_PROMPT

    try:
        client = GradioClient(gradio_space)
        payload = {
            "input_image": handle_file(image_path),
            "prompt": prompt,
            "steps": steps,
            "negative_prompt": negative_prompt,
            "duration_seconds": duration_seconds,
            "guidance_scale": guidance_scale,
            "guidance_scale_2": guidance_scale_2,
            "seed": seed,
            "randomize_seed": randomize_seed,
            "api_name": api_name
        }

        result = client.predict(**payload)
        downloaded_temp_files: List[str] = []

        def _download_url_wrapper(url: str) -> Optional[str]:
            path = _download_url(url)
            if path:
                downloaded_temp_files.append(path)
            return path

        video_temp_path = _extract_video_path(result, _download_url_wrapper)

        if not video_temp_path or not os.path.exists(video_temp_path):
            logger.error("Не удалось получить путь к видео WAN")
            for tmp in downloaded_temp_files:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            return {"success": False, "error": "Unable to retrieve WAN video result"}

        return {
            "success": True,
            "video_path": video_temp_path,
            "model": "wan",
            "cleanup_paths": downloaded_temp_files
        }
    except Exception as exc:
        logger.error("Ошибка WAN видео: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}


def _generate_video_veo(
    image_path: Optional[str],
    prompt: str,
    text_only: bool = False,
    **options: Any
) -> Dict[str, Any]:
    if not TELETHON_AVAILABLE:
        return {"success": False, "error": "telethon не установлен. Установите пакет telethon."}

    if not text_only and not image_path:
        return {"success": False, "error": "Для генерации по изображению нужен путь к файлу"}

    bot_username = options.get("bot_username") or os.getenv("VEO_BOT_USERNAME", "syntxaibot")
    session_path = (
        options.get("session_path")
        or os.getenv("VEO_SESSION_PATH")
        or os.getenv("VEO_SESSION_FILE")
        or os.getenv("TELEGRAM_SESSION_PATH")
    )
    session_name_raw = options.get("session_name") or os.getenv("VEO_SESSION_NAME", "veo_generator")
    session_label = session_path or session_name_raw
    if session_path:
        expanded_path = os.path.abspath(os.path.expanduser(session_path))
        if expanded_path.endswith(".session"):
            session_name = expanded_path[:-8]
            session_file = expanded_path
        else:
            session_name = expanded_path
            session_file = expanded_path + ".session"
        session_label = session_file
        logger.info("Используется файл сессии Telethon: %s", session_file)
    else:
        session_name = session_name_raw
        session_file = f"{session_name}.session"
    session_dir = os.path.dirname(session_name)
    if session_dir and not os.path.exists(session_dir):
        os.makedirs(session_dir, exist_ok=True)
    timeout_value = options.get("timeout")
    if timeout_value is None:
        env_timeout = os.getenv("VEO_TIMEOUT")
        if env_timeout:
            try:
                timeout_value = int(env_timeout)
            except ValueError:
                logger.warning("Некорректное значение VEO_TIMEOUT: %s", env_timeout)
                timeout_value = None
        if timeout_value is None:
            timeout_value = get_video_generation_timeout()
    try:
        timeout = max(30, int(timeout_value))
    except (TypeError, ValueError):
        timeout = get_video_generation_timeout()

    api_id = (
        options.get("api_id")
        or os.getenv("TELEGRAM_API_ID")
        or os.getenv("TG_API_ID")
        or os.getenv("API_ID")
    )
    api_hash = (
        options.get("api_hash")
        or os.getenv("TELEGRAM_API_HASH")
        or os.getenv("TG_API_HASH")
        or os.getenv("API_HASH")
    )

    if not api_id or not api_hash:
        return {
            "success": False,
            "error": "TELEGRAM_API_ID (или TG_API_ID/API_ID) и TELEGRAM_API_HASH (TG_API_HASH/API_HASH) обязательны для метода VEO"
        }

    try:
        api_id = int(api_id)
    except ValueError:
        return {"success": False, "error": "TELEGRAM_API_ID должен быть числом"}

    caption = prompt or options.get("fallback_prompt") or "Please animate this image"
    # Убрать markdown форматирование перед созданием сигнатуры
    caption_clean = re.sub(r'\*+', '', caption).strip()
    expected_prompt_signature = _normalize_prompt_signature(caption_clean)
    matched_prompt_fragment: Optional[str] = None
    cached_payload = _pop_video_response(expected_prompt_signature)
    if cached_payload:
        logger.info("[VEO] Используем кешированный ответ для промпта до обращения к боту")
        cached_payload.pop("prompt_signature", None)
        return cached_payload

    cleanup_session_files: List[str] = []

    async def _veo_coroutine() -> Optional[Dict[str, Any]]:
        session_base = session_name[:-8] if session_name.endswith('.session') else session_name
        thread_id = threading.get_ident()
        unique_suffix = uuid.uuid4().hex[:6]
        thread_session_name = f"{session_base}_thread_{thread_id}_{unique_suffix}"
        thread_session_file = f"{thread_session_name}.session"
        cleanup_session_files.clear()
        cleanup_session_files.extend([
            thread_session_file,
            f"{thread_session_file}-journal",
            f"{thread_session_file}-wal",
        ])

        source_session_file = f"{session_base}.session"

        logger.info("[VEO Thread %s] Начало инициализации клиента", thread_id)
        logger.info("[VEO Thread %s] Базовая сессия: %s", thread_id, source_session_file)
        logger.info("[VEO Thread %s] Сессия потока: %s", thread_id, thread_session_file)

        thread_session_dir = os.path.dirname(thread_session_file)
        if thread_session_dir:
            os.makedirs(thread_session_dir, exist_ok=True)

        def _take_cached_payload(stage: str) -> Optional[Dict[str, Any]]:
            cached = _pop_video_response(expected_prompt_signature)
            if cached:
                logger.info("[VEO Thread %s] Найден кешированный ответ (%s) для текущего промпта", thread_id, stage)
            return cached

        with _telethon_session_lock(source_session_file):
            if os.path.exists(source_session_file):
                try:
                    shutil.copy2(source_session_file, thread_session_file)
                    logger.info(
                        "[VEO Thread %s] Скопирована сессия: %s -> %s",
                        thread_id,
                        source_session_file,
                        thread_session_file
                    )
                except Exception as e:
                    logger.warning("[VEO Thread %s] Не удалось скопировать сессию: %s", thread_id, e)
            else:
                logger.warning("[VEO Thread %s] Исходная сессия не найдена: %s", thread_id, source_session_file)

        logger.info("[VEO Thread %s] Создание TelegramClient с сессией: %s", thread_id, thread_session_name)
        client = TelegramClient(thread_session_name, api_id, api_hash)

        try:
            cached_before_connect = _take_cached_payload("before connect")
            if cached_before_connect:
                return cached_before_connect
            logger.info("[VEO Thread %s] Попытка подключения к Telegram...", thread_id)
            await client.connect()
            logger.info("[VEO Thread %s] Успешно подключено к Telegram", thread_id)

            logger.info("[VEO Thread %s] Проверка авторизации...", thread_id)
            if not await client.is_user_authorized():
                raise RuntimeError(
                    f"Telethon session '{session_label}' не авторизована. "
                    "Запустите backend/core/foto_video_gen.py (или scripts/authorize_telegram.py) и пройдите вход в Telegram."
                )
            logger.info("[VEO Thread %s] Авторизация подтверждена", thread_id)

            try:
                logger.info("[VEO Thread %s] Получение бота %s...", thread_id, bot_username)
                bot = await client.get_entity(bot_username)
                logger.info("[VEO Thread %s] Бот получен: %s", thread_id, bot_username)
            except AuthKeyUnregisteredError as auth_err:
                raise RuntimeError(
                    f"Telethon session '{session_label}' требует повторной авторизации: {auth_err}. "
                    "Удалите файл сессии и выполните вход снова через backend/core/foto_video_gen.py или scripts/authorize_telegram.py."
                ) from auth_err
            except Exception:
                raise
            try:
                logger.info("[VEO Thread %s] Начало разговора с ботом (timeout=%s)...", thread_id, timeout)
                async with client.conversation(bot, timeout=timeout) as conv:
                    # Шаг 1: Отправляем команду /video
                    logger.info("[VEO Thread %s] Отправка команды /video...", thread_id)
                    await conv.send_message("/video")
                    
                    # Ждем ответа с кнопками
                    try:
                        response = await conv.get_response(timeout=5)
                        logger.info("[VEO Thread %s] Получен ответ на /video", thread_id)
                    except asyncio.TimeoutError:
                        logger.warning("[VEO Thread %s] Таймаут ожидания ответа на /video", thread_id)
                        return None

                    # Шаг 2: Ищем и нажимаем кнопку "⭕️ Veo"
                    if response.reply_markup:
                        veo_button = None
                        for row in response.reply_markup.rows:
                            for button in row.buttons:
                                if "Veo" in button.text or "⭕️" in button.text:
                                    veo_button = button
                                    break
                            if veo_button:
                                break
                        
                        if veo_button:
                            logger.info("[VEO Thread %s] Нажимаю кнопку: %s", thread_id, veo_button.text)
                            button_data = getattr(veo_button, "data", None)
                            if button_data:
                                await client(GetBotCallbackAnswerRequest(
                                    peer=bot_username,
                                    msg_id=response.id,
                                    data=button_data
                                ))
                            else:
                                await conv.send_message(veo_button.text)
                            logger.info("[VEO Thread %s] Кнопка Veo нажата", thread_id)
                        else:
                            logger.error("[VEO Thread %s] Кнопка Veo не найдена", thread_id)
                            return None
                    else:
                        logger.error("[VEO Thread %s] Нет inline-кнопок в ответе на /video", thread_id)
                        return None

                    # Шаг 3: Ждем подтверждение выбора режима
                    try:
                        mode_response = await conv.get_response(timeout=5)
                        logger.info("[VEO Thread %s] Получено подтверждение выбора режима", thread_id)
                    except asyncio.TimeoutError:
                        logger.warning("[VEO Thread %s] Таймаут ожидания подтверждения режима", thread_id)
                        return None

                    # Шаг 4: Отправляем изображение или текст
                    logger.info("[VEO Thread %s] Отправка %s боту...", thread_id, "текста" if text_only else "файла")
                    if text_only:
                        await conv.send_message(caption)
                    else:
                        await conv.send_file(bot, image_path, caption=caption)
                    logger.info("[VEO Thread %s] Сообщение отправлено, ожидание ответа...", thread_id)

                    try:
                        response = await conv.get_response()
                        logger.info("[VEO Thread %s] Получен первый ответ от бота", thread_id)
                    except asyncio.TimeoutError:
                        logger.error("Бот VEO не ответил в течение %s секунд", timeout)
                        return None

                    deadline = time.time() + timeout
                    timed_out = False

                    async def _handle_response(resp) -> Optional[Dict[str, Any]]:
                        nonlocal matched_prompt_fragment
                        resp_text = resp.raw_text or ""
                        fragment_raw = _extract_response_prompt_fragment(resp_text)
                        # Убрать markdown форматирование перед созданием сигнатуры
                        fragment_raw_clean = re.sub(r'\*+', '', fragment_raw).strip() if fragment_raw else None
                        fragment_signature = _normalize_prompt_signature(fragment_raw_clean)
                        # Очищенная версия caption для логирования
                        caption_clean_local = re.sub(r'\*+', '', caption).strip()
                        if fragment_raw:
                            matched_prompt_fragment = fragment_raw
                        if fragment_signature and expected_prompt_signature:
                            matches_expected = (
                                fragment_signature in expected_prompt_signature
                                or expected_prompt_signature in fragment_signature
                            )
                            if not matches_expected:
                                logger.warning(
                                    "[VEO Thread %s] Ответ относится к другому промпту, ожидаем совпадение...",
                                    thread_id
                                )
                                # Получить оригинальные промпты для отображения (уже очищенные от markdown)
                                original_expected = _take_first_sentences(caption_clean_local, 1)
                                original_received = _take_first_sentences(fragment_raw_clean, 1) if fragment_raw_clean else fragment_signature
                                logger.warning(
                                    "[VEO Thread %s] Ожидаемое первое предложение: '%s'",
                                    thread_id,
                                    original_expected
                                )
                                logger.warning(
                                    "[VEO Thread %s] Полученное первое предложение: '%s'",
                                    thread_id,
                                    original_received
                                )
                                return None
                            if fragment_raw:
                                logger.info(
                                    "[VEO Thread %s] Ответ подтвержден по промпту: %s",
                                    thread_id,
                                    fragment_raw[:120]
                                )
                        if resp_text:
                            url_match = re.search(r'https?://\S+', resp_text)
                            if url_match:
                                direct_url = url_match.group(0)
                                logger.info("Получена прямая ссылка от VEO: %s", direct_url)
                                downloaded_path = _download_url(direct_url)
                                if downloaded_path:
                                    target_signature = fragment_signature or expected_prompt_signature
                                    payload = {
                                        "success": True,
                                        "video_path": downloaded_path,
                                        "model": "veo",
                                        "cleanup_paths": [downloaded_path],
                                        "response_prompt_fragment": matched_prompt_fragment or fragment_raw or "",
                                        "prompt_signature": target_signature,
                                    }
                                    if target_signature and target_signature != expected_prompt_signature:
                                        _cache_video_response(target_signature, payload)
                                        logger.info(
                                            "[VEO Thread %s] Видео сохранено в кеш для другого промпта (%s)",
                                            thread_id,
                                            target_signature
                                        )
                                        return None
                                    return payload
                                logger.warning(
                                    "Не удалось скачать видео по ссылке %s, пробуем следующие ответы.", direct_url
                                )
                        if resp.media:
                            fd, temp_path = tempfile.mkstemp(suffix=".mp4")
                            os.close(fd)
                            downloaded = await client.download_media(resp.media, file=temp_path)
                            target_signature = fragment_signature or expected_prompt_signature
                            payload = {
                                "success": True,
                                "video_path": downloaded,
                                "model": "veo",
                                "cleanup_paths": [downloaded],
                                "response_prompt_fragment": matched_prompt_fragment or fragment_raw or "",
                                "prompt_signature": target_signature,
                            }
                            if target_signature and target_signature != expected_prompt_signature:
                                _cache_video_response(target_signature, payload)
                                logger.info(
                                    "[VEO Thread %s] Видео сохранено в кеш для другого промпта (%s)",
                                    thread_id,
                                    target_signature
                                )
                                return None
                            return payload
                        return None

                    while True:
                        result_payload = await _handle_response(response)
                        if result_payload:
                            return result_payload
                        cached_after_response = _take_cached_payload("after foreign response")
                        if cached_after_response:
                            return cached_after_response

                        remaining = deadline - time.time()
                        if remaining <= 0:
                            timed_out = True
                            break
                        try:
                            response = await conv.get_response(timeout=remaining)
                        except asyncio.TimeoutError:
                            timed_out = True
                            break

                    if timed_out:
                        logger.error("Бот VEO не прислал видео в течение %s секунд (conversation)", timeout)
                        cached_timeout_payload = _take_cached_payload("conversation timeout")
                        if cached_timeout_payload:
                            return cached_timeout_payload
                        return None

            except asyncio.TimeoutError:
                logger.error("Бот VEO не ответил в течение %s секунд (conversation)", timeout)
                cached_on_timeout = _take_cached_payload("timeout")
                if cached_on_timeout:
                    return cached_on_timeout
                return None

        finally:
            await client.disconnect()
            if os.path.exists(thread_session_file):
                try:
                    with _telethon_session_lock(source_session_file):
                        shutil.copy2(thread_session_file, source_session_file)
                        logger.info(
                            "[VEO Thread %s] Сессия потока синхронизирована обратно в базовую",
                            thread_id
                        )
                except Exception as sync_exc:
                    logger.warning(
                        "[VEO Thread %s] Не удалось обновить базовую сессию: %s",
                        thread_id,
                        sync_exc
                    )

    try:
        video_payload = asyncio.run(_veo_coroutine())
    except Exception as exc:
        logger.error("Ошибка общения с ботом VEO: %s", exc, exc_info=True)
        return {"success": False, "error": str(exc)}
    finally:
        for temp_path in cleanup_session_files:
            if not temp_path:
                continue
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    if temp_path.endswith(".session"):
                        logger.info("[VEO] Удалена временная сессия: %s", temp_path)
                except OSError:
                    pass

    if not video_payload:
        cached_fallback = _pop_video_response(expected_prompt_signature)
        if cached_fallback:
            video_payload = cached_fallback

    if video_payload:
        video_payload.pop("prompt_signature", None)

    video_path = (video_payload or {}).get("video_path") if video_payload else None
    prompt_fragment = (video_payload or {}).get("response_prompt_fragment")
    if not video_path or not os.path.exists(video_path):
        return {"success": False, "error": "Не удалось получить видео от VEO"}

    return {
        "success": True,
        "video_path": video_path,
        "model": "veo",
        "cleanup_paths": video_payload.get("cleanup_paths") if video_payload else [video_path],
        "response_prompt_fragment": prompt_fragment,
    }


def _download_url(url: str) -> Optional[str]:
    try:
        video_timeout = get_video_generation_timeout()
        response = requests.get(url, timeout=video_timeout)
        response.raise_for_status()
        fd, temp_path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, "wb") as tmp_file:
            tmp_file.write(response.content)
        return temp_path
    except Exception as exc:
        logger.error("Не удалось скачать файл %s: %s", url, exc)
        return None


def _extract_video_path(value: Any, download_func) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, str):
        candidate = value.strip()
        if candidate.startswith("file="):
            candidate = candidate.split("file=", 1)[1].split(";", 1)[0]
        if candidate.startswith("http"):
            return download_func(candidate)
        if os.path.exists(candidate):
            return candidate
        return None

    if isinstance(value, (list, tuple)):
        for item in value:
            path = _extract_video_path(item, download_func)
            if path:
                return path
        return None

    if isinstance(value, dict):
        for key in ("video", "videos", "result", "data", "value", "output", "outputs"):
            if key in value:
                path = _extract_video_path(value[key], download_func)
                if path:
                    return path
        for nested in value.values():
            path = _extract_video_path(nested, download_func)
            if path:
                return path
        return None

    for attr in ("data", "value"):
        if hasattr(value, attr):
            path = _extract_video_path(getattr(value, attr), download_func)
            if path:
                return path

    return None
