import asyncio
import logging
from datetime import datetime

from asgiref.sync import sync_to_async
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command
from aiogram.types import Message

from core.models import Client, TelegramTask, UserTenantRole


logger = logging.getLogger(__name__)
router = Router()
SUPPORT_CHAT = "@pavel_architect"


def _get_or_create_client_for_user(
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
) -> tuple[str, Client]:
    User = get_user_model()
    fallback_username = f"tg_{telegram_id}"
    candidate_usernames = [name for name in [username, fallback_username] if name]

    user = (
        User.objects.filter(username__in=candidate_usernames)
        .order_by("id")
        .first()
    )

    display_name = " ".join(part for part in [first_name, last_name] if part).strip()
    primary_username = username or fallback_username

    if user is None:
        user = User.objects.create(
            username=primary_username,
            first_name=first_name or "",
            last_name=last_name or "",
            email=f"{primary_username}@telegram.local",
        )
    else:
        needs_update = False
        if first_name is not None and user.first_name != first_name:
            user.first_name = first_name
            needs_update = True
        if last_name is not None and user.last_name != last_name:
            user.last_name = last_name
            needs_update = True
        if needs_update:
            user.save(update_fields=["first_name", "last_name"])

    role = (
        UserTenantRole.objects.select_related("client")
        .filter(user=user)
        .order_by("id")
        .first()
    )
    if role:
        return primary_username, role.client

    client, _ = Client.objects.get_or_create(
        slug=str(telegram_id),
        defaults={"name": display_name or username or f"User {telegram_id}"},
    )
    UserTenantRole.objects.get_or_create(
        user=user,
        client=client,
        defaults={"role": "owner"},
    )
    return primary_username, client


def _store_task(
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    message_id: int | None,
    message_text: str,
    received_at: datetime,
) -> None:
    tg_name, client = _get_or_create_client_for_user(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
    )

    TelegramTask.objects.create(
        client=client,
        tg_name=tg_name,
        telegram_user_id=telegram_id,
        telegram_message_id=message_id,
        message_text=message_text,
        received_at=received_at,
    )


@router.message()
async def handle_message(message: Message) -> None:
    if message.chat.type != "private":
        return

    from_user = message.from_user
    if from_user is None:
        return

    if message.text and message.text.lstrip().startswith("/"):
        return

    message_text = (message.text or message.caption or "").strip()
    if not message_text:
        return

    received_at = message.date or timezone.now()
    if timezone.is_naive(received_at):
        received_at = timezone.make_aware(received_at)

    try:
        await sync_to_async(_store_task, thread_sensitive=True)(
            telegram_id=from_user.id,
            username=from_user.username,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            message_id=message.message_id,
            message_text=message_text,
            received_at=received_at,
        )
    except Exception:
        logger.exception("Failed to store Telegram task (user_id=%s)", from_user.id)


@router.message(Command("support"))
async def handle_support(message: Message, bot: Bot) -> None:
    if message.chat.type != "private":
        return

    try:
        await bot.forward_message(
            chat_id=SUPPORT_CHAT,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer("Сообщение отправлено в поддержку.")
    except Exception:
        logger.exception("Failed to forward support message (chat_id=%s)", message.chat.id)
        await message.answer("Не удалось отправить сообщение в поддержку.")


async def _run_bot(token: str) -> None:
    bot = Bot(token=token)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    await dispatcher.start_polling(
        bot,
        allowed_updates=dispatcher.resolve_used_update_types(),
    )


class Command(BaseCommand):
    help = "Run Telegram bot that stores incoming messages as tasks."

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or ""
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set")

        self.stdout.write(self.style.SUCCESS("Starting Telegram tasks bot..."))
        asyncio.run(_run_bot(token))
