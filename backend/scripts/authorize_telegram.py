#!/usr/bin/env python3
"""
Скрипт принудительной авторизации Telegram User API.

Использование:
    python backend/scripts/authorize_telegram.py --client-id 3 --session-type publisher
"""

import argparse
import asyncio
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
django.setup()

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from core.models import Client
from asgiref.sync import sync_to_async


SESSION_TYPES = {
    "publisher": "session_publisher_client_{client_id}",
    "collector": "session_collector_client_{client_id}",
    "giga_bot": "giga_generator",
}

SESSION_DESCRIPTIONS = {
    "publisher": "Публикация постов через User API",
    "collector": "Сбор Telegram трендов",
    "giga_bot": "Генерация изображений через GigaChat бот",
}


def get_session_name(client_id: int | None, session_type: str) -> str:
    template = SESSION_TYPES[session_type]
    return template.format(client_id=client_id) if "{client_id}" in template else template


async def authorize_session(client_id: int | None, session_type: str):
    if session_type == "giga_bot":
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")
        if not api_id or not api_hash:
            print("❌ Не найдены TELEGRAM_API_ID / TELEGRAM_API_HASH")
            return False
        api_id = int(api_id)
        client_name = "GigaChat Bot"
    else:
        client = await sync_to_async(Client.objects.get)(id=client_id)
        api_id = client.telegram_api_id
        api_hash = client.telegram_api_hash
        client_name = client.name

    sessions_dir = os.path.join(os.path.dirname(__file__), "..", "telegram_sessions")
    os.makedirs(sessions_dir, exist_ok=True)

    session_path = os.path.join(sessions_dir, get_session_name(client_id, session_type))

    print("\n" + "=" * 60)
    print(f"🔐 Авторизация для: {client_name}")
    print(f"📂 Файл сессии: {session_path}.session")
    print("=" * 60)

    # 🔥 удаляем битую сессию
    if os.path.exists(session_path + ".session"):
        os.remove(session_path + ".session")
        print("🗑 Удалена старая сессия")

    client = TelegramClient(session_path, api_id, api_hash)
    await client.connect()

    phone = input("📞 Введите номер телефона в формате +79998887766: ")

    print("📨 Отправляем код в Telegram...")
    await client.send_code_request(phone)

    code = input("🔑 Введите код из Telegram: ")

    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        password = input("🔐 Введите пароль 2FA: ")
        await client.sign_in(password=password)

    me = await client.get_me()
    print(f"\n✅ Успешный вход: {me.first_name} ({me.id})")
    print(f"🎉 Сессия сохранена: {session_path}.session\n")

    await client.disconnect()
    return True


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--client-id", type=int)
    parser.add_argument("--session-type", choices=SESSION_TYPES, default="publisher")
    return parser.parse_args()


async def main(args):
    success = await authorize_session(args.client_id, args.session_type)
    print("🎯 ГОТОВО!" if success else "❌ Ошибка авторизации")


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
