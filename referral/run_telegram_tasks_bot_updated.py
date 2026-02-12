# core/management/commands/run_telegram_tasks_bot.py
# ИЗМЕНЕНИЯ: добавлено ветвление /start для ref_* vs tenant deeplink
# Ищи блоки "# REFERRAL:" чтобы найти все изменения

import asyncio
import base64
import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from core.models import TelegramTask
from core.telegram_bot.dependencies import get_telegram_user_service, init_dependencies
from core.telegram_bot.meetings import meetings_router, send_meetings, get_binding_meeting_keyboard
from core.telegram_bot.ui import main_menu, MEETINGS_BUTTON_TEXT, WELCOME_BUTTON_TEXT
from core.services.chain_executor import ChainExecutor
from core.tasks.chains import chains_send_delayed_message, chains_check_timeout, CHAIN_BUTTON_PREFIX

# REFERRAL: импорт моделей
from core.referral import ReferralCode, Referral


logger = logging.getLogger(__name__)
debug_logger = logging.getLogger('telegram_bot_debug')
router = Router()

SUPPORT_CHAT = -5038963606


# ---------------------------------------------------------------------------
# States (без изменений)
# ---------------------------------------------------------------------------

class SupportFlowStates(StatesGroup):
    waiting_for_message = State()


class ServiceLevelStates(StatesGroup):
    waiting_for_rating = State()
    waiting_for_improvement = State()


# ---------------------------------------------------------------------------
# Helpers (без изменений)
# ---------------------------------------------------------------------------

def decode_start_param(start_param: str) -> dict:
    """Decode Telegram deep link parameter from /start."""
    try:
        padding = 4 - len(start_param) % 4
        if padding != 4:
            start_param += "=" * padding
        decoded = base64.urlsafe_b64decode(start_param)
        return json.loads(decoded)
    except Exception as exc:
        raise ValueError(f"Invalid start parameter: {exc}") from exc


# ---------------------------------------------------------------------------
# REFERRAL: новые функции ветвления
# ---------------------------------------------------------------------------

async def handle_referral_link(message: Message, start_param: str) -> None:
    """
    Обрабатывает /start ref_XXXXXXXX.
    Находит ReferralCode, создаёт Referral, уведомляет пригласившего.
    """
    from_user = message.from_user

    # Проверяем код
    try:
        referral_code = await sync_to_async(
            ReferralCode.objects.select_related("client").get,
            thread_sensitive=True,
        )(code=start_param, is_active=True)
    except ReferralCode.DoesNotExist:
        await message.answer("❌ Реферальная ссылка недействительна или устарела.")
        return

    # Защита от самоприглашения
    telegram_user_service = get_telegram_user_service()
    existing_binding = await sync_to_async(
        telegram_user_service.get_active_binding,
        thread_sensitive=True,
    )(from_user.id)

    if existing_binding is not None:
        if existing_binding.tenant_id == referral_code.client_id:
            await message.answer(
                "ℹ️ Вы уже подключены к этому клиенту.",
                reply_markup=main_menu(),
            )
        else:
            await message.answer(
                "ℹ️ Вы уже зарегистрированы. Реферальная ссылка действует только для новых пользователей.",
                reply_markup=main_menu(),
            )
        return

    # Создаём запись Referral (pending — до привязки к tenant)
    await sync_to_async(Referral.objects.create, thread_sensitive=True)(
        referral_code=referral_code,
        referrer=referral_code.client,
        invited_telegram_id=from_user.id,
        invited_telegram_username=from_user.username or "",
        expires_at=timezone.now() + timedelta(days=30),
    )

    # Уведомляем пользователя
    await message.answer(
        "🎁 Вы перешли по реферальной ссылке!\n\n"
        "После подключения вы и пригласивший вас получите бонус — бесплатный месяц подписки.\n\n"
        "Используйте вашу персональную ссылку от администратора для привязки аккаунта.",
        reply_markup=main_menu(),
    )

    # Уведомляем пригласившего — ищем его binding напрямую через модель
    try:
        from core.models import UserTenantBinding

        referrer_binding = await sync_to_async(
            UserTenantBinding.objects
            .filter(tenant_id=referral_code.client_id, is_active=True)
            .order_by("-bound_at")
            .first,
            thread_sensitive=True,
        )()

        if referrer_binding:
            await message.bot.send_message(
                chat_id=referrer_binding.telegram_chat_id,
                text=(
                    f"🎉 По вашей реферальной ссылке перешёл пользователь "
                    f"@{from_user.username or from_user.id}!\n\n"
                    f"После его привязки вы оба получите бонус."
                ),
            )
    except Exception:
        logger.exception("Failed to notify referrer (client_id=%s)", referral_code.client_id)


async def handle_tenant_deeplink(message: Message, start_param: str) -> None:
    """
    Обрабатывает /start base64payload (обычный deeplink от TenantService).
    Вынесена из handle_start_with_deeplink для читаемости.
    """
    from_user = message.from_user

    try:
        payload = decode_start_param(start_param)
        tenant_id = payload.get("tid")
        contact_id = payload.get("cid")

        if not tenant_id:
            await message.answer("❌ Неверная ссылка. Свяжитесь с администратором.")
            return
        try:
            tenant_id = int(tenant_id)
        except (TypeError, ValueError):
            await message.answer("❌ Неверная ссылка. Свяжитесь с администратором.")
            return

        if contact_id is not None:
            try:
                contact_id = int(contact_id)
            except (TypeError, ValueError):
                await message.answer("❌ Неверная ссылка. Свяжитесь с администратором.")
                return

        telegram_user_service = get_telegram_user_service()
        result = await sync_to_async(
            telegram_user_service.bind_user_to_tenant,
            thread_sensitive=True,
        )(
            telegram_chat_id=from_user.id,
            tenant_id=tenant_id,
            contact_id=contact_id,
            telegram_username=from_user.username,
        )

        if result["status"] == "newly_bound":
            # REFERRAL: если был pending Referral для этого telegram_id — закрываем его
            await _complete_pending_referral(from_user.id, tenant_id, message)

            await message.answer(
                "✅ Вы успешно подключены к клиенту!\n"
                "Добро пожаловать!",
                reply_markup=main_menu(),
            )
            await message.answer(
                "Запланируем встречу?",
                reply_markup=get_binding_meeting_keyboard(),
            )
        else:
            await message.answer(
                "ℹ️ Вы уже подключены к этому клиенту.\n"
                "Можете продолжить работу.",
                reply_markup=main_menu(),
            )

    except ValueError:
        await message.answer(
            "❌ Неверная ссылка. Пожалуйста, получите новую ссылку от администратора.",
            reply_markup=main_menu(),
        )
    except Exception:
        logger.exception("Failed to bind Telegram user (user_id=%s)", from_user.id)
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже или свяжитесь с поддержкой.",
            reply_markup=main_menu(),
        )


async def _complete_pending_referral(telegram_id: int, tenant_id: int, message: Message) -> None:
    """
    Если у пользователя есть pending Referral — закрываем его после привязки к tenant.
    Здесь можно добавить логику выдачи наград (bonus_days и т.д.).
    """
    try:
        from core.models import Client

        referee_client = await sync_to_async(
            Client.objects.get,
            thread_sensitive=True,
        )(id=tenant_id)

        referral = await sync_to_async(
            Referral.objects.select_related("referral_code__client")
            .filter(
                invited_telegram_id=telegram_id,
                status=Referral.STATUS_PENDING,
            )
            .first,
            thread_sensitive=True,
        )()

        if referral is None:
            return

        await sync_to_async(referral.mark_registered, thread_sensitive=True)(referee_client)
        await sync_to_async(referral.mark_rewarded, thread_sensitive=True)()

        # Уведомляем пригласившего о завершении
        from core.models import UserTenantBinding

        referrer_binding = await sync_to_async(
            UserTenantBinding.objects
            .filter(tenant_id=referral.referrer_id, is_active=True)
            .order_by("-bound_at")
            .first,
            thread_sensitive=True,
        )()

        if referrer_binding:
            await message.bot.send_message(
                chat_id=referrer_binding.telegram_chat_id,
                text=(
                    "✅ Ваш реферал успешно зарегистрировался!\n\n"
                    "🎁 Вы получили бонус — бесплатный месяц подписки."
                ),
            )

        await message.answer(
            "🎁 Реферальный бонус активирован! Вы получили бесплатный месяц подписки."
        )

    except Exception:
        logger.exception("Failed to complete pending referral (telegram_id=%s)", telegram_id)


# ---------------------------------------------------------------------------
# /start  (ИЗМЕНЕНО: ветвление ref_* vs tenant deeplink)
# ---------------------------------------------------------------------------

@router.message(CommandStart(deep_link=True))
async def handle_start_with_deeplink(message: Message, command: CommandObject) -> None:
    if message.chat.type != "private":
        return

    from_user = message.from_user
    if from_user is None:
        return

    start_param = command.args or ""
    if not start_param:
        await message.answer("❌ Неверная ссылка. Свяжитесь с администратором.")
        return

    # REFERRAL: ветвление
    if ReferralCode.is_referral_code(start_param):
        await handle_referral_link(message, start_param)
    else:
        await handle_tenant_deeplink(message, start_param)


@router.message(CommandStart(deep_link=False))
async def handle_start_without_deeplink(message: Message) -> None:
    if message.chat.type != "private":
        return

    await message.answer(
        "👋 Добро пожаловать!\n\n"
        "Для начала работы вам нужна персональная ссылка.\n"
        "Игнорируйте, если уже вводили и ничего не изменилось",
        reply_markup=main_menu(),
    )


# ---------------------------------------------------------------------------
# Остальные хендлеры — без изменений (support, level, meetings, message, etc.)
# ---------------------------------------------------------------------------

def _store_task(
    *,
    telegram_id: int,
    username: str | None,
    message_id: int | None,
    message_text: str,
    received_at: datetime,
    rating: int | None = None,
    improvement: str | None = None,
) -> bool:
    telegram_user_service = get_telegram_user_service()
    binding = telegram_user_service.get_active_binding(telegram_id)
    if binding is None:
        return False

    tg_name = username or f"tg_{telegram_id}"
    stored_text = message_text
    if improvement is not None:
        stored_text = improvement

    TelegramTask.objects.create(
        client=binding.tenant,
        tg_name=tg_name,
        telegram_user_id=telegram_id,
        telegram_message_id=message_id,
        message_text=stored_text,
        received_at=received_at,
        rating=rating,
    )
    return True


def _normalize_buttons(buttons: list) -> list[str]:
    normalized = []
    for btn in buttons or []:
        if isinstance(btn, str):
            label = btn
        else:
            label = (btn or {}).get("text")
        if label:
            normalized.append(label)
    return normalized


def _build_chain_keyboard(buttons: list[str]) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=label, callback_data=f"{CHAIN_BUTTON_PREFIX}{label}")]
        for label in buttons
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def _execute_chain_actions(*, bot, chat_id, session_id, actions):
    for action in actions:
        action_type = action.get("action_type")
        payload = action.get("payload", {})
        delay_seconds = int(action.get("delay_seconds", 0) or 0)

        if action_type in {"send_text", "send_photo", "send_buttons"} and delay_seconds > 0:
            node_id = payload.get("node_id")
            if session_id and node_id:
                chains_send_delayed_message.apply_async(
                    args=[session_id, node_id],
                    countdown=delay_seconds,
                )
            continue

        if action_type == "send_text":
            await bot.send_message(chat_id, text=payload.get("text", ""))
        elif action_type == "send_photo":
            await bot.send_photo(
                chat_id,
                photo=payload.get("photo_url"),
                caption=payload.get("caption", ""),
            )
        elif action_type == "send_buttons":
            buttons = _normalize_buttons(payload.get("buttons", []))
            await bot.send_message(
                chat_id,
                text=payload.get("text", ""),
                reply_markup=_build_chain_keyboard(buttons),
            )
        elif action_type == "schedule_timeout":
            chains_check_timeout.apply_async(
                args=[payload.get("session_id"), payload.get("edge_id")],
                countdown=int(payload.get("timeout_seconds", 300)),
            )


async def _get_binding_for_user(telegram_id: int):
    telegram_user_service = get_telegram_user_service()
    return await sync_to_async(
        telegram_user_service.get_active_binding,
        thread_sensitive=True,
    )(telegram_id)


# ---------------------------------------------------------------------------
# Bot bootstrap (без изменений)
# ---------------------------------------------------------------------------

async def _run_bot(token: str) -> None:
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO)

    debug_handler = _logging.StreamHandler()
    debug_formatter = _logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    debug_handler.setFormatter(debug_formatter)
    debug_logger.addHandler(debug_handler)
    debug_logger.setLevel(_logging.INFO)

    bot = Bot(token=token)
    await bot.set_my_commands(
        [
            BotCommand(command="meetings", description="Показать запланированные встречи"),
            BotCommand(command="level", description="Оценить уровень сервиса"),
            BotCommand(command="support", description="Связаться с поддержкой"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    dispatcher.include_router(meetings_router)

    debug_logger.info("Starting Telegram bot polling...")
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

        init_dependencies()
        self.stdout.write(self.style.SUCCESS("Starting Telegram tasks bot with DEBUG logging..."))
        debug_logger.info("Telegram bot starting with debug logging enabled")
        asyncio.run(_run_bot(token))
