#!/usr/bin/env python
"""
Регистрирует вебхуки YooKassa для существующих клиентов.

Нужен если:
  - у клиентов уже есть ключи (OAuth-токен или ручные shop_id/secret_key)
  - но вебхуки ещё не были зарегистрированы

Запуск (из корня Django-проекта):

    # Для всех подключённых клиентов
    python yookassa_oauth_package/scripts/register_webhooks.py --all

    # Для конкретного клиента по id
    python yookassa_oauth_package/scripts/register_webhooks.py --client-id 42

    # Dry-run (показать что будет, ничего не делать)
    python yookassa_oauth_package/scripts/register_webhooks.py --all --dry-run
"""

import os
import sys
import argparse
import uuid

# Настройка Django
for settings_module in ["config.settings.base", "config.settings", "settings"]:
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
        import django
        django.setup()
        break
    except Exception:
        continue

import requests
from django.conf import settings


def get_credentials(client):
    """Возвращает (shop_id, secret_or_token, auth_type) для клиента."""
    if getattr(client, "yookassa_oauth_token", None):
        return "", client.yookassa_oauth_token, "bearer"
    if getattr(client, "yookassa_shop_id", None) and getattr(client, "yookassa_secret_key", None):
        return client.yookassa_shop_id, client.yookassa_secret_key, "basic"
    return None, None, None


def build_request_kwargs(shop_id, secret_or_token, auth_type, idempotence_key):
    headers = {
        "Idempotence-Key": idempotence_key,
        "Content-Type": "application/json",
    }
    if auth_type == "bearer":
        headers["Authorization"] = f"Bearer {secret_or_token}"
        return {"headers": headers}
    return {"auth": (shop_id, secret_or_token), "headers": headers}


def get_webhook_url(client):
    base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    return f"{base}/api/payments/webhook/{client.uuid}/"


def register_webhooks_for_client(client, dry_run=False):
    shop_id, secret_or_token, auth_type = get_credentials(client)

    if not secret_or_token:
        print(f"  ⚠️  client_id={client.id} ({client.name}): нет ключей, пропускаем")
        return False

    webhook_url = get_webhook_url(client)
    events = [
        "payment.succeeded",
        "payment.canceled",
        "payment.waiting_for_capture",
    ]

    print(f"\n  📋  client_id={client.id} ({client.name})")
    print(f"       auth_type: {auth_type}")
    print(f"       webhook_url: {webhook_url}")

    if dry_run:
        print(f"       [dry-run] зарегистрировал бы {len(events)} вебхука(ов)")
        return True

    success_count = 0
    for event in events:
        idem_key = str(uuid.uuid4())
        kwargs = build_request_kwargs(shop_id, secret_or_token, auth_type, idem_key)

        try:
            resp = requests.post(
                "https://api.yookassa.ru/v3/webhooks",
                json={"event": event, "url": webhook_url},
                timeout=10,
                **kwargs,
            )
            if resp.status_code in (200, 201):
                print(f"       ✅  {event}")
                success_count += 1
            elif resp.status_code == 409:
                # Вебхук уже существует — это нормально
                print(f"       ✓   {event} (уже зарегистрирован)")
                success_count += 1
            else:
                print(f"       ❌  {event} → HTTP {resp.status_code}: {resp.text[:100]}")
        except requests.RequestException as e:
            print(f"       ❌  {event} → Ошибка запроса: {e}")

    return success_count == len(events)


def main():
    parser = argparse.ArgumentParser(description="Регистрация вебхуков YooKassa для клиентов")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Все подключённые клиенты")
    group.add_argument("--client-id", type=int, help="Конкретный client.id")
    parser.add_argument("--dry-run", action="store_true", help="Не делать реальных запросов")
    args = parser.parse_args()

    from core.models import Client

    if args.dry_run:
        print("\n⚠️  Режим dry-run — реальных запросов не будет\n")

    if args.all:
        # Клиенты у которых есть хоть какие-то ключи
        clients = Client.objects.filter(
            yookassa_connected=True
        ).exclude(
            yookassa_oauth_token=None,
            yookassa_shop_id=None,
        )
        print(f"Найдено клиентов с YooKassa: {clients.count()}")
    else:
        clients = Client.objects.filter(id=args.client_id)
        if not clients.exists():
            print(f"❌ Клиент с id={args.client_id} не найден")
            sys.exit(1)

    success_total = 0
    fail_total = 0

    for client in clients:
        ok = register_webhooks_for_client(client, dry_run=args.dry_run)
        if ok:
            success_total += 1
        else:
            fail_total += 1

    print(f"\n{'=' * 40}")
    print(f"Итого: ✅ {success_total} успешно, ❌ {fail_total} с ошибками")
    print(f"{'=' * 40}\n")


if __name__ == "__main__":
    main()
