#!/usr/bin/env python
"""
Скрипт для предварительной авторизации Telegram User API.

Использование:
    python backend/scripts/authorize_telegram.py

Этот скрипт нужен только если вы НЕ используете Bot API.
Рекомендуется использовать Bot API (см. TELEGRAM_SETUP.md)
"""

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

async def authorize_client(client_id: int):
    """Авторизовать Telegram сессию для клиента."""
    try:
        client = Client.objects.get(id=client_id)
    except Client.DoesNotExist:
        print(f"❌ Клиент с ID {client_id} не найден")
        return False

    if not client.telegram_api_id or not client.telegram_api_hash:
        print(f"❌ У клиента '{client.name}' не настроены telegram_api_id и telegram_api_hash")
        return False

    session_name = f"session_publisher_client_{client.id}"
    sessions_dir = os.path.join(os.path.dirname(__file__), '..', 'telegram_sessions')
    os.makedirs(sessions_dir, exist_ok=True)
    session_path = os.path.join(sessions_dir, session_name)

    print(f"🔐 Авторизация для клиента: {client.name} (ID: {client.id})")
    print(f"📱 API ID: {client.telegram_api_id}")
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
        print("Теперь Celery worker сможет использовать эту сессию для публикации постов.")
        print("Перезапустите Celery worker, чтобы изменения вступили в силу.")

        await telegram_client.disconnect()
        return True

    except Exception as e:
        print(f"❌ Ошибка при авторизации: {e}")
        await telegram_client.disconnect()
        return False


async def main():
    """Главная функция."""
    print("=" * 70)
    print("Скрипт авторизации Telegram User API")
    print("=" * 70)
    print()
    print("⚠️  ВНИМАНИЕ: Рекомендуется использовать Bot API вместо User API")
    print("   См. инструкцию в TELEGRAM_SETUP.md")
    print()

    # Показываем доступных клиентов
    clients = Client.objects.all()
    if not clients.exists():
        print("❌ В базе нет клиентов")
        return

    print("Доступные клиенты:")
    for c in clients:
        has_api = "✅" if c.telegram_api_id and c.telegram_api_hash else "❌"
        print(f"  {has_api} {c.id}: {c.name}")
    print()

    # Запрашиваем ID клиента
    try:
        client_id = int(input("Введите ID клиента для авторизации: "))
    except (ValueError, EOFError):
        print("❌ Неверный ID")
        return

    print()
    success = await authorize_client(client_id)

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
    asyncio.run(main())
