"""
UI элементы для Telegram бота
"""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


WELCOME_BUTTON_TEXT = "Welcome"
MEETINGS_BUTTON_TEXT = "Встречи"


def main_menu() -> ReplyKeyboardMarkup:
    """Главное меню бота"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=WELCOME_BUTTON_TEXT)],
            [KeyboardButton(text=MEETINGS_BUTTON_TEXT)],
            [KeyboardButton(text="📊 Уровень сервиса")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
