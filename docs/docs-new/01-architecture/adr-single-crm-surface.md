# ADR: Single CRM API Surface

## Status
Accepted

## Date
2026-02-19

## Context

В кодовой базе исторически существовали несколько CRM-контуров:

- активный `api.urls` (`/api/crm/...`),
- legacy-модули (`api/views_clients.py`, `api/urls_map_crm.py`),
- отдельная ветка `core/api/v1/crm/*` (не подключена в корневом роутинге).

Это создавало риск расщепления логики, контрактов и тестов.

## Decision

Единственным поддерживаемым CRM surface считается:

- backend: маршруты `/api/crm/...` из `backend/api/urls.py`;
- frontend: единый CRM gateway из `frontend/lib/api/crm.ts`.

Дополнительно:

- Raw SQL в активном CRM surface подлежит поэтапной замене на ORM.
- Неподключенные/legacy CRM-контуры считаются deprecated и не развиваются.

## Consequences

### Positive

- Один источник правды для API-контрактов.
- Проще тестирование и регрессионный контроль.
- Меньше риска разъезда поведения между экранами.

### Negative

- Нужно провести миграцию оставшихся raw SQL endpoint-ов на ORM.
- Нужно вычистить дублирующиеся frontend gateways (`map*` -> `crm.ts`).

## Rollout Notes

1. Зафиксировать контракт текущего `/api/crm/...`.
2. Переключить endpoint-ы raw SQL на ORM реализации.
3. Удалить/архивировать deprecated CRM-контуры после стабилизации.
