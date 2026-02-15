from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from aiogram import Bot
from django.conf import settings

from core.ai_generator import AIContentGenerator
from core.system_settings import get_default_ai_model

try:
    from telethon import TelegramClient
    from telethon.errors import AuthKeyUnregisteredError
except ImportError:  # pragma: no cover - defensive fallback
    TelegramClient = None  # type: ignore[assignment]
    AuthKeyUnregisteredError = RuntimeError  # type: ignore[assignment]


logger = logging.getLogger(__name__)
_SESSION_COPY_LOCK = threading.Lock()


@dataclass
class VoiceTranscriptionResult:
    text: Optional[str]
    error: Optional[str] = None
    confirmation_received: bool = False


def _resolve_api_credentials() -> tuple[int, str]:
    api_id_raw = (getattr(settings, "TELEGRAM_API_ID", "") or os.getenv("TELEGRAM_API_ID") or "").strip()
    api_hash = (getattr(settings, "TELEGRAM_API_HASH", "") or os.getenv("TELEGRAM_API_HASH") or "").strip()
    if not api_id_raw or not api_hash:
        raise RuntimeError("TELEGRAM_API_ID/TELEGRAM_API_HASH are not configured")
    try:
        api_id = int(api_id_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("TELEGRAM_API_ID must be an integer") from exc
    return api_id, api_hash


def _normalize_session_base(value: str) -> Path:
    candidate = Path((value or "").strip()).expanduser()
    if not candidate.is_absolute():
        candidate = Path(settings.BASE_DIR) / candidate
    if candidate.suffix == ".session":
        candidate = candidate.with_suffix("")
    return candidate


def _iter_session_candidates() -> list[Path]:
    env_candidates = [
        os.getenv("SBER_TRANSCRIBE_SESSION_NAME"),
        os.getenv("SBER_TRANSCRIBE_SESSION_PATH"),
        os.getenv("VEO_SESSION_PATH"),
        os.getenv("GIGA_BOT_SESSION_PATH"),
        "telegram_sessions/session_publisher_client_3",
        "telegram_sessions/session_collector_client_3",
    ]

    candidates: list[Path] = []
    for raw in env_candidates:
        if raw:
            candidates.append(_normalize_session_base(raw))

    sessions_dir = Path(settings.BASE_DIR) / "telegram_sessions"
    if sessions_dir.exists():
        for session_file in sorted(sessions_dir.glob("*.session")):
            candidates.append(session_file.with_suffix(""))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _resolve_session_base() -> Path:
    for base in _iter_session_candidates():
        if base.with_suffix(".session").exists():
            return base
    raise RuntimeError("No authorized Telethon session found in backend/telegram_sessions")


def _cleanup_session_files(session_base: Path) -> None:
    for suffix in (".session", ".session-journal"):
        try:
            path = session_base.with_name(session_base.name + suffix)
            if path.exists():
                path.unlink()
        except Exception:
            logger.debug("Failed to cleanup temporary session file: %s", session_base, exc_info=True)


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower().replace("ё", "е"))


def _is_service_text(normalized_text: str) -> bool:
    if not normalized_text:
        return True
    service_markers = (
        "аудиосообщение принято",
        "обрабаты",
        "распозна",
        "пришлите",
        "отправьте",
        "попробуйте",
    )
    return len(normalized_text) <= 220 and any(marker in normalized_text for marker in service_markers)


def _build_cleanup_prompt(raw_text: str) -> str:
    return (
        "Очисти транскрибированную речь от слов-паразитов, междометий и повторов. "
        "Сохрани смысл, факты, числа и формулировки максимально близко к оригиналу. "
        "Не добавляй новую информацию.\n\n"
        "Верни только очищенный текст без пояснений.\n\n"
        f"Текст:\n{raw_text}"
    )


def _clean_transcription_sync(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if not text:
        return ""

    try:
        model_name = get_default_ai_model()
        generator = AIContentGenerator()
        response = generator.get_ai_response(
            prompt=_build_cleanup_prompt(text),
            max_tokens=1600,
            temperature=0.1,
            model=model_name,
            allow_fallback=True,
            timeout_seconds=45.0,
        )
        cleaned = (response or "").strip()
        return cleaned or text
    except Exception:
        logger.exception("Failed to clean transcription via default AI model")
        return text


async def clean_transcription_with_default_ai(raw_text: str) -> str:
    return await asyncio.to_thread(_clean_transcription_sync, raw_text)


class TelegramVoiceTranscriber:
    def __init__(
        self,
        *,
        target_bot_username: str = "smartspeech_sber_bot",
        timeout_seconds: int = 90,
    ) -> None:
        self.target_bot_username = target_bot_username.lstrip("@")
        self.timeout_seconds = max(20, int(timeout_seconds))

    async def _download_voice(self, bot: Bot, voice_file_id: str) -> Path:
        fd, temp_path = tempfile.mkstemp(prefix="tg_voice_", suffix=".ogg")
        os.close(fd)
        await bot.download(voice_file_id, destination=temp_path)
        return Path(temp_path)

    async def _wait_transcription(self, conv, timeout_seconds: int) -> tuple[Optional[str], bool]:
        deadline = time.monotonic() + timeout_seconds
        confirmation_received = False

        while time.monotonic() < deadline:
            remaining = max(1, int(deadline - time.monotonic()))
            try:
                response = await conv.get_response(timeout=remaining)
            except asyncio.TimeoutError:
                break

            text = (getattr(response, "raw_text", None) or "").strip()
            if not text:
                continue

            normalized = _normalize_text(text)
            if "аудиосообщение принято" in normalized:
                confirmation_received = True
                continue

            if not confirmation_received and _is_service_text(normalized):
                continue

            return text, confirmation_received

        return None, confirmation_received

    async def _wait_transcription_polling(
        self,
        *,
        client: TelegramClient,
        bot_entity,
        min_message_id: int,
        timeout_seconds: int,
    ) -> tuple[Optional[str], bool]:
        deadline = time.monotonic() + timeout_seconds
        confirmation_received = False
        last_text_by_id: dict[int, str] = {}

        while time.monotonic() < deadline:
            history = await client.get_messages(bot_entity, limit=20)
            for msg in reversed(history):
                msg_id = int(getattr(msg, "id", 0) or 0)
                if msg_id <= min_message_id:
                    continue

                # Интересуют только сообщения от бота
                if getattr(msg, "out", False):
                    continue

                text = (getattr(msg, "raw_text", None) or "").strip()
                prev_text = last_text_by_id.get(msg_id)
                # Критично для SmartSpeech: он может редактировать одно и то же сообщение.
                # Поэтому обрабатываем повторно только если текст изменился.
                if prev_text is not None and prev_text == text:
                    continue
                if prev_text is not None and prev_text != text:
                    logger.warning(
                        "SmartSpeech message edited: id=%s old=%s new=%s",
                        msg_id,
                        prev_text[:120],
                        text[:120],
                    )
                last_text_by_id[msg_id] = text

                if not text:
                    continue

                normalized = _normalize_text(text)
                if "аудиосообщение принято" in normalized:
                    confirmation_received = True
                    continue

                if not confirmation_received and _is_service_text(normalized):
                    continue

                return text, confirmation_received

            await asyncio.sleep(1.0)

        return None, confirmation_received

    async def transcribe_voice(
        self,
        *,
        bot: Bot,
        voice_file_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> VoiceTranscriptionResult:
        if TelegramClient is None:
            return VoiceTranscriptionResult(text=None, error="Telethon is not installed")

        effective_timeout = timeout_seconds or self.timeout_seconds
        voice_path: Optional[Path] = None
        client = None
        thread_session_base: Optional[Path] = None

        try:
            api_id, api_hash = _resolve_api_credentials()
            source_session_base = _resolve_session_base()
            voice_path = await self._download_voice(bot, voice_file_id)

            thread_session_base = source_session_base.parent / (
                f"{source_session_base.name}_voice_{uuid.uuid4().hex[:8]}"
            )

            with _SESSION_COPY_LOCK:
                shutil.copy2(
                    source_session_base.with_suffix(".session"),
                    thread_session_base.with_suffix(".session"),
                )

            client = TelegramClient(str(thread_session_base), api_id, api_hash)
            await client.connect()

            if not await client.is_user_authorized():
                return VoiceTranscriptionResult(
                    text=None,
                    error="Telethon session is not authorized",
                )

            me = await client.get_me()
            logger.warning(
                "Voice transcription via Telethon session=%s account_id=%s username=%s",
                source_session_base,
                getattr(me, "id", None),
                getattr(me, "username", None),
            )
            if getattr(me, "bot", False):
                return VoiceTranscriptionResult(
                    text=None,
                    error="Configured Telethon session is authorized as a bot, user session is required",
                )

            bot_entity = await client.get_entity(f"@{self.target_bot_username}")
            sent_message_id = 0

            async with client.conversation(bot_entity, timeout=effective_timeout) as conv:
                # Как и в VEO, явно "будим" диалог с ботом перед рабочим сообщением.
                try:
                    await conv.send_message("/start")
                    await conv.get_response(timeout=5)
                except Exception:
                    logger.debug("Failed to warm up conversation with @%s", self.target_bot_username, exc_info=True)

                sent_message = await conv.send_file(str(voice_path), voice_note=True)
                sent_message_id = int(getattr(sent_message, "id", 0) or 0)
                logger.warning(
                    "Voice file sent to @%s: message_id=%s",
                    self.target_bot_username,
                    sent_message_id,
                )
                logger.info("Waiting for transcription via polling (Sber Bot edits messages)")
                text, confirmation_received = await self._wait_transcription_polling(
                    client=client,
                    bot_entity=bot_entity,
                    min_message_id=sent_message_id,
                    timeout_seconds=effective_timeout,
                )

            if not text:
                return VoiceTranscriptionResult(
                    text=None,
                    error="No transcription response from SmartSpeech bot",
                    confirmation_received=confirmation_received,
                )
            return VoiceTranscriptionResult(
                text=text,
                confirmation_received=confirmation_received,
            )
        except AuthKeyUnregisteredError as exc:
            logger.exception("Telethon session authorization key is invalid")
            return VoiceTranscriptionResult(text=None, error=f"Telethon session is invalid: {exc}")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Voice transcription failed")
            return VoiceTranscriptionResult(text=None, error=str(exc))
        finally:
            if client is not None:
                try:
                    await client.disconnect()
                except Exception:
                    logger.debug("Failed to disconnect telethon client", exc_info=True)

            if voice_path and voice_path.exists():
                try:
                    voice_path.unlink()
                except Exception:
                    logger.debug("Failed to cleanup downloaded voice file: %s", voice_path, exc_info=True)

            if thread_session_base is not None:
                _cleanup_session_files(thread_session_base)
