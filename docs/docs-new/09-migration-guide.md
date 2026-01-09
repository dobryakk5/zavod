# Migration Guide

В этом документе описан процесс миграции с старой документации на новую структуру.

## Содержание

- [Обзор изменений](#обзор-изменений)
- [Старая структура](#старая-структура)
- [Новая структура](#новая-структура)
- [Перенос документов](#перенос-документов)
- [Обновление ссылок](#обновление-ссылок)
- [Проверка целостности](#проверка-целостности)

## Обзор изменений

### Цели миграции

1. **Улучшение структуры** - Логическая группировка документов
2. **Упрощение навигации** - Четкая иерархия и перекрестные ссылки
3. **Актуализация контента** - Обновление устаревшей информации
4. **Расширение покрытия** - Добавление недостающих разделов
5. **Улучшение UX** - Дружелюбный интерфейс и примеры

### Ключевые изменения

- **Новая нумерованная структура папок** (00-quickstart, 01-architecture, и т.д.)
- **Разделение на тематические блоки** (Architecture, API, AI, Social, Frontend, Backend, Deployment, Guides)
- **Единый стиль документации** - Consistent formatting и structure
- **Перекрестные ссылки** - Легкий переход между связанными документами
- **Практические примеры** - Готовые к использованию кодовые сниппеты

## Старая структура

### Исходные файлы

```
docs/
├── API_DOCUMENTATION.md           # API документация
├── AI_GENERATOR_SETUP.md          # Настройка AI генератора
├── ARCHITECTURE.md                # Архитектура системы
├── BACKEND.md                     # Backend документация
├── DEVOPS.md                      # DevOps и deployment
├── FRONTEND_GUIDE.md              # Frontend руководство
├── IMPLEMENTATION_SUMMARY.md      # Сводка реализации
├── multi-tenant.md                # Multi-tenant архитектура
├── pipeline.md                    # Контент-пиайп
├── TELEGRAM_AUTH.md               # Telegram аутентификация
├── TELEGRAM_PUBLISHING.md         # Telegram публикация
├── TELEGRAM_SETUP.md              # Telegram настройка
├── UI COMPONENTS.md               # UI компоненты
└── readme                         # Старый README
```

### Проблемы старой структуры

1. **Отсутствие иерархии** - Все файлы в одной папке
2. **Дублирование контента** - Информация повторяется в разных файлах
3. **Сложная навигация** - Трудно найти нужную информацию
4. **Несогласованность** - Разный стиль и форматирование
5. **Отсутствие перекрестных ссылок** - Трудно переходить между связанными темами

## Новая структура

### Целевая структура

```
docs-new/
├── README.md                      # Главный入口
├── 00-quickstart/
│   └── README.md                  # Быстрый старт
├── 01-architecture/
│   ├── overview.md                # Обзор архитектуры
│   ├── implementation-summary.md  # Сводка реализации
│   └── multi-tenant.md            # Multi-tenant архитектура
├── 02-api/
│   ├── overview.md                # Обзор API
│   ├── authentication.md          # Аутентификация
│   └── telegram-auth.md           # Telegram аутентификация
├── 03-ai-integration/
│   ├── setup.md                   # Настройка AI
│   └── content-generation.md      # Генерация контента
├── 04-social-integration/
│   ├── overview.md                # Обзор social интеграции
│   ├── telegram.md                # Telegram публикация
│   ├── telegram-setup.md          # Telegram настройка
│   ├── instagram.md               # Instagram интеграция
│   └── youtube.md                 # YouTube интеграция
├── 05-frontend/
│   ├── overview.md                # Обзор frontend
│   ├── api-integration.md         # API интеграция
│   └── ui-components.md           # UI компоненты
├── 06-backend/
│   ├── setup.md                   # Настройка backend
│   └── permissions.md             # Права доступа
├── 07-deployment/
│   ├── docker.md                  # Docker deployment
│   └── kubernetes.md              # Kubernetes deployment
└── 08-guides/
    ├── troubleshooting.md         # Troubleshooting
    └── best-practices.md          # Best practices
```

### Преимущества новой структуры

1. **Логическая группировка** - Связанные темы сгруппированы вместе
2. **Четкая иерархия** - Нумерованные папки указывают порядок изучения
3. **Единый стиль** - Consistent formatting и structure
4. **Перекрестные ссылки** - Легкий переход между документами
5. **Масштабируемость** - Простое добавление новых разделов

## Перенос документов

### 1. API Documentation

**Источник:** `docs/API_DOCUMENTATION.md`
**Назначение:** `docs-new/02-api/overview.md`

**Изменения:**
- Обновлено форматирование под новый стиль
- Добавлены перекрестные ссылки на другие API документы
- Улучшена структура endpoints
- Добавлены примеры использования

**Статус:** ✅ Завершено

### 2. AI Generator Setup

**Источник:** `docs/AI_GENERATOR_SETUP.md`
**Назначение:** `docs-new/03-ai-integration/setup.md`

**Изменения:**
- Разделен на setup и content-generation
- Добавлены практические примеры
- Улучшена структура настройки
- Добавлены troubleshooting разделы

**Статус:** ✅ Завершено

### 3. Architecture

**Источник:** `docs/ARCHITECTURE.md`
**Назначение:** `docs-new/01-architecture/overview.md`

**Изменения:**
- Обновлена архитектурная диаграмма
- Добавлены описания компонентов
- Улучшена структура разделов
- Добавлены best practices

**Статус:** ✅ Завершено

### 4. Backend Documentation

**Источник:** `docs/BACKEND.md`
**Назначение:** `docs-new/06-backend/permissions.md`

**Изменения:**
- Выделены отдельные разделы для permissions
- Добавлен setup.md для базовой настройки
- Улучшена структура кода
- Добавлены примеры middleware

**Статус:** ✅ Завершено

### 5. DevOps

**Источник:** `docs/DEVOPS.md`
**Назначение:** `docs-new/07-deployment/kubernetes.md`

**Изменения:**
- Разделен на docker и kubernetes
- Добавлены practical examples
- Улучшена структура манифестов
- Добавлены monitoring и scaling

**Статус:** ✅ Завершено

### 6. Frontend Guide

**Источник:** `docs/FRONTEND_GUIDE.md`
**Назначение:** `docs-new/05-frontend/overview.md`

**Изменения:**
- Разделен на overview, api-integration, ui-components
- Добавлены practical examples
- Улучшена структура компонентов
- Добавлены best practices

**Статус:** ✅ Завершено

### 7. Implementation Summary

**Источник:** `docs/IMPLEMENTATION_SUMMARY.md`
**Назначение:** `docs-new/01-architecture/implementation-summary.md`

**Изменения:**
- Обновлено форматирование
- Добавлены перекрестные ссылки
- Улучшена структура кода
- Добавлены примеры использования

**Статус:** ✅ Завершено

### 8. Telegram Documents

**Источники:**
- `docs/TELEGRAM_AUTH.md` → `docs-new/02-api/telegram-auth.md`
- `docs/TELEGRAM_PUBLISHING.md` → `docs-new/04-social-integration/telegram.md`
- `docs/TELEGRAM_SETUP.md` → `docs-new/04-social-integration/telegram-setup.md`

**Изменения:**
- Логическое разделение по разделам
- Улучшена структура инструкций
- Добавлены practical examples
- Добавлены troubleshooting разделы

**Статус:** ✅ Завершено

### 9. UI Components

**Источник:** `docs/UI COMPONENTS.md`
**Назначение:** `docs-new/05-frontend/ui-components.md`

**Изменения:**
- Интегрировано в frontend раздел
- Добавлены shadcn/ui примеры
- Улучшена структура компонентов
- Добавлены practical examples

**Статус:** ✅ Завершено

## Обновление ссылок

### 1. Внутренние ссылки

#### Старые ссылки

```markdown
[API Documentation](API_DOCUMENTATION.md)
[Telegram Setup](TELEGRAM_SETUP.md)
[Backend Guide](BACKEND.md)
```

#### Новые ссылки

```markdown
[API Documentation](../02-api/overview.md)
[Telegram Setup](./telegram-setup.md)
[Backend Guide](../06-backend/setup.md)
```

### 2. Cross-references

#### В API Documentation

```markdown
**См. также:**
- [Аутентификация](./authentication.md)
- [Telegram Auth](./telegram-auth.md)
- [Backend Setup](../06-backend/setup.md)
```

#### В Frontend Guide

```markdown
**См. также:**
- [API Integration](./api-integration.md)
- [UI Components](./ui-components.md)
- [Backend API](../02-api/overview.md)
```

#### В Backend Documentation

```markdown
**См. также:**
- [Permissions](./permissions.md)
- [API Endpoints](../02-api/overview.md)
- [Frontend Integration](../05-frontend/api-integration.md)
```

### 3. Navigation Links

#### В README

```markdown
## По разделам

- [01. Architecture](./01-architecture/overview.md) - Архитектура системы
- [02. API](./02-api/overview.md) - API документация
- [03. AI Integration](./03-ai-integration/setup.md) - Интеграция AI
- [04. Social Integration](./04-social-integration/overview.md) - Social сети
- [05. Frontend](./05-frontend/overview.md) - Frontend разработка
- [06. Backend](./06-backend/setup.md) - Backend разработка
- [07. Deployment](./07-deployment/docker.md) - Деплоймент
- [08. Guides](./08-guides/troubleshooting.md) - Руководства
```

#### В каждом разделе

```markdown
---

**Далее:**
- [API Documentation](../02-api/overview.md) - API документация
- [Backend Setup](../06-backend/setup.md) - Backend настройка
- [Troubleshooting](../08-guides/troubleshooting.md) - Решение проблем
```

## Проверка целостности

### 1. Ссылки

#### Проверка broken links

```bash
# Проверка ссылок в markdown файлах
npm install -g markdown-link-check

# Проверка всех файлов
find docs-new -name "*.md" -exec markdown-link-check {} \;
```

#### Проверка internal references

```bash
# Поиск broken internal links
grep -r "\[.*\](.*\.md)" docs-new/ | grep -v "docs-new/"

# Проверка существования файлов
find docs-new -name "*.md" -exec bash -c 'grep -l "](.*\.md)" "$1" | xargs -I {} dirname {}' _ {} \;
```

### 2. Структура

#### Проверка иерархии

```bash
# Проверка структуры папок
tree docs-new/

# Проверка наличия README в каждом разделе
find docs-new -type d -exec test -f "{}/README.md" \; -print
```

#### Проверка нумерации

```bash
# Проверка правильной нумерации папок
ls -d docs-new/*/ | sort

# Должно быть:
# docs-new/00-quickstart/
# docs-new/01-architecture/
# docs-new/02-api/
# docs-new/03-ai-integration/
# docs-new/04-social-integration/
# docs-new/05-frontend/
# docs-new/06-backend/
# docs-new/07-deployment/
# docs-new/08-guides/
```

### 3. Контент

#### Проверка дубликатов

```bash
# Поиск дублирующихся заголовков
grep -r "^# " docs-new/ | sort | uniq -d

# Поиск дублирующихся sections
grep -r "^## " docs-new/ | sort | uniq -d
```

#### Проверка formatting

```bash
# Проверка Markdown linting
npm install -g markdownlint-cli
markdownlint docs-new/**/*.md
```

### 4. Navigation

#### Проверка main navigation

```bash
# Проверка наличия navigation в README
grep -A 20 "## По разделам" docs-new/README.md

# Проверка наличия "Далее:" ссылок
grep -r "Далее:" docs-new/
```

#### Проверка cross-references

```bash
# Проверка наличия "См. также:"
grep -r "См. также:" docs-new/

# Проверка ссылок на другие разделы
grep -r "\[\.*\](\.\./" docs-new/
```

## Post-migration tasks

### 1. Update main README

```markdown
# Zavod Documentation

Добро пожаловать в документацию по системе Zavod!

## Краткое описание

Zavod - это система автоматической генерации и публикации контента с использованием AI.

## Быстрый старт

1. [Quick Start Guide](./00-quickstart/README.md)
2. [Architecture Overview](./01-architecture/overview.md)
3. [Setup Guide](./02-api/overview.md)

## По разделам

- [01. Architecture](./01-architecture/overview.md) - Архитектура системы
- [02. API](./02-api/overview.md) - API документация
- [03. AI Integration](./03-ai-integration/setup.md) - Интеграция AI
- [04. Social Integration](./04-social-integration/overview.md) - Social сети
- [05. Frontend](./05-frontend/overview.md) - Frontend разработка
- [06. Backend](./06-backend/setup.md) - Backend разработка
- [07. Deployment](./07-deployment/docker.md) - Деплоймент
- [08. Guides](./08-guides/troubleshooting.md) - Руководства

## Поиск

Используйте поиск по репозиторию для быстрого доступа к нужной информации.
```

### 2. Create index files

```markdown
# docs-new/00-quickstart/README.md

## Quick Start

1. [System Requirements](../../README.md#требования)
2. [Installation](../06-backend/setup.md#установка)
3. [Configuration](../02-api/overview.md#настройка)
4. [Running the System](../07-deployment/docker.md#запуск)

## Troubleshooting

Если возникли проблемы, см. [Troubleshooting Guide](../08-guides/troubleshooting.md).
```

### 3. Update navigation

```markdown
# Add to each document

---

**Назад:** [API Overview](../overview.md)
**Вперед:** [Authentication](./authentication.md)
**См. также:** [Backend Setup](../../06-backend/setup.md)
```

### 4. Final verification

```bash
# Complete verification script
./scripts/verify_migration.sh

# Check all links
./scripts/check_links.sh

# Validate structure
./scripts/validate_structure.sh
```

## Migration completion checklist

- [x] Create new directory structure
- [x] Migrate all documents
- [x] Update internal links
- [x] Add cross-references
- [x] Verify link integrity
- [x] Validate structure
- [x] Update main README
- [x] Create index files
- [x] Final verification

---

**Миграция завершена!**

Новая документация теперь доступна в `docs-new/` папке. Старая документация сохранена в `docs/` для обратной совместимости.

Для перехода на новую документацию:
1. Обновите все ссылки на документы
2. Проверьте работоспособность всех ссылок
3. Убедитесь, что вся информация актуальна
4. Удалите старую документацию (опционально)
