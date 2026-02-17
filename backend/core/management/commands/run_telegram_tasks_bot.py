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

from core.models import CRMTask, TelegramTask
from core.telegram_bot.dependencies import get_telegram_user_service, init_dependencies
from core.telegram_bot.meetings import meetings_router, send_meetings, get_binding_meeting_keyboard
from core.telegram_bot.voice_handlers import voice_router
from core.telegram_bot.ui import main_menu, MEETINGS_BUTTON_TEXT, WELCOME_BUTTON_TEXT
from core.services.chain_executor import ChainExecutor
from core.tasks.chains import chains_send_delayed_message, chains_check_timeout, CHAIN_BUTTON_PREFIX

# Referral
from core.referral import Referral, ReferralCode, reward_referral_month


logger = logging.getLogger(__name__)
debug_logger = logging.getLogger('telegram_bot_debug')
router = Router()

SUPPORT_CHAT = -5038963606  # Групповой чат для уведомлений поддержки


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------

class SupportFlowStates(StatesGroup):
    waiting_for_message = State()


class ServiceLevelStates(StatesGroup):
    waiting_for_rating = State()
    waiting_for_improvement = State()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def decode_start_param(start_param: str) -> dict:
    """Decode Telegram deep link parameter from /start."""
    try:
        padding = 4 - len(start_param) % 4
        if padding != 4:
            start_param += "=" * padding
        decoded = base64.urlsafe_b64decode(start_param)
        return json.loads(decoded)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid start parameter: {exc}") from exc


# ---------------------------------------------------------------------------
# Referral helpers
# ---------------------------------------------------------------------------


async def handle_referral_link(message: Message, start_param: str) -> None:
    """
    Обрабатывает /start ref_XXXXXXXX.
    Находит ReferralCode, создаёт Referral, уведомляет пригласившего.
    """
    from_user = message.from_user
    if from_user is None:
        return

    try:
        referral_code = await sync_to_async(
            ReferralCode.objects.select_related("client").get,
            thread_sensitive=True,
        )(code=start_param, is_active=True)
    except ReferralCode.DoesNotExist:
        await message.answer("❌ Реферальная ссылка недействительна или устарела.")
        return

    # Защита от самоприглашения / повторных регистраций
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

    await sync_to_async(Referral.objects.create, thread_sensitive=True)(
        referral_code=referral_code,
        referrer=referral_code.client,
        invited_telegram_id=from_user.id,
        invited_telegram_username=from_user.username or "",
        expires_at=timezone.now() + timedelta(days=30),
    )

    await message.answer(
        "🎁 Вы перешли по реферальной ссылке!\n\n"
        "После подключения вы и пригласивший вас получите бонус — бесплатный месяц подписки.\n\n"
        "Используйте вашу персональную ссылку от администратора для привязки аккаунта.",
        reply_markup=main_menu(),
    )

    # Уведомляем пригласившего — прямой запрос по binding (метода в сервисе нет)
    try:
        from core.models import UserTenantBinding

        referrer_binding = await sync_to_async(
            UserTenantBinding.objects.filter(tenant_id=referral_code.client_id, is_active=True)
            .order_by("-bound_at")
            .first,
            thread_sensitive=True,
        )()
        if referrer_binding:
            await message.bot.send_message(
                chat_id=referrer_binding.telegram_chat_id,
                text=(
                    "🎉 По вашей реферальной ссылке перешёл пользователь "
                    f"@{from_user.username or from_user.id}!\n\n"
                    "После его привязки вы оба получите бонус."
                ),
            )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to notify referrer (client_id=%s)", referral_code.client_id)


async def _complete_pending_referral(telegram_id: int, tenant_id: int, message: Message) -> None:
    """
    Если у пользователя есть pending Referral — закрываем его после привязки к tenant
    и начисляем бонус обоим (по бесплатному месяцу).
    """
    try:
        from core.models import Client, UserTenantBinding

        referee_client = await sync_to_async(
            Client.objects.get,
            thread_sensitive=True,
        )(id=tenant_id)

        referral = await sync_to_async(
            Referral.objects.select_related("referral_code__client", "referrer")
            .filter(invited_telegram_id=telegram_id, status=Referral.STATUS_PENDING)
            .first,
            thread_sensitive=True,
        )()
        if referral is None:
            return

        await sync_to_async(referral.mark_registered, thread_sensitive=True)(referee_client)
        await sync_to_async(reward_referral_month, thread_sensitive=True)(
            referrer=referral.referrer,
            referee=referee_client,
        )
        await sync_to_async(referral.mark_rewarded, thread_sensitive=True)()

        referrer_binding = await sync_to_async(
            UserTenantBinding.objects.filter(tenant_id=referral.referrer_id, is_active=True)
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

        await message.answer("🎁 Реферальный бонус активирован! Вы получили бесплатный месяц подписки.")

    except Exception:  # noqa: BLE001
        logger.exception("Failed to complete pending referral (telegram_id=%s)", telegram_id)


async def handle_tenant_deeplink(message: Message, start_param: str) -> None:
    """
    Обрабатывает /start base64payload (обычный deeplink от TenantService).
    Вынесено из handle_start_with_deeplink для читаемости.
    """
    from_user = message.from_user
    if from_user is None:
        return

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
    except Exception:  # noqa: BLE001
        logger.exception("Failed to bind Telegram user (user_id=%s)", from_user.id)
        await message.answer(
            "❌ Произошла ошибка. Попробуйте позже или свяжитесь с поддержкой.",
            reply_markup=main_menu(),
        )


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

    feedback = TelegramTask.objects.create(
        client=binding.tenant,
        tg_name=tg_name,
        telegram_user_id=telegram_id,
        telegram_message_id=message_id,
        message_text=stored_text,
        received_at=received_at,
        rating=rating,
    )
    if rating is not None and rating < 8:
        CRMTask.objects.create(
            level=feedback,
            title=f"Связаться с клиентом @{tg_name} и решить вопрос",
            description=stored_text or None,
            status="open",
            priority=1,
            created_by=0,
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


async def _execute_chain_actions(
    *,
    bot: Bot,
    chat_id: int,
    session_id: int | None,
    actions: list[dict],
) -> None:
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
            await bot.send_message(chat_id, text=payload.get("text", ""), parse_mode="HTML")
        elif action_type == "send_photo":
            await bot.send_photo(
                chat_id,
                photo=payload.get("photo_url"),
                caption=payload.get("caption", ""),
                parse_mode="HTML",
            )
        elif action_type == "send_buttons":
            buttons = _normalize_buttons(payload.get("buttons", []))
            await bot.send_message(
                chat_id,
                text=payload.get("text", ""),
                reply_markup=_build_chain_keyboard(buttons),
                parse_mode="HTML",
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
# /start
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

    # Referral: ref_* vs tenant deeplink (base64)
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
# /support
# ---------------------------------------------------------------------------

@router.message(Command("support"))
async def handle_support(message: Message, bot: Bot, command: CommandObject, state: FSMContext) -> None:
    debug_logger.info(f"Received /support command from user: {message.from_user.username if message.from_user else 'Unknown'}")

    if message.chat.type != "private":
        return

    support_text = command.args if command and command.args else None

    if support_text:
        await _send_support_message(message, bot, support_text)
    else:
        await state.set_state(SupportFlowStates.waiting_for_message)
        await message.answer(
            "📝 Опишите вашу проблему или вопрос в следующем сообщении.\n\n"
            "Или используйте: /support ваш текст\n\n"
            "Для отмены отправьте /cancel"
        )


@router.message(SupportFlowStates.waiting_for_message)
async def handle_support_message(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.text and message.text.startswith('/cancel'):
        await state.clear()
        await message.answer("❌ Обращение отменено.")
        return

    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте текстовое сообщение.")
        return

    await _send_support_message(message, bot, message.text)
    await state.clear()


async def _send_support_message(message: Message, bot: Bot, support_text: str) -> None:
    user_info = []
    if message.from_user:
        if message.from_user.username:
            user_info.append(f"@{message.from_user.username}")
        if message.from_user.first_name or message.from_user.last_name:
            full_name = " ".join(filter(None, [message.from_user.first_name, message.from_user.last_name]))
            user_info.append(f"({full_name})")

    user_str = " ".join(user_info) if user_info else "Неизвестный пользователь"
    user_id = message.from_user.id if message.from_user else None

    hidden_marker = f"\n\n<code>[USER_ID:{user_id}]</code>" if user_id else ""

    notification_text = (
        "🆘 <b>Новое обращение в поддержку</b>\n\n"
        f"👤 <b>Пользователь:</b> {user_str}\n"
        f"💬 <b>Сообщение:</b>\n{support_text}"
        f"{hidden_marker}"
    )

    try:
        await bot.send_message(
            chat_id=SUPPORT_CHAT,
            text=notification_text,
            parse_mode="HTML",
        )
        await message.answer("✅ Ваше обращение отправлено в поддержку. Мы скоро с вами свяжемся!")
        debug_logger.info(f"Successfully sent support notification from {message.from_user.username if message.from_user else 'Unknown'}")
    except Exception:
        logger.exception("Failed to send support notification (chat_id=%s)", message.chat.id)
        await message.answer("❌ Не удалось отправить сообщение в поддержку. Попробуйте позже.")


# ---------------------------------------------------------------------------
# Reply в групповом чате поддержки → ответ пользователю
# ---------------------------------------------------------------------------

@router.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_any_group_message(message: Message, bot: Bot) -> None:
    debug_logger.info(
        f"Group message received: chat_id={message.chat.id}, "
        f"chat_type={message.chat.type}, "
        f"has_reply={message.reply_to_message is not None}, "
        f"text={message.text[:50] if message.text else 'no text'}"
    )

    if message.chat.id != SUPPORT_CHAT:
        return
    if not message.reply_to_message or not message.text:
        return

    replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    debug_logger.info(f"Replied message text: {replied_text[:100]}...")

    match = re.search(r'\[USER_ID:(\d+)\]', replied_text)
    if not match:
        debug_logger.warning(f"No USER_ID found in replied message. Full text: {replied_text}")
        await message.reply("⚠️ Не найден ID пользователя в этом сообщении. Возможно, это старое обращение.")
        return

    user_chat_id = int(match.group(1))
    debug_logger.info(f"Extracted user_chat_id: {user_chat_id}")

    try:
        sent = await bot.send_message(
            chat_id=user_chat_id,
            text=f"💬 <b>Ответ от поддержки:</b>\n\n{message.text}",
            parse_mode="HTML",
        )
        await message.reply("✅ Ответ отправлен пользователю")
        debug_logger.info(f"Support reply sent successfully to user_id={user_chat_id}, message_id={sent.message_id}")
    except Exception as e:
        logger.exception("Failed to send support reply to user_id=%s", user_chat_id)
        await message.reply(f"❌ Не удалось отправить ответ пользователю: {e}")


# ---------------------------------------------------------------------------
# /level — оценка сервиса
# ---------------------------------------------------------------------------

@router.message(Command("level"))
async def handle_level_command(message: Message, state: FSMContext) -> None:
    if message.chat.type != "private":
        return
    await _start_service_level_survey(message, state)


async def _start_service_level_survey(message: Message, state: FSMContext | None = None) -> None:
    if state:
        await state.set_state(ServiceLevelStates.waiting_for_rating)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1", callback_data="rating:1"),
                InlineKeyboardButton(text="2", callback_data="rating:2"),
                InlineKeyboardButton(text="3", callback_data="rating:3"),
                InlineKeyboardButton(text="4", callback_data="rating:4"),
                InlineKeyboardButton(text="5", callback_data="rating:5"),
            ],
            [
                InlineKeyboardButton(text="6", callback_data="rating:6"),
                InlineKeyboardButton(text="7", callback_data="rating:7"),
                InlineKeyboardButton(text="8", callback_data="rating:8"),
                InlineKeyboardButton(text="9", callback_data="rating:9"),
                InlineKeyboardButton(text="10", callback_data="rating:10"),
            ],
            [
                InlineKeyboardButton(text="❌ Отменить", callback_data="service_cancel"),
            ],
        ]
    )

    await message.answer(
        "📊 <b>Оценка уровня сервиса</b>\n\n"
        "Пожалуйста, оцените качество наших встреч и услуг по шкале от 1 до 10:",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("rating:"))
async def handle_rating_selection(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data or not callback.message:
        return

    rating = int(callback.data.split(":")[1])
    await state.update_data(rating=rating)
    await state.set_state(ServiceLevelStates.waiting_for_improvement)

    await callback.message.edit_text(
        f"📊 <b>Оценка уровня сервиса</b>\n\n"
        f"Ваша оценка: <b>{rating}/10</b>\n\n"
        "Что бы вы хотели улучшить в работе на встречах?\n"
        "Напишите ваши пожелания или нажмите 'Пропустить':",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="⏩ Пропустить", callback_data="improvement_skip")],
                [InlineKeyboardButton(text="❌ Отменить", callback_data="service_cancel")],
            ]
        ),
    )
    await callback.answer()


@router.message(ServiceLevelStates.waiting_for_improvement)
async def handle_improvement_text(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("⚠️ Пожалуйста, отправьте текстовое сообщение или нажмите 'Пропустить'.")
        return

    data = await state.get_data()
    rating = data.get("rating", 0)

    await _save_service_level_feedback(message, rating, message.text)
    await state.clear()


@router.callback_query(F.data == "improvement_skip")
async def handle_improvement_skip(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    data = await state.get_data()
    rating = data.get("rating", 0)

    await _save_service_level_feedback(callback.message, rating, None, from_user=callback.from_user)
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "service_cancel")
async def handle_service_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    await state.clear()
    await callback.message.edit_text("❌ Опрос отменён.")
    await callback.answer()


async def _save_service_level_feedback(message: Message, rating: int, improvement: str | None, from_user=None) -> None:
    from_user = from_user or message.from_user
    if not from_user:
        return

    received_at = message.date or timezone.now()
    if timezone.is_naive(received_at):
        received_at = timezone.make_aware(received_at)

    try:
        stored = await sync_to_async(_store_task, thread_sensitive=True)(
            telegram_id=from_user.id,
            username=from_user.username,
            message_id=message.message_id,
            message_text="",
            received_at=received_at,
            rating=rating,
            improvement=improvement,
        )

        if stored:
            debug_logger.info(f"Service level feedback saved: rating={rating}, improvement={improvement!r}, user={from_user.username}")
            if isinstance(message, Message):
                await message.answer("✅ Спасибо за ваш вклад в наше общее дело!")
            else:
                await message.edit_text("✅ Спасибо за ваш вклад в наше общее дело!", reply_markup=None)
        else:
            error_text = (
                "❗️Ваш аккаунт ещё не привязан к клиенту.\n"
                "Пожалуйста, используйте персональную ссылку от администратора."
            )
            if isinstance(message, Message):
                await message.answer(error_text)
            else:
                await message.edit_text(error_text, reply_markup=None)
    except Exception:
        logger.exception("Failed to save service level feedback (user_id=%s)", from_user.id)
        error_text = "❌ Не удалось сохранить отзыв. Попробуйте позже."
        if isinstance(message, Message):
            await message.answer(error_text)
        else:
            await message.edit_text(error_text, reply_markup=None)


@router.callback_query(F.data.startswith(CHAIN_BUTTON_PREFIX))
async def handle_chain_button(callback: CallbackQuery) -> None:
    """Handle chain inline button presses."""
    if callback.message is None:
        return

    from_user = callback.from_user
    if from_user is None:
        await callback.answer()
        return

    binding = await _get_binding_for_user(from_user.id)
    if binding is None:
        await callback.answer()
        await callback.message.answer(
            "❗️Ваш аккаунт ещё не привязан к клиенту.\n"
            "Пожалуйста, используйте персональную ссылку от администратора.",
            reply_markup=main_menu(),
        )
        return

    # ИСПРАВЛЕНИЕ: Отвечаем на callback сразу, чтобы убрать "часики" в Telegram
    await callback.answer()

    data = callback.data or ""
    button_label = data[len(CHAIN_BUTTON_PREFIX):]

    executor = ChainExecutor()
    result = await sync_to_async(
        executor.process_user_message,
        thread_sensitive=True,
    )(
        user_id=from_user.id,
        tenant_id=binding.tenant_id,
        user_message={"button": button_label},
    )
    await _execute_chain_actions(
        bot=callback.message.bot,
        chat_id=from_user.id,
        session_id=result.get("session_id"),
        actions=result.get("actions", []),
    )
    if result.get("session_status") == "completed":
        await callback.message.answer("Цепочка завершена.", reply_markup=main_menu())


# ---------------------------------------------------------------------------
# /meetings
# ---------------------------------------------------------------------------

@router.message(Command("meetings"))
async def handle_meetings(message: Message) -> None:
    if message.chat.type != "private":
        return
    await send_meetings(message)


# ---------------------------------------------------------------------------
# Глобальный обработчик — маршрутизация по кнопкам меню
# ---------------------------------------------------------------------------

@router.message((~(F.text.startswith("/") | F.caption.startswith("/"))) & ~F.voice)
async def handle_message(message: Message, state: FSMContext) -> None:
    if message.chat.type != "private":
        return

    from_user = message.from_user
    if from_user is None:
        return

    message_text = (message.text or message.caption or "").strip()
    if not message_text:
        return

    if message_text == WELCOME_BUTTON_TEXT:
        binding = await _get_binding_for_user(from_user.id)
        if binding is None:
            await message.answer(
                "❗️Ваш аккаунт ещё не привязан к клиенту.\n"
                "Пожалуйста, используйте персональную ссылку от администратора.",
                reply_markup=main_menu(),
            )
            return

        executor = ChainExecutor()
        result = await sync_to_async(
            executor.start_chain,
            thread_sensitive=True,
        )(user_id=from_user.id, tenant_id=binding.tenant_id)
        await _execute_chain_actions(
            bot=message.bot,
            chat_id=from_user.id,
            session_id=result.get("session_id"),
            actions=result.get("actions", []),
        )
        return

    if message_text.lower() == MEETINGS_BUTTON_TEXT.lower():
        await send_meetings(message)
        return

    if message_text == "📊 Уровень сервиса":
        await _start_service_level_survey(message, state)
        return

    binding = await _get_binding_for_user(from_user.id)
    if binding is not None:
        user_message: dict[str, Any] = {}
        text_value = (message.text or message.caption or "").strip()
        if text_value:
            user_message["text"] = text_value
        if message.photo:
            user_message["photo"] = True
        if message.video:
            user_message["video"] = True
        if message.audio:
            user_message["audio"] = True
        if message.voice:
            user_message["voice"] = True
        if message.document:
            user_message["document"] = True
        if message.sticker:
            user_message["sticker"] = True
        if message.location:
            user_message["location"] = True
        if message.contact:
            user_message["contact"] = True

        message_type = None
        if message.photo:
            message_type = "photo"
        elif message.video:
            message_type = "video"
        elif message.audio:
            message_type = "audio"
        elif message.voice:
            message_type = "voice"
        elif message.document:
            message_type = "document"
        elif message.sticker:
            message_type = "sticker"
        elif message.location:
            message_type = "location"
        elif message.contact:
            message_type = "contact"
        elif text_value:
            message_type = "text"

        if message_type:
            user_message["message_type"] = message_type

        entities_raw = []
        if message.entities:
            entities_raw.extend(message.entities)
        if message.caption_entities:
            entities_raw.extend(message.caption_entities)

        if entities_raw:
            normalized = set()
            for ent in entities_raw:
                ent_type = getattr(ent, "type", "") or ""
                if ent_type == "email":
                    normalized.add("email")
                elif ent_type == "phone_number":
                    normalized.add("phone")
                elif ent_type in {"url", "text_link"}:
                    normalized.add("url")
                elif ent_type == "hashtag":
                    normalized.add("hashtag")
                elif ent_type == "mention":
                    normalized.add("mention")
                elif ent_type == "cashtag":
                    normalized.add("cashtag")
                elif ent_type == "bot_command":
                    normalized.add("bot_command")
            if normalized:
                user_message["entities"] = sorted(normalized)

        if user_message:
            executor = ChainExecutor()
            result = await sync_to_async(
                executor.process_user_message,
                thread_sensitive=True,
            )(
                user_id=from_user.id,
                tenant_id=binding.tenant_id,
                user_message=user_message,
            )
            if result.get("session_status") != "none":
                await _execute_chain_actions(
                    bot=message.bot,
                    chat_id=from_user.id,
                    session_id=result.get("session_id"),
                    actions=result.get("actions", []),
                )
                if result.get("session_status") == "completed":
                    await message.answer("Цепочка завершена.", reply_markup=main_menu())
                return

    await message.answer(
        "Используйте меню для выбора действия:",
        reply_markup=main_menu(),
    )


# ---------------------------------------------------------------------------
# Bot bootstrap
# ---------------------------------------------------------------------------

async def _run_bot(token: str) -> None:
    import logging as _logging
    _logging.basicConfig(level=_logging.WARNING)

    debug_handler = _logging.StreamHandler()
    debug_formatter = _logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    debug_handler.setFormatter(debug_formatter)
    debug_logger.addHandler(debug_handler)
    debug_logger.setLevel(_logging.WARNING)

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
    dispatcher.include_router(voice_router)
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
