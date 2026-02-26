# Спецификация интеграции CRM с Bitrix24 (Contacts)

Дата: 2026-02-26
Статус: draft (MVP design)

## Цель

Добавить интеграцию Bitrix24 CRM для контактов по тому же паттерну, что и amoCRM:

- OAuth2 подключение Bitrix24 аккаунта
- синхронизация `CRMClient -> Bitrix24 Contact`
- webhook из Bitrix24 на изменения контактов
- логирование ошибок/операций
- ручной `resync`

## Область MVP

В MVP поддерживаем только сущность `Contact`.

Входит:
- подключение/отключение портала Bitrix24
- хранение и обновление OAuth токенов
- push контакта из Zavod в Bitrix24 (create/update)
- inbound webhook `ONCRMCONTACTADD|UPDATE|DELETE`
- pull контакта по webhook (`crm.contact.get`) и обновление локального `CRMClient` (для замапленных записей)
- ручной ресинк одного контакта и полного набора
- логи + идемпотентность обработки

Не входит (можно позже):
- компании/сделки/лиды
- авто-создание кастомных полей `UF_CRM_*`
- двусторонний sync для всех полей/сложная conflict-resolution политика
- offline events (`event_type=offline`)

## Связь с текущей архитектурой

В проекте уже есть паттерн для amoCRM:
- `backend/core/models/amocrm.py`
  - `AmoCRMAccount`
  - `AmoCRMContactMapping`
  - `AmoCRMLogEntry`

Для Bitrix24 используем тот же shape данных и сервисов (отдельный provider/адаптер, но одинаковые слои):
- `Auth`
- `ContactMapper`
- `SyncService`
- `WebhookHandler`
- `ResyncService`
- `LogService`

## Целевая модель данных (аналогично amoCRM)

### 1. `Bitrix24Account`

Назначение: подключенный портал Bitrix24 + OAuth + состояние интеграции.

Рекомендуемые поля:
- `client` (FK -> `core.Client`)
- `created_by` (FK -> user)
- `portal_domain` (например `example.bitrix24.ru`, `example.bitrix24.com`)
- `member_id` (уникальный идентификатор портала, предпочтительный ключ для стабильной идентификации)
- `account_name` (опционально)
- `client_endpoint` (например `https://portal.bitrix24.com/rest/`)
- `server_endpoint` (обычно `https://oauth.bitrix.info/rest/`)
- `access_token`
- `refresh_token`
- `expires_at`
- `scope` (`JSON/list`)
- `application_token` (для валидации webhook handler)
- `status` (`active|error|revoked`)
- `last_sync_at`
- `last_error`
- `metadata` (JSON)
- `created_at`, `updated_at`

Ключевые ограничения/индексы:
- `UNIQUE (client_id, member_id)`
- `UNIQUE (member_id)` (если один портал нельзя подключать к нескольким tenants)
- index по `(client_id, status)`

### 2. `Bitrix24ContactMapping`

Назначение: соответствие локального `CRMClient` и `Bitrix24 Contact`.

Рекомендуемые поля:
- `account` (FK -> `Bitrix24Account`)
- `crm_client` (FK -> `CRMClient`)
- `bitrix_contact_id` (bigint)
- `last_synced_at`
- `last_webhook_at`
- `sync_hash` (hash нормализованных синкаемых полей)
- `remote_updated_at` (если удается стабильно читать из Bitrix)
- `metadata` (JSON)
- `created_at`, `updated_at`

Ключевые ограничения/индексы:
- `UNIQUE (account_id, crm_client_id)`
- `UNIQUE (account_id, bitrix_contact_id)`
- index `(account_id, last_synced_at)`

### 3. `Bitrix24LogEntry`

Назначение: аудит операций OAuth/sync/webhook/resync и ошибок.

Рекомендуемые поля (повторить shape amoCRM лога):
- `client`, `account`, `crm_client`, `mapping`
- `source` (`oauth|sync|webhook|resync`)
- `action` (например `oauth.exchange`, `contact.push.create`, `webhook.contact.update`)
- `level` (`info|warning|error`)
- `status` (`queued|success|error|skipped`)
- `message`
- `payload` (JSON, с редактированием секретов)
- `error_code`
- `idempotency_key`
- `created_at`

Индексы:
- `(client_id, created_at)`
- `(account_id, created_at)`
- `(level, status)`
- `idempotency_key`

### 4. `Bitrix24WebhookEvent` (рекомендуется, даже для MVP)

Назначение: dedup/replay входящих событий и безопасная ретри-обработка.

Рекомендуемые поля:
- `account` (FK)
- `event_name` (`ONCRMCONTACTUPDATE`, ...)
- `event_handler_id`
- `remote_entity_id` (`data.FIELDS.ID`)
- `ts` (timestamp из payload)
- `idempotency_key`
- `payload` (JSON)
- `status` (`received|processing|done|failed|ignored`)
- `attempts`
- `last_error`
- `processed_at`
- `created_at`

Идемпотентность:
- `UNIQUE (account_id, idempotency_key)`
- ключ формировать из `event + event_handler_id + ts + entity_id`

## Маппинг полей `CRMClient` -> Bitrix24 Contact

Исходная локальная модель: `backend/core/models/crm.py` (`CRMClient`).

Минимальный маппинг MVP:
- `CRMClient.first_name` -> `NAME`
- `CRMClient.last_name` -> `LAST_NAME`
- `CRMClient.phone` -> `PHONE` (multiple field, массив объектов `{VALUE, VALUE_TYPE}`)
- `CRMClient.email` -> `EMAIL` (multiple field, массив объектов `{VALUE, VALUE_TYPE}`)
- `CRMClient.notes` -> `COMMENTS`
- `CRMClient.photo_url` -> `WEB` или пропустить в MVP (рекомендуется пропустить)
- `CRMClient.status` -> кастомное поле `UF_CRM_ZAVOD_STATUS` (опционально, не MVP)
- `CRMClient.category_id` -> кастомное поле `UF_CRM_ZAVOD_CATEGORY_ID` (опционально, не MVP)

Внутренние технические поля (опционально, phase 2):
- `UF_CRM_ZAVOD_CLIENT_ID` = `core.Client.id`
- `UF_CRM_ZAVOD_CRM_CLIENT_ID` = `CRMClient.id`

Примечание:
- В MVP не полагаемся на `UF_CRM_*` для корректности синка; основным источником связки остается локальная таблица `Bitrix24ContactMapping`.

## Внешние методы Bitrix24 (MVP)

### OAuth2

Используем полноценный OAuth2 (не local incoming webhook), чтобы поддержать:
- обновление токенов
- `event.bind`
- стабильную интеграцию с UI/настройками

Основные шаги:
1. Redirect пользователя на портал:
   - `https://{portal}/oauth/authorize/?client_id=...&state=...`
2. Получить `code` в callback (срок жизни кода короткий, использовать сразу)
3. Обменять `code` на токены через auth server:
   - `https://oauth.bitrix.info/oauth/token/?grant_type=authorization_code&client_id=...&client_secret=...&code=...`
4. Обновлять токены через:
   - `https://oauth.bitrix.info/oauth/token/?grant_type=refresh_token&client_id=...&client_secret=...&refresh_token=...`

Что сохраняем из ответа:
- `access_token`
- `refresh_token`
- `expires_in` -> `expires_at`
- `client_endpoint`
- `server_endpoint`
- `member_id`
- `scope`
- `status`

### Contacts API

Базовые методы:
- `crm.contact.fields` — схема полей (в т.ч. custom fields)
- `crm.contact.list` — поиск/листинг контактов
- `crm.contact.get` — получить контакт по ID
- `crm.contact.add` — создать контакт
- `crm.contact.update` — обновить контакт
- `crm.contact.delete` — удалить контакт (необязательно вызывать в MVP)

Примечание:
- В официальной документации `crm.contact.*` помечены как методы, развитие которых остановлено (есть более новый `crm.item.*`).
- Для MVP допустимо использовать `crm.contact.*` (проще и напрямую соответствует задаче Contacts), а миграцию на `crm.item.*` запланировать отдельным этапом.

### Events API

Для подписки/управления подписками:
- `event.bind`
- `event.get`
- `event.unbind`

События для подписки (Contacts):
- `ONCRMCONTACTADD`
- `ONCRMCONTACTUPDATE`
- `ONCRMCONTACTDELETE`

## Webhook / Event Handling

### Что приходит от Bitrix24

Событие приходит POST-запросом и содержит (типовой payload):
- `event` (например `ONCRMCONTACTUPDATE`)
- `event_handler_id`
- `data.FIELDS.ID` (ID контакта в Bitrix24)
- `ts`
- `auth` (может содержать `access_token`, `member_id`, `application_token`, `client_endpoint`, и т.д.)

Важно:
- токены в `auth` могут приходить не всегда, поэтому нельзя строить интеграцию только на webhook-token payload
- хранить собственные токены из OAuth установки обязательно

### Безопасность webhook handler

Минимум для MVP:
- найти аккаунт по `auth.member_id` (или fallback по домену)
- проверить `auth.application_token == Bitrix24Account.application_token` (если есть)
- логировать отклоненные события как `warning`

Если `auth` неполный:
- допускается fallback-поиск по домену (`auth.domain`) + строгий allowlist handler URL/route
- при невозможности идентифицировать аккаунт — `ignored + log`

### Идемпотентность и anti-loop

Нужно обязательно:
- dedup входящих событий по `idempotency_key`
- хранить `sync_hash` в mapping
- перед outbound update сравнивать новый hash с `mapping.sync_hash`; если совпадает — `skip`
- после inbound pull обновлять `mapping.sync_hash`

Чтобы избежать ping-pong (мы обновили Bitrix -> получили webhook -> снова обновили локально -> снова push):
- webhook handler не делает прямой обратный push
- webhook handler делает `pull remote -> merge local` и обновляет hash
- outbound sync пропускает push, если hash совпадает

## Потоки (flows)

### 1. Подключение аккаунта Bitrix24 (OAuth2)

1. Пользователь открывает настройки интеграции
2. Вводит/подтверждает `portal_domain`
3. Backend создает `state`, редиректит на `{portal}/oauth/authorize`
4. Callback получает `code`, `domain`, `member_id`
5. Backend вызывает `oauth.bitrix.info/oauth/token` (`authorization_code`)
6. Создает/обновляет `Bitrix24Account`
7. Вызывает `event.bind` для 3 contact events
8. Сохраняет `application_token` (из install/webhook auth payload или при первом событии)
9. Пишет `Bitrix24LogEntry(source=oauth, action=oauth.connect)`

### 2. Outbound sync `CRMClient -> Bitrix24`

Триггеры:
- ручной resync
- изменение `CRMClient` (signal/explicit service call)
- bulk task

Алгоритм:
1. Выбрать `Bitrix24Account` клиента (`status=active`)
2. Нормализовать поля через `ContactMapper`
3. Найти mapping:
   - если нет -> `crm.contact.add`
   - если есть -> `crm.contact.update`
4. При `add` сохранить `bitrix_contact_id` в mapping
5. Обновить `sync_hash`, `last_synced_at`
6. Записать лог (`contact.push.create` / `contact.push.update`)

Fallback дедуп при отсутствии mapping (опционально phase 2):
- поиск через `crm.contact.list` по точному `PHONE`/`EMAIL`
- если найден 1 контакт -> привязать mapping вместо создания дубля

### 3. Inbound webhook `Bitrix24 -> Zavod`

Триггер: `ONCRMCONTACTADD|UPDATE|DELETE`

Алгоритм:
1. Принять POST
2. Идентифицировать `Bitrix24Account`
3. Проверить безопасность (`application_token`, если доступен)
4. Сформировать `idempotency_key`, upsert в `Bitrix24WebhookEvent`
5. Если дубликат — `200 OK`, `skipped`
6. Для `ADD/UPDATE`:
   - вызвать `crm.contact.get(id)`
   - найти mapping по `(account, bitrix_contact_id)`
   - если mapping нет: логировать `unmapped_remote_contact` (MVP можно не создавать локальный `CRMClient` автоматически)
   - если mapping есть: обновить локальный `CRMClient` по разрешенным полям
7. Для `DELETE`:
   - в MVP не удалять локальный `CRMClient`; пометить в `mapping.metadata.remote_deleted=true`
8. Обновить `last_webhook_at`, `sync_hash`, статус события `done`

## Конфликтная политика (MVP)

MVP policy: `local-first` с ограниченным inbound merge.

Правила:
- Zavod (`CRMClient`) — источник правды для outbound sync
- webhook updates из Bitrix24 применяются только к полям, разрешенным для inbound merge (`first_name`, `last_name`, `phone`, `email`, `notes`)
- если локальная запись изменилась позже последнего sync и есть риск конфликта, логируем `conflict_detected` и используем правило:
  - MVP: `last-write-wins` на стороне inbound merge, но с логом уровня `warning`

Phase 2 (лучше):
- field-level conflict strategy
- явный `source_of_truth` per integration/account

## Ручной `resync`

### Варианты операций

1. `push_contact`
- вход: `crm_client_id`
- действие: перепушить локальный контакт в Bitrix24 (create/update)

2. `pull_contact`
- вход: `bitrix_contact_id` или `crm_client_id`
- действие: получить контакт из Bitrix24 и обновить локальный

3. `full_export`
- действие: пройти все `CRMClient` tenant-а и синхронизировать в Bitrix24 пакетами

4. `rebind_webhooks`
- действие: проверить `event.get`, зарегистрировать отсутствующие события

### API (внутренний backend, предлагаемая форма)

Рекомендуемый surface (пример):
- `POST /api/integrations/bitrix24/connect/`
- `GET /api/integrations/bitrix24/callback/`
- `POST /api/integrations/bitrix24/disconnect/`
- `GET /api/integrations/bitrix24/accounts/`
- `POST /api/integrations/bitrix24/accounts/{id}/resync/`
- `POST /api/integrations/bitrix24/webhook/{account_id_or_secret}/`

`resync` body (пример):
```json
{
  "mode": "push_contact",
  "crm_client_id": 123,
  "force": true,
  "dry_run": false
}
```

## Ошибки, retry и rate limiting

### Обязательная обработка ошибок Bitrix24

Минимум:
- `expired_token` -> refresh token + retry 1 раз
- `QUERY_LIMIT_EXCEEDED` -> exponential backoff + retry
- `INVALID_CREDENTIALS` / `user_access_error` -> пометить аккаунт `error`, лог
- `ACCESS_DENIED` -> лог + показать в UI (план/права)
- `insufficient_scope` -> лог + подсказка на переподключение с нужными scope
- `OVERLOAD_LIMIT` -> backoff + прекращение bulk-задачи

### Лимиты (учесть в реализации)

Bitrix24 (cloud) docs указывает:
- list methods возвращают страницы (обычно до 50 записей)
- использовать `next` -> параметр `start` для пагинации
- `batch` поддерживает до 50 подзапросов
- для cloud есть лимиты интенсивности (`QUERY_LIMIT_EXCEEDED`) и лимиты потребления ресурсов

Практика для MVP:
- один rate-limiter на `Bitrix24Account`
- Celery task queue per account (или lock per account)
- bulk sync батчами по 20-50 контактов с паузами

## Нормализация данных

Перед сравнением и `sync_hash`:
- `phone`: убрать пробелы/скобки/дефисы, привести к канонической форме (например E.164 если возможно)
- `email`: lower-case, trim
- строки: trim, пустые -> `null`

`sync_hash` считать от нормализованного payload, например:
- `first_name`, `last_name`, `phone`, `email`, `notes`

## Набор сервисов/модулей (рекомендуемая структура)

Примерно:
- `backend/core/models/bitrix24.py`
- `backend/core/services/bitrix24/auth_service.py`
- `backend/core/services/bitrix24/client.py` (HTTP wrapper + retry + refresh)
- `backend/core/services/bitrix24/contact_mapper.py`
- `backend/core/services/bitrix24/sync_service.py`
- `backend/core/services/bitrix24/webhook_service.py`
- `backend/core/services/bitrix24/resync_service.py`
- `backend/api/views_bitrix24.py`
- `backend/core/migrations/XXXX_bitrix24_integration_mvp.py`

Важно:
- HTTP wrapper должен централизованно делать refresh токена и retry
- Логи писать через единый helper, чтобы payload очищался от секретов (`access_token`, `refresh_token`)

## Минимальные тест-кейсы (MVP)

### Unit
- `ContactMapper`: локальные поля -> payload Bitrix24
- нормализация `phone/email`
- `sync_hash` стабильный для эквивалентных значений
- idempotency key generation

### Integration (backend)
- OAuth callback: успешный обмен `code` и сохранение account
- refresh token path при `expired_token`
- `crm.contact.add` создает mapping
- `crm.contact.update` не вызывается при одинаковом `sync_hash`
- webhook duplicate event не обрабатывается дважды
- webhook `ONCRMCONTACTUPDATE` обновляет локальный `CRMClient` для existing mapping
- webhook unmapped contact -> лог `warning`, без падения

## Rollout план

### Phase 1 (MVP)
- модели + миграции (`Bitrix24Account`, `Bitrix24ContactMapping`, `Bitrix24LogEntry`, `Bitrix24WebhookEvent`)
- OAuth connect/disconnect/callback
- `crm.contact.add/update/get`
- `event.bind` для 3 contact events
- webhook endpoint + idempotency
- ручной `push_contact`, `pull_contact`

### Phase 2 (Hardening)
- `event.get`/`event.unbind`/rebind диагностика
- bulk `full_export` с батчами и rate limit orchestration
- UI статусы интеграции + логи + кнопка resync
- кастомные поля `UF_CRM_*` и расширенный маппинг
- auto-recovery и health checks

## Открытые решения (нужно подтвердить перед кодом)

1. Направление синка по умолчанию:
- `local-first` (предложено в этом документе)
- или полноценный bi-directional

2. Создавать ли локальный `CRMClient`, если webhook пришел на незамапленный Bitrix24 контакт:
- MVP предлагает `нет` (лог + manual link/resync)
- альтернатива: auto-import

3. Где разместить API surface:
- `/api/integrations/bitrix24/...` (предпочтительно, ближе к существующим integration views)
- или `/api/crm/integrations/bitrix24/...` (если хотите держать все CRM-связанное в CRM namespace)

## Полезные официальные страницы (Bitrix24)

- OAuth (полный flow): `https://apidocs.bitrix24.com/settings/oauth/index.html`
- OAuth refresh: `https://apidocs.bitrix24.com/settings/oauth/auto-renewal.html`
- REST authorization overview: `https://apidocs.bitrix24.com/settings/how-to-call-rest-api/authorization.html`
- List pagination (`next`/`start`): `https://apidocs.bitrix24.com/settings/how-to-call-rest-api/list-methods-pecularities.html`
- Batch (до 50 команд): `https://apidocs.bitrix24.com/settings/how-to-call-rest-api/batch.html`
- Limits / `QUERY_LIMIT_EXCEEDED`: `https://apidocs.bitrix24.com/settings/performance/limits.html`
- `event.bind`: `https://apidocs.bitrix24.com/api-reference/events/event-bind.html`
- Security in handlers (`application_token`): `https://apidocs.bitrix24.com/api-reference/events/safe-event-handlers.html`
- `crm.contact.list`: `https://apidocs.bitrix24.com/api-reference/crm/contacts/crm-contact-list.html`
- `crm.contact.get`: `https://apidocs.bitrix24.com/api-reference/crm/contacts/crm-contact-get.html`
- `crm.contact.add`: `https://apidocs.bitrix24.com/api-reference/crm/contacts/crm-contact-add.html`
- `crm.contact.update`: `https://apidocs.bitrix24.com/api-reference/crm/contacts/crm-contact-update.html`
- `crm.contact.fields`: `https://apidocs.bitrix24.com/api-reference/crm/contacts/crm-contact-fields.html`
- Contact events (`onCrmContact*`): `https://apidocs.bitrix24.com/api-reference/crm/contacts/events/index.html`
