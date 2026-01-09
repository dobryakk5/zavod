# Настройка VEO генерации изображений

## Обзор
Система поддерживает генерацию изображений через Telegram бота **@syntxaibot** для метода `veo_photo`.

## Быстрая настройка

### 1. Установка переменных окружения
```bash
./scripts/setup_veo_telegram.sh
```
Скрипт запросит:
- `TELEGRAM_API_ID` - ваш API ID от https://my.telegram.org
- `TELEGRAM_API_HASH` - ваш API Hash от https://my.telegram.org

### 2. Проверка сессии
Убедитесь, что сессия авторизована:
```bash
ls -la backend/telegram_sessions/session_collector_client_3.session
```
Если файла нет, авторизуйтесь:
```bash
cd backend && python -c "
import asyncio
from telethon import TelegramClient
import os

async def auth():
    api_id = int(os.getenv('TELEGRAM_API_ID'))
    api_hash = os.getenv('TELEGRAM_API_HASH')
    client = TelegramClient('telegram_sessions/session_collector_client_3', api_id, api_hash)
    await client.start()
    print('✅ Авторизация успешна')
    await client.disconnect()

asyncio.run(auth())
"
```

### 3. Тестирование
```bash
python scripts/test_veo_bot.py
```

### 4. Использование
Установите метод генерации в админке или через API:
```python
# Через API
POST /api/posts/{id}/generate_image/
{
    "model": "veo_photo"
}

# Или установите по умолчанию в System Settings
generation_method = "veo_photo"
```

## Конфигурация

### Переменные окружения
- `TELEGRAM_API_ID` - API ID для Telegram
- `TELEGRAM_API_HASH` - API Hash для Telegram

### Сессия
- **Путь**: `telegram_sessions/session_collector_client_3.session`
- **Общая**: используется для всех Telegram ботов

### Бот
- **Username**: `@syntxaibot`
- **Тип**: генерация изображений через inline меню

## Диагностика

### Распространенные ошибки

1. **"You can't write in this chat"**
   - Бот не позволяет отправлять сообщения
   - Проверьте, что бот запущен и доступен

2. **"Session not authorized"**
   - Сессия не авторизована
   - Переавторизуйтесь через скрипт выше

3. **"Bot not found"**
   - Бот с таким username не существует
   - Проверьте корректность `@syntxaibot`

### Логи
Логи VEO генерации:
```
[IMAGE BOT Thread XXX] Начало инициализации клиента
[IMAGE BOT Thread XXX] Отправка команды /design...
[IMAGE BOT Thread XXX] Кнопка SORA Images нажата
```

## Архитектура

```
generate_image_for_post() -> generate_image_from_telegram_bot()
    ↓
@syntxaibot: /design -> 🌙 SORA Images -> prompt -> image
```

Бот использует inline меню для выбора режима генерации изображений.