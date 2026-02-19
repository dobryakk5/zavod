# CRM API Contract Snapshot

Snapshot date: 2026-02-19

Base path: `/api/crm/`

## Contacts

- `GET /contacts/` -> `Contact[]`
- `POST /contacts/` -> `Contact`
- `GET /contacts/{id}/` -> `Contact`
- `PATCH /contacts/{id}/` -> `Contact`
- `DELETE /contacts/{id}/` -> `204`
- `GET /contacts/{id}/telegram-link/` -> `{ contact_id, tenant_id, telegram_chat_id, tg_name, is_connected, link }`

Contact fields:
`id, name, email, phone, source, category_id, status, photo_url, notes, parent_id, tags, created_at, updated_at`

## Tags

- `GET /tags/` -> `Tag[]`
- `POST /tags/` -> `Tag`
- `GET /tags/{id}/` -> `Tag`
- `PATCH /tags/{id}/` -> `Tag`
- `DELETE /tags/{id}/` -> `204`

Tag fields:
`id, type, value, created_at`

## Contact Tags

- `GET /contact-tags/?contact_id={id}` -> `ContactTag[]`
- `POST /contact-tags/` body `{ contact_id|contactId, tag_id|tagId, description? }` -> `ContactTag | {success}`
- `DELETE /contact-tags/` body `{ contact_id|contactId, tag_id|tagId }` -> `204`
- `DELETE /contact-tags/remove/` body `{ contact_id|contactId, tag_id|tagId }` -> `204`
- `DELETE /contact-tags/{id}/` -> `204`

ContactTag fields:
`id?, contact_id, tag_id, type, value, tag_type, tag_value, description`

## Categories

- `GET /categories/` -> `Category[]`
- `POST /categories/` -> `Category`
- `GET /categories/{id}/` -> `Category`
- `PATCH /categories/{id}/` -> `Category`
- `DELETE /categories/{id}/` -> `204`

Category fields:
`id, name, description, color, created_at, updated_at`

## Event Types

- `GET /event-types/` -> `EventType[]`
- `POST /event-types/` -> `EventType`
- `GET /event-types/{id}/` -> `EventType`
- `PATCH /event-types/{id}/` -> `EventType`
- `DELETE /event-types/{id}/` -> `204`

EventType fields:
`id, name, description, duration_minutes, color, created_at`

## Events

- `GET /events/` -> `Event[]`
- `POST /events/` -> `Event`
- `GET /events/{id}/` -> `Event`
- `PATCH /events/{id}/` -> `Event`
- `DELETE /events/{id}/` -> `204`

Event fields:
`id, contact_id, event_type_id, title, description, start_time, end_time, location, status, notes, price, created_at, updated_at`

Notes:
- При `POST /events/` и заполненном `price` создается/обновляется pending-платеж по `event_id`.
- При `PATCH /events/{id}/` и наличии поля `price` выполняется тот же upsert платежа.

## Availability Events

- `GET /availability-events/` -> `AvailabilityEvent[]` (tenant-scoped)
- `POST /availability-events/` -> `AvailabilityEvent` (tenant from active client)
- `GET /availability-events/{id}/` -> `AvailabilityEvent`
- `PATCH /availability-events/{id}/` -> `AvailabilityEvent`
- `DELETE /availability-events/{id}/` -> `204`

AvailabilityEvent fields:
`id, tenant_id, start_time, duration_minutes, repeat_type, created_at, updated_at`

`repeat_type` allowed: `0,1,2,3`

## Payments

- `GET /payments/` -> `Payment[]`
- `POST /payments/` -> `Payment`
- `GET /payments/{id}/` -> `Payment`
- `PATCH /payments/{id}/` -> `Payment`
- `DELETE /payments/{id}/` -> `204`

Payment fields:
`id, contact_id, event_id, product_id, amount, currency, status, payment_method, transaction_id, description, planned_at, paid_at, created_at, updated_at`

## Notes

- `GET /notes/` -> `Note[]`
- `POST /notes/` -> `Note`
- `GET /notes/{id}/` -> `Note`
- `PATCH /notes/{id}/` -> `Note`
- `DELETE /notes/{id}/` -> `204`

Note fields:
`id, contact_id, title, content, is_important, created_at, updated_at`

## Permissions

- Read operations: tenant member (`IsTenantMember`).
- Write operations (POST/PATCH/PUT/DELETE): tenant owner/editor (`IsTenantOwnerOrEditor`) for CRM resources.
