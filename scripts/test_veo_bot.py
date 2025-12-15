#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы VEO бота @syntxaibot
"""

import os
import asyncio
import sys
from pathlib import Path

# Добавляем backend в путь
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from core.foto_video_gen import generate_image_from_telegram_bot

async def test_veo_bot():
    """Тестирование VEO бота"""
    print("🧪 Тестирование VEO бота @syntxaibot")

    # Проверяем переменные окружения
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("❌ Ошибка: TELEGRAM_API_ID и TELEGRAM_API_HASH не установлены")
        print("💡 Запустите: ./scripts/setup_veo_telegram.sh")
        return

    print(f"✅ API ID: {api_id}")
    print(f"✅ API Hash: установлен")

    # Проверяем сессию
    session_file = backend_path / "telegram_sessions" / "session_collector_client_3.session"
    if not session_file.exists():
        print(f"❌ Сессия не найдена: {session_file}")
        print("💡 Авторизуйтесь через: python backend/core/foto_video_gen.py")
        return

    print(f"✅ Сессия найдена: {session_file}")

    # Тестируем генерацию
    test_prompt = "A beautiful sunset over mountains"
    print(f"🎨 Тестируем генерацию с промптом: '{test_prompt}'")

    result = generate_image_from_telegram_bot(
        prompt=test_prompt,
        bot_username="@syntxaibot",
        session_name="telegram_sessions/session_collector_client_3",
        timeout=60,  # Короткий таймаут для теста
        api_id=api_id,
        api_hash=api_hash
    )

    if result.get("success"):
        print("✅ Генерация успешна!")
        print(f"🖼️  Изображение: {result.get('image_path')}")
    else:
        print(f"❌ Ошибка: {result.get('error')}")
        print("💡 Проверьте логи для подробностей")

if __name__ == "__main__":
    asyncio.run(test_veo_bot())