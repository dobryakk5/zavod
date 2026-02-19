# CRM Refactor Plan (P1-P2)

## Контекст и принятые ограничения

- Целевая CRM-ветка: только текущая рабочая ветка, подключенная через `backend/api/urls.py` и используемая фронтом через `frontend/lib/api/crm.ts`.
- Все альтернативные/параллельные CRM-контуры (legacy и не подключенные ветки) не развиваем, только выводим из эксплуатации.
- Raw SQL в CRM должен быть заменен на слой ORM + сервисы/репозитории без изменения внешнего API-контракта.

## Цели

1. Оставить один source of truth для CRM API и убрать архитектурное расщепление.
2. Полностью убрать Raw SQL из активной CRM-ветки, сохранив поведение и совместимость по endpoint-ам.
3. Подготовить архитектуру для дальнейшего развития без повторного смешивания transport/domain/data access.

---

## Priority 1. Консолидация CRM в одну рабочую ветку

### P1.1. Зафиксировать целевой API-контракт (до рефакторинга)

- Снять полный реестр endpoint-ов CRM из `backend/api/urls.py` (`/crm/...`).
- Для каждого endpoint зафиксировать:
  - метод(ы), request/response schema,
  - коды ошибок,
  - обязательные поля,
  - особенности backward compatibility (например `contactId/tagId` vs `contact_id/tag_id`).
- Сформировать contract snapshot (Markdown + JSON-примеры).

Результат:
- артефакт `docs/docs-new/01-architecture/crm-api-contract-snapshot.md`.

Критерий готовности:
- любой endpoint из текущего CRM можно восстановить из snapshot без чтения кода.

### P1.2. Инвентаризация и отсечение нецелевых CRM-контуров

- Отметить как `deprecated` и запланировать удаление для:
  - `backend/core/api/v1/crm/*` (если не участвует в роутинге),
  - `backend/api/views_clients.py` и `backend/api/urls_map_crm.py` (если не используются runtime),
  - дублирующих frontend API клиентов (`mapClients.ts`, `mapContacts.ts`) в части CRM-операций.
- Добавить явную архитектурную запись "единственный CRM-контур".

Результат:
- ADR/решение: `docs/docs-new/01-architecture/adr-single-crm-surface.md`.

Критерий готовности:
- в кодовой базе один поддерживаемый CRM API surface и один frontend CRM gateway.

### P1.3. Нормализация слоев внутри текущей CRM-ветки

- Вынести из `views_map_crm.py` доменные/валидаторные куски в:
  - `core/services/crm/...` (use-case логика),
  - `core/repositories/crm/...` (data access через ORM),
  - `api/schemas/crm/...` (DTO/serializer слой).
- Оставить в API views только:
  - auth/permission,
  - вызов use-case,
  - маппинг ответа и ошибок.

Результат:
- views становятся orchestration-only, без бизнес-логики и SQL.

Критерий готовности:
- в CRM views нет прямых бизнес-вычислений сложнее простого request mapping.

### P1.4. Тестовый каркас до миграции данных доступа

- Добавить интеграционные тесты на текущий CRM surface (API-level):
  - contacts, tags, categories, events, availability-events, payments, notes, contact-tags.
- Для каждого endpoint минимум:
  - happy path,
  - validation error,
  - permission error,
  - not found.
- Добавить smoke e2e-сценарий (контакт -> событие -> платеж -> заметка).

Результат:
- тесты фиксируют текущее поведение перед заменой SQL.

Критерий готовности:
- можно безопасно переписывать data access, не ломая контракт.

---

## Priority 2. Устранение Raw SQL из CRM

### P2.1. Спроектировать ORM-модель map CRM как единую точку доступа

- Проверить покрытие сущностей в `core.models` для `map.*`:
  - contacts,
  - crm_tags,
  - contact_tags,
  - crm_categories,
  - crm_event_types,
  - crm_events,
  - events (availability),
  - crm_payments,
  - crm_notes.
- Где моделей нет/неполные поля — добавить unmanaged модели с корректными связями и индексами.

Результат:
- полный ORM-слой для активной CRM-схемы.

Критерий готовности:
- для каждого SQL-запроса из текущего CRM есть ORM-эквивалент.

### P2.2. Ввести репозитории и transaction boundaries

- Создать `core/repositories/crm/`:
  - `contacts_repo.py`, `events_repo.py`, `payments_repo.py`, etc.
- Вынести туда QuerySet-логику, annotate/prefetch/select_related.
- Зафиксировать `transaction.atomic()` в use-case сервисах, а не во views.

Результат:
- единый data access слой вместо SQL внутри API.

Критерий готовности:
- CRM views не импортируют `connection.cursor`.

### P2.3. Вертикальная миграция endpoint-ов (по срезам)

Рекомендуемый порядок:

1. contacts + contact-tags + tags
2. categories + event-types
3. events + availability-events
4. payments
5. notes

Для каждого среза:

- Переписать CRUD на ORM/репозитории.
- Сохранить payload-формат 1:1.
- Прогнать интеграционные тесты среза.
- Снять SQL telemetry (поиск `cursor.execute`) после каждого шага.

Результат:
- постепенный безопасный отказ от Raw SQL без большого взрыва.

Критерий готовности:
- после завершения среза в соответствующих views отсутствует SQL.

### P2.4. Мультиарендность и безопасность

- В каждом репозитории enforce tenant filter на уровне QuerySet.
- Убрать динамическое SQL-формирование по schema string там, где можно закрепить через модель/db_table.
- Проверить, что нельзя обратиться к данным другого tenant через ID guessing.

Результат:
- tenant safety обеспечена на уровне data access, а не "по договоренности".

Критерий готовности:
- negative tests на cross-tenant доступ стабильны.

### P2.5. Производительность и регресс

- Для ключевых list endpoint-ов замерить:
  - SQL count,
  - p95 latency на тестовом наборе.
- Добавить `select_related/prefetch_related` и индексы при необходимости.

Результат:
- ORM-версия не хуже текущей по p95 и количеству запросов (или улучшена).

Критерий готовности:
- зафиксированные метрики до/после в отчете.

### P2.6. Финальная очистка

- Удалить/архивировать Raw SQL код в активной CRM-ветке.
- Добавить CI-check (grep-based) на запрет `connection.cursor()` в CRM API слое.
- Обновить документацию архитектуры и API.

Результат:
- запрет на возврат Raw SQL в CRM закреплен технически.

Критерий готовности:
- в CRM API слое нет `cursor.execute`, CI это контролирует.

---

## План внедрения по итерациям

### Итерация 1 (P1)

- contract snapshot,
- архитектурное решение single CRM surface,
- старт тестового каркаса.

Выход:
- зафиксированный контракт и границы.

### Итерация 2 (P2, срезы 1-2)

- ORM migration: contacts/tags/contact-tags/categories/event-types.

Выход:
- половина CRM без Raw SQL.

### Итерация 3 (P2, срезы 3-5)

- ORM migration: events/availability/payments/notes,
- perf tuning,
- cleanup + CI guardrails.

Выход:
- Raw SQL в CRM eliminated.

---

## Риски и меры

- Риск: скрытые зависимости фронта от нестабильных полей.
  - Мера: snapshot + контрактные интеграционные тесты.
- Риск: деградация производительности при наивном ORM.
  - Мера: prefetch/select_related + метрики до/после.
- Риск: поломка tenant-изоляции.
  - Мера: обязательные cross-tenant negative tests.

---

## Definition of Done (P1+P2)

- Один активный CRM API surface в backend и один CRM gateway во frontend.
- В CRM API слое отсутствуют прямые Raw SQL вызовы.
- Контракт API сохранен (или изменения задокументированы и versioned).
- Интеграционные тесты закрывают ключевые CRM endpoint-ы.
- Документация архитектуры обновлена и соответствует фактическому роутингу.
