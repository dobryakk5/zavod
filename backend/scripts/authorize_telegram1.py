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
    "giga_bot": "giga_generator",
}

SESSION_DESCRIPTIONS = {
    "publisher": "Публикация постов через User API",
    "collector": "Сбор Telegram трендов (требуется User API)",
    "giga_bot": "Генерация изображений через GigaChat бот",
}


def list_clients():
    return list(Client.objects.all())


def get_session_name(client_id: int | None, session_type: str) -> str:
    if session_type not in SESSION_TYPES:
        raise ValueError(f"Неизвестный тип сессии: {session_type}")

    template = SESSION_TYPES[session_type]
    if "{client_id}" in template:
        if client_id is None:
            raise ValueError(f"Тип сессии {session_type} требует client_id")
        return template.format(client_id=client_id)
    else:
        return template


async def authorize_session(client_id: int | None, session_type: str):
    """Авторизовать Telegram сессию."""
    if session_type == "giga_bot":
        # Для GigaChat бота используем общие настройки из переменных окружения
        api_id = os.getenv("TELEGRAM_API_ID")
        api_hash = os.getenv("TELEGRAM_API_HASH")

        if not api_id or not api_hash:
            print("❌ TELEGRAM_API_ID и TELEGRAM_API_HASH не найдены в переменных окружения")
            print("   Установите их в .env файле или переменных окружения")
            return False

        try:
            api_id = int(api_id)
        except ValueError:
            print("❌ TELEGRAM_API_ID должен быть числом")
            return False

        client_name = "GigaChat Bot"
        client_id_display = "общий"

    else:
        # Для других типов сессий нужен клиент
        if client_id is None:
            print("❌ client_id обязателен для этого типа сессии")
            return False

        try:
            client = await sync_to_async(Client.objects.get)(id=client_id)
        except Client.DoesNotExist:
            print(f"❌ Клиент с ID {client_id} не найден")
            return False

        if not client.telegram_api_id or not client.telegram_api_hash:
            print(f"❌ У клиента '{client.name}' не настроены telegram_api_id и telegram_api_hash")
            return False

        api_id = client.telegram_api_id
        api_hash = client.telegram_api_hash
        client_name = client.name
        client_id_display = str(client.id)

    session_name = get_session_name(client_id, session_type)

    if session_type == "giga_bot":
        # For giga_bot, create session in backend directory to match foto_video_gen.py expectations
        sessions_dir = os.path.join(os.path.dirname(__file__), '..')
        session_path = os.path.join(sessions_dir, session_name)
    else:
        sessions_dir = os.path.join(os.path.dirname(__file__), '..', 'telegram_sessions')
        os.makedirs(sessions_dir, exist_ok=True)
        session_path = os.path.join(sessions_dir, session_name)

    print(f"🔐 Авторизация для: {client_name} (ID: {client_id_display})")
    print(f"📱 API ID: {api_id}")
    print(f"🎯 Тип сессии: {session_type} – {SESSION_DESCRIPTIONS.get(session_type, '')}")
    print(f"📂 Сессия будет сохранена в: {session_path}.session")
    print()

    telegram_client = TelegramClient(session_path, api_id, api_hash)

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
        help="Тип сессии: publisher (публикация постов), collector (сбор трендов), giga_bot (GigaChat бот)"
    )
    return parser.parse_args()


async def main(args):
    """Главная функция."""
    print("=" * 70)
    print("Скрипт авторизации Telegram сессий")
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

    # Получаем ID клиента (для giga_bot не требуется)
    client_id = args.client_id
    if args.session_type != "giga_bot":
        if client_id is None:
            try:
                client_id = int(input("Введите ID клиента для авторизации: "))
            except (ValueError, EOFError):
                print("❌ Неверный ID")
                return
    elif client_id is not None:
        print("⚠️  Для типа сессии giga_bot client_id игнорируется")

    print()
    success = await authorize_session(client_id, args.session_type)

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
