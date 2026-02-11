#!/usr/bin/env python
"""
Тест OAuth-флоу YooKassa без браузера.

Что делает:
  1. Показывает URL для ручного открытия в браузере (шаг авторизации)
  2. Принимает code из командной строки (скопировать из адресной строки после редиректа)
  3. Обменивает code → токен
  4. Сохраняет токен в БД для указанного клиента
  5. Регистрирует вебхуки

Запуск:
    python yookassa_oauth_package/scripts/test_oauth_flow.py --client-id 1

Затем следуй инструкциям в консоли.
"""

import os
import sys
import argparse
import uuid

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


def get_auth_url(client_uuid: str) -> str:
    client_id = getattr(settings, "YOOKASSA_CLIENT_ID", "")
    if not client_id:
        raise ValueError("YOOKASSA_CLIENT_ID не задан в settings")
    return (
        f"https://yookassa.ru/oauth/v2/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&state={client_uuid}"
    )


def exchange_code_for_token(code: str) -> str:
    oauth_client_id = getattr(settings, "YOOKASSA_CLIENT_ID", "")
    oauth_client_secret = getattr(settings, "YOOKASSA_CLIENT_SECRET", "")

    if not oauth_client_id or not oauth_client_secret:
        raise ValueError("YOOKASSA_CLIENT_ID или YOOKASSA_CLIENT_SECRET не заданы")

    resp = requests.post(
        "https://yookassa.ru/oauth/v2/token",
        auth=(oauth_client_id, oauth_client_secret),
        data={"grant_type": "authorization_code", "code": code},
        timeout=15,
    )

    if resp.status_code != 200:
        raise ValueError(f"Ошибка обмена кода: HTTP {resp.status_code}\n{resp.text}")

    data = resp.json()
    token = data.get("access_token")
    if not token:
        raise ValueError(f"access_token не получен. Ответ: {data}")

    return token


def register_webhooks(client, token: str):
    webhook_url = (
        f"{getattr(settings, 'SITE_BASE_URL', '').rstrip('/')}"
        f"/api/payments/webhook/{client.uuid}/"
    )
    events = ["payment.succeeded", "payment.canceled", "payment.waiting_for_capture"]

    print(f"\n  Регистрируем вебхуки на: {webhook_url}")
    for event in events:
        resp = requests.post(
            "https://api.yookassa.ru/v3/webhooks",
            headers={
                "Authorization": f"Bearer {token}",
                "Idempotence-Key": str(uuid.uuid4()),
                "Content-Type": "application/json",
            },
            json={"event": event, "url": webhook_url},
            timeout=10,
        )
        status = "✅" if resp.status_code in (200, 201, 409) else "❌"
        print(f"  {status}  {event} → HTTP {resp.status_code}")


def main():
    parser = argparse.ArgumentParser(description="Тест OAuth-флоу YooKassa")
    parser.add_argument("--client-id", type=int, required=True, help="ID клиента в БД")
    parser.add_argument("--code", type=str, help="Код подтверждения (если уже есть)")
    parser.add_argument("--save", action="store_true", default=True,
                        help="Сохранить токен в БД (по умолчанию: да)")
    args = parser.parse_args()

    from core.models import Client

    try:
        client = Client.objects.get(id=args.client_id)
    except Client.DoesNotExist:
        print(f"❌ Клиент с id={args.client_id} не найден")
        sys.exit(1)

    print(f"\n{'=' * 55}")
    print(f"  OAuth-тест для клиента: {client.name} (id={client.id})")
    print(f"  UUID: {client.uuid}")
    print(f"{'=' * 55}\n")

    code = args.code

    if not code:
        # Шаг 1: показываем URL для авторизации
        try:
            auth_url = get_auth_url(str(client.uuid))
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)

        print("Шаг 1. Открой эту ссылку в браузере:")
        print(f"\n  {auth_url}\n")
        print("Шаг 2. Залогинься в кабинет YooKassa клиента и нажми «Разрешить»")
        print("Шаг 3. После редиректа скопируй значение параметра 'code' из адресной строки")
        print("        Адрес будет выглядеть примерно так:")
        print(f"        https://yourapp.com/api/payments/yookassa/callback/?code=XXXXXX&state={client.uuid}")
        print()
        code = input("Введи код (code=...): ").strip()
        # Очищаем если вставили "code=XXXX" целиком
        if code.startswith("code="):
            code = code[5:]

    if not code:
        print("❌ Код не введён")
        sys.exit(1)

    print(f"\nОбмениваем code → токен...")
    try:
        token = exchange_code_for_token(code)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"✅ Токен получен: ***{token[-8:]}")

    if args.save:
        client.yookassa_oauth_token = token
        client.yookassa_connected = True
        client.save(update_fields=["yookassa_oauth_token", "yookassa_connected"])
        print(f"✅ Токен сохранён в БД для клиента id={client.id}")

    register_webhooks(client, token)

    print(f"\n{'=' * 55}")
    print(f"  ✅  OAuth подключён для клиента {client.name}")
    print(f"{'=' * 55}\n")


if __name__ == "__main__":
    main()
