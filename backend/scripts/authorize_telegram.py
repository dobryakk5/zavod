#!/usr/bin/env python
"""
Скрипт для предварительной авторизации Telegram User API.

Использование:
    python backend/scripts/authorize_telegram.py [--client-id 3] [--session-type publisher|collector]

Этот скрипт нужен, если вы хотите использовать Telegram User API для публикаций
или сбора трендов (боты не могут читать историю каналов).
"""

import argparse
import asyncio
import os
import sys
import django

# Настраиваем Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')
django.setup()

from telethon import TelegramClient
from core.models import Client
from asgiref.sync import sync_to_async

SESSION_TYPES = {
    "publisher": "session_publisher_client_{client_id}",
    "collector": "session_collector_client_{client_id}",
}

SESSION_DESCRIPTIONS = {
    "publisher": "Публикация постов через User API",
    "collector": "Сбор Telegram трендов (требуется User API)",
}


def list_clients():
    return list(Client.objects.all())


def get_session_name(client_id: int, session_type: str) -> str:
    if session_type not in SESSION_TYPES:
        raise ValueError(f"Неизвестный тип сессии: {session_type}")
    return SESSION_TYPES[session_type].format(client_id=client_id)


async def authorize_client(client_id: int, session_type: str):
    """Авторизовать Telegram сессию для клиента."""
    try:
        client = await sync_to_async(Client.objects.get)(id=client_id)
    except Client.DoesNotExist:
        print(f"❌ Клиент с ID {client_id} не найден")
        return False

    if not client.telegram_api_id or not client.telegram_api_hash:
        print(f"❌ У клиента '{client.name}' не настроены telegram_api_id и telegram_api_hash")
        return False

    session_name = get_session_name(client.id, session_type)
    sessions_dir = os.path.join(os.path.dirname(__file__), '..', 'telegram_sessions')
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, session_name)

    print(f"🔐 Авторизация для клиента: {client.name} (ID: {client.id})")
    print(f"📱 API ID: {client.telegram_api_id}")
    print(f"🎯 Тип сессии: {session_type} – {SESSION_DESCRIPTIONS.get(session_type, '')}")
    print(f"📂 Сессия будет сохранена в: {session_path}.session")
    print()

    telegram_client = TelegramClient(session_path, client.telegram_api_id, client.telegram_api_hash)

    try:
        print("🚀 Подключаемся к Telegram...")
        await telegram_client.start()

        # Проверяем, что авторизация прошла успешно
        me = await telegram_client.get_me()
        print()
        print(f"✅ Авторизация успешна!")
        print(f"   Пользователь: {me.first_name} {me.last_name or ''}")
        print(f"   Username: @{me.username}" if me.username else "")
        print(f"   Телефон: {me.phone}")
        print()
        print(f"✅ Сессия сохранена в: {session_path}.session")
        print()
        print("Теперь Celery worker сможет использовать эту сессию.")
        print("Перезапустите Celery worker, чтобы изменения вступили в силу.")

        await telegram_client.disconnect()
        return True

    except Exception as e:
        print(f"❌ Ошибка при авторизации: {e}")
        await telegram_client.disconnect()
        return False


def parse_args():
    parser = argparse.ArgumentParser(description="Авторизация Telegram User API сессии")
    parser.add_argument(
        "--client-id",
        type=int,
        help="ID клиента, для которого нужно авторизовать сессию (если не указан, будет задан вопрос)"
    )
    parser.add_argument(
        "--session-type",
        choices=SESSION_TYPES.keys(),
        default="publisher",
        help="Тип сессии: publisher (публикация постов) или collector (сбор трендов)"
    )
    return parser.parse_args()


async def main(args):
    """Главная функция."""
    print("=" * 70)
    print("Скрипт авторизации Telegram User API")
    print("=" * 70)
    print()
    print("⚠️  ВНИМАНИЕ: Рекомендуется использовать Bot API вместо User API")
    print("   См. инструкцию в TELEGRAM_SETUP.md")
    print()

    print(f"🪪 Выбран тип сессии: {args.session_type} – {SESSION_DESCRIPTIONS.get(args.session_type, '')}")
    print()

    # Показываем доступных клиентов
    clients = await sync_to_async(list_clients)()
    if not clients:
        print("❌ В базе нет клиентов")
        return

    print("Доступные клиенты:")
    for c in clients:
        has_api = "✅" if c.telegram_api_id and c.telegram_api_hash else "❌"
        print(f"  {has_api} {c.id}: {c.name}")
    print()

    # Получаем ID клиента
    client_id = args.client_id
    if client_id is None:
        try:
            client_id = int(input("Введите ID клиента для авторизации: "))
        except (ValueError, EOFError):
            print("❌ Неверный ID")
            return

    print()
    success = await authorize_client(client_id, args.session_type)

    if success:
        print()
        print("=" * 70)
        print("✅ Авторизация завершена успешно!")
        print("=" * 70)
    else:
        print()
        print("=" * 70)
        print("❌ Авторизация не удалась")
        print("=" * 70)


if __name__ == '__main__':
    cli_args = parse_args()
    asyncio.run(main(cli_args))
