"""
UI элементы для Telegram бота
"""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


MEETINGS_BUTTON_TEXT = "Встречи"


def main_menu() -> ReplyKeyboardMarkup:
    """Главное меню бота"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=MEETINGS_BUTTON_TEXT)],
            [KeyboardButton(text="📊 Уровень сервиса")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )