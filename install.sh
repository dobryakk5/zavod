

#!/usr/bin/env bash
set -e

echo "== Content Factory: установка окружения =="

# Корень проекта = папка, где лежит этот скрипт
PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$PROJECT_ROOT"

if [ ! -d "backend" ]; then
  echo "❌ Не найдена папка 'backend' рядом с install.sh"
  exit 1
fi

# 1. VENV
if [ ! -d "venv" ]; then
  echo "📦 Создаю виртуальное окружение venv..."
  python3 -m venv venv
else
  echo "📦 venv уже существует, пропускаю создание."
fi

echo "✅ Активирую venv..."
# shellcheck disable=SC1091
source venv/bin/activate

# 2. Обновляем pip
echo "⬆️ Обновляю pip..."
pip install --upgrade pip

# 3. Устанавливаем зависимости
echo "📥 Устанавливаю зависимости (wagtail, celery, pillow, drf, redis-клиент)..."
pip install \
  wagtail \
  "celery<6" \
  pillow \
  djangorestframework \
  redis

echo "✅ Зависимости установлены."

# 4. Миграции
cd backend

echo "🛠 Запускаю makemigrations..."
python manage.py makemigrations

echo "🛠 Запускаю migrate..."
python manage.py migrate

echo
echo "👌 Бэкенд готов."

echo
echo "Дальше сделай вручную (один раз):"
echo "  source venv/bin/activate"
echo "  cd backend"
echo "  python manage.py createsuperuser"
echo "  python manage.py runserver"
echo
echo "Для Celery (после настройки Redis):"
echo "  celery -A config worker -l INFO"
echo

# дзапускаемый: 
# chmod +x install.sh
# ./install.sh