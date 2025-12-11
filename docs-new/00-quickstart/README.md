# Быстрый старт

Это руководство поможет вам начать работу с Zavod за 5 минут.

## Содержание

- [Требования](#требования)
- [Установка](#установка)
- [Запуск системы](#запуск-системы)
- [Первый пост](#первый-пост)
- [Дальнейшие шаги](#дальнейшие-шаги)

## Требования

- **Python 3.10+**
- **Node.js 18+**
- **PostgreSQL 12+**
- **Redis 6+**

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd zavod
```

### 2. Установка backend зависимостей

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

### 3. Установка frontend зависимостей

```bash
cd ../frontend
npm install
```

### 4. Настройка окружения

```bash
# Backend
cp .env.example .env
# Заполните .env своими настройками

# Frontend
cp .env.local.example .env.local
# Заполните .env.local своими настройками
```

## Запуск системы

### 1. Backend

```bash
cd backend
python manage.py migrate
python manage.py runserver
```

Сервер запустится на `http://localhost:8000`

### 2. Frontend

```bash
cd frontend
npm run dev
```

Frontend запустится на `http://localhost:3000`

### 3. Celery Worker

```bash
cd backend
celery -A config worker -l info
```

### 4. Redis (если не установлен)

```bash
# Установка через brew (Mac)
brew install redis
redis-server

# Или через Docker
docker run -p 6379:6379 redis:alpine
```

## Первый пост

### 1. Создание клиента

1. Перейдите в Django Admin: http://localhost:8000/admin/
2. Создайте нового клиента в разделе **Clients**
3. Укажите имя и slug

### 2. Настройка AI

1. Получите API ключ от OpenAI
2. Добавьте его в `backend/.env`:
   ```
   OPENAI_API_KEY=sk-your-key-here
   ```

### 3. Создание поста

1. Перейдите в интерфейс: http://localhost:3000
2. Авторизуйтесь через Telegram
3. Выберите клиента
4. Перейдите в раздел **Posts**
5. Нажмите **"Создать пост"**
6. Заполните заголовок и текст
7. Сохраните

### 4. Публикация

1. В разделе **Schedule** выберите пост
2. Укажите дату и время публикации
3. Выберите социальные сети
4. Сохраните расписание

## Дальнейшие шаги

### Изучите документацию

- **[Архитектура системы](../01-architecture/overview.md)** - Как работает Zavod
- **[API документация](../02-api/overview.md)** - Все доступные endpoints
- **[AI интеграция](../03-ai-integration/setup.md)** - Настройка генерации контента
- **[Social интеграция](../04-social-integration/overview.md)** - Подключение соцсетей

### Настройка под себя

- **[Backend настройка](../06-backend/setup.md)** - Django конфигурация
- **[Frontend настройка](../05-frontend/overview.md)** - Next.js UI
- **[Деплоймент](../07-deployment/docker.md)** - Запуск в production

### Решение проблем

Если возникли проблемы:
- Проверьте [Troubleshooting](../08-guides/troubleshooting.md)
- Задайте вопрос в issues
- Изучите логи backend и frontend

---

**Готово!** Теперь вы можете использовать Zavod для автоматической генерации и публикации контента.
