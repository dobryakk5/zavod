#!/bin/bash

# Скрипт для настройки переменных окружения для VEO Telegram бота
# Используется бот @syntxaibot для генерации изображений

echo "Настройка переменных окружения для VEO Telegram бота"
echo "=================================================="

# Запрашиваем API ID и Hash
read -p "Введите TELEGRAM_API_ID: " TELEGRAM_API_ID
read -p "Введите TELEGRAM_API_HASH: " TELEGRAM_API_HASH

# Создаем или обновляем .env файл
ENV_FILE=".env"
if [ ! -f "$ENV_FILE" ]; then
    touch "$ENV_FILE"
fi

# Добавляем или обновляем переменные
if grep -q "^TELEGRAM_API_ID=" "$ENV_FILE"; then
    sed -i.bak "s/^TELEGRAM_API_ID=.*/TELEGRAM_API_ID=\"$TELEGRAM_API_ID\"/" "$ENV_FILE"
else
    echo "TELEGRAM_API_ID=\"$TELEGRAM_API_ID\"" >> "$ENV_FILE"
fi

if grep -q "^TELEGRAM_API_HASH=" "$ENV_FILE"; then
    sed -i.bak "s/^TELEGRAM_API_HASH=.*/TELEGRAM_API_HASH=\"$TELEGRAM_API_HASH\"/" "$ENV_FILE"
else
    echo "TELEGRAM_API_HASH=\"$TELEGRAM_API_HASH\"" >> "$ENV_FILE"
fi

echo ""
echo "✅ Переменные окружения настроены в файле .env"
echo "📋 Для применения изменений перезапустите сервер:"
echo "   cd backend && python manage.py runserver"
echo ""
echo "🔧 Текущая конфигурация VEO:"
echo "   - Бот: @syntxaibot"
echo "   - Сессия: telegram_sessions/session_collector_client_3"
echo "   - API ID: $TELEGRAM_API_ID"
echo "   - API Hash: [скрыт]"