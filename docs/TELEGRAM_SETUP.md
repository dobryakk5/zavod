# Настройка Telegram для автоматической публикации

## Проблема

При публикации через Celery worker возникает ошибка:
```
EOFError: EOF when reading a line
```

Это происходит потому, что Telegram User API требует интерактивной авторизации через телефон и код, но Celery worker работает без интерактивного терминала.

## Решение 1: Использование Telegram Bot (Рекомендуется)

Это самый надежный способ для автоматической публикации постов.

### Шаг 1: Создайте Telegram бота

1. Откройте Telegram и найдите @BotFather
2. Отправьте команду `/newbot`
3. Следуйте инструкциям:
   - Введите имя бота (например: "Auto Prodaji Publisher")
   - Введите username бота (например: "auto_prodaji_bot")
4. Скопируйте токен бота (выглядит как `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Шаг 2: Добавьте бота в канал как администратора

1. Откройте настройки вашего канала @auto_prodaji
2. Перейдите в "Администраторы"
3. Нажмите "Добавить администратора"
4. Найдите вашего бота по username
5. Дайте ему права:
   - ✅ Публикация сообщений
   - ✅ Редактирование сообщений (опционально)
   - ✅ Удаление сообщений (опционально)

### Шаг 3: Сохраните токен бота в Django Admin

1. Откройте http://127.0.0.1:8000/django-admin/core/socialaccount/1/change/
2. В поле **Access token** вставьте токен бота (например: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
3. Нажмите "Сохранить"

### Шаг 4: Перезапустите Celery worker

```bash
# Остановите текущий worker (Ctrl+C)
# Затем запустите снова
celery -A config worker -l info
```

### Готово!

Теперь публикация должна работать автоматически через Bot API.

---

## Решение 2: Авторизация User API (Альтернативное)

Если по какой-то причине вы не можете использовать бота, можно предварительно авторизовать User API сессию.

**Важно:** User API имеет ограничения на количество сообщений и может быть заблокирован при спамминге.

### Шаг 1: Создайте скрипт авторизации

Создайте файл `backend/scripts/authorize_telegram.py`:

```python
import asyncio
from telethon import TelegramClient
import os

# Замените эти значения на ваши из Client модели
API_ID = 21596530
API_HASH = "726ec3c4e19e75807956..."  # Полный hash
CLIENT_ID = 3  # ID клиента из базы

session_name = f"session_publisher_client_{CLIENT_ID}"
sessions_dir = os.path.join(os.path.dirname(__file__), '..', 'telegram_sessions')
os.makedirs(sessions_dir, exist_ok=True)
session_path = os.path.join(sessions_dir, session_name)

async def main():
    client = TelegramClient(session_path, API_ID, API_HASH)

    print("Начинаем авторизацию...")
    await client.start()

    print(f"✅ Авторизация успешна! Сессия сохранена в {session_path}.session")
    print("Теперь Celery worker сможет использовать эту сессию")

    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
```

### Шаг 2: Запустите скрипт

```bash
cd backend
python scripts/authorize_telegram.py
```

Вам будет предложено ввести:
1. Номер телефона (в международном формате, например: +79123456789)
2. Код подтверждения из Telegram
3. (Опционально) 2FA пароль, если включен

### Шаг 3: Перезапустите Celery worker

После успешной авторизации файл сессии будет создан, и Celery worker сможет использовать его для публикаций.

---

## Проверка

После настройки попробуйте опубликовать пост через кнопку "Быстрая публикация" в Django Admin.

Если возникают ошибки, проверьте логи Celery worker:
```bash
tail -f celery.log
```

## Troubleshooting

### Ошибка: "RuntimeError: Сессия не найдена"
- Используйте Решение 1 (Bot API) или создайте сессию через Решение 2

### Ошибка: "Can't write messages to channel"
- Убедитесь, что бот добавлен как администратор канала с правами на публикацию

### Ошибка: "Invalid bot token"
- Проверьте правильность токена в SocialAccount.access_token
- Токен должен выглядеть как `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

### Бот публикует от своего имени, а не от имени канала
- Это нормально! При публикации ботом в канал сообщения появляются как сообщения канала, а не бота
