from __future__ import annotations

import logging
import os
import re
from datetime import datetime

from asgiref.sync import sync_to_async
from django.db import connection
from django.utils import timezone

from aiogram import F, Router
from aiogram.types import Message

from core.telegram_bot.dependencies import get_telegram_user_service
from core.telegram_bot.voice_transcription import (
    TelegramVoiceTranscriber,
    clean_transcription_with_default_ai,
)


logger = logging.getLogger(__name__)
voice_router = Router()


def _map_schema() -> str:
    schema = os.getenv("MAP_SCHEMA", "map").strip()
    if not schema or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", schema):
        return "map"
    return schema


def _save_note(*, contact_id: int, title: str, content: str) -> int:
    schema = _map_schema()
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {schema}.crm_notes (contact_id, title, content, is_important)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            [contact_id, title, content, False],
        )
        row = cursor.fetchone()
    if not row:
        raise RuntimeError("Failed to save note")
    return int(row[0])


async def _get_binding(telegram_user_id: int):
    telegram_user_service = get_telegram_user_service()
    return await sync_to_async(
        telegram_user_service.get_active_binding,
        thread_sensitive=True,
    )(telegram_user_id)


def _format_note_title(message_dt: datetime | None) -> str:
    dt = message_dt or timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt)
    local_dt = timezone.localtime(dt)
    return f"Telegram voice {local_dt.strftime('%d.%m.%Y %H:%M')}"


@voice_router.message(F.voice)
async def handle_voice_message(message: Message) -> None:
    if message.chat.type != "private":
        return

    from_user = message.from_user
    if from_user is None or message.voice is None:
        return

    binding = await _get_binding(from_user.id)
    if binding is None:
        await message.answer(
            "❗️Ваш аккаунт ещё не привязан к клиенту.\n"
            "Пожалуйста, используйте персональную ссылку от администратора.",
        )
        return

    if not binding.contact_id:
        await message.answer(
            "❗️Аккаунт привязан, но контакт не указан.\n"
            "Попросите администратора отправить новую ссылку.",
        )
        return

    status_message = await message.answer("Голосовое принято")

    try:
        transcriber = TelegramVoiceTranscriber()
        result = await transcriber.transcribe_voice(
            bot=message.bot,
            voice_file_id=message.voice.file_id,
        )
        if not result.text:
            await status_message.edit_text("❌ Ошибка")
            return

        cleaned_text = (await clean_transcription_with_default_ai(result.text)).strip() or result.text.strip()
        await sync_to_async(_save_note, thread_sensitive=True)(
            contact_id=int(binding.contact_id),
            title=_format_note_title(message.date),
            content=cleaned_text,
        )

        await status_message.edit_text(
            "✅ Расшифровка сохранена\n\n"
            f"{cleaned_text}"
        )
    except Exception:  # noqa: BLE001
        logger.exception("Voice handling failed for user_id=%s", from_user.id)
        await status_message.edit_text("❌ Ошибка")
