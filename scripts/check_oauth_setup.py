#!/usr/bin/env python
"""
Проверяет, что всё необходимое для YooKassa OAuth настроено корректно.

Запуск (из корня Django-проекта):
    python yookassa_oauth_package/scripts/check_oauth_setup.py

Или через manage.py shell:
    python manage.py shell < yookassa_oauth_package/scripts/check_oauth_setup.py
"""

import os
import sys

# Настройка Django окружения
if __name__ == "__main__":
    # Попробуем найти settings автоматически
    for settings_module in ["config.settings.base", "config.settings", "settings", "project.settings"]:
        try:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings_module)
            import django
            django.setup()
            break
        except Exception:
            continue


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "✅" if ok else "❌"
    msg = f"  {status}  {label}"
    if detail:
        msg += f"\n       {detail}"
    print(msg)
    return ok


def run_checks():
    from django.conf import settings

    print("\n" + "=" * 55)
    print("  YooKassa OAuth — проверка настройки")
    print("=" * 55 + "\n")

    results = []

    # --- Проверка .env / settings ---
    print("[ Переменные окружения ]")

    client_id = getattr(settings, "YOOKASSA_CLIENT_ID", "")
    results.append(check(
        "YOOKASSA_CLIENT_ID задан",
        bool(client_id),
        f"Текущее значение: {'***' + client_id[-4:] if client_id else 'НЕ ЗАДАН'}",
    ))

    client_secret = getattr(settings, "YOOKASSA_CLIENT_SECRET", "")
    results.append(check(
        "YOOKASSA_CLIENT_SECRET задан",
        bool(client_secret),
        "Получить на yookassa.ru/oauth/v2/client" if not client_secret else "",
    ))

    site_base_url = getattr(settings, "SITE_BASE_URL", "")
    results.append(check(
        "SITE_BASE_URL задан",
        bool(site_base_url),
        f"Текущее значение: {site_base_url or 'НЕ ЗАДАН'}",
    ))

    if site_base_url:
        results.append(check(
            "SITE_BASE_URL использует HTTPS",
            site_base_url.startswith("https://"),
            f"Текущее: {site_base_url}" if not site_base_url.startswith("https://") else "",
        ))
        results.append(check(
            "SITE_BASE_URL не заканчивается на /",
            not site_base_url.endswith("/"),
            f"Убери слэш в конце: {site_base_url}",
        ))

    fallback_shop_id = getattr(settings, "YOOKASSA_SHOP_ID", "")
    fallback_secret = getattr(settings, "YOOKASSA_SECRET_KEY", "")
    results.append(check(
        "Fallback ключи (YOOKASSA_SHOP_ID / SECRET_KEY) присутствуют",
        bool(fallback_shop_id and fallback_secret),
        "Нужны как fallback для старых платежей и клиентов без OAuth",
    ))

    print()

    # --- Проверка моделей ---
    print("[ Модели Django ]")

    try:
        from core.models import Client

        # Проверяем наличие новых полей
        client_fields = [f.name for f in Client._meta.get_fields()]

        for field_name in ["uuid", "yookassa_oauth_token", "yookassa_connected",
                           "yookassa_shop_id", "yookassa_secret_key", "yookassa_return_url"]:
            results.append(check(
                f"Client.{field_name} существует",
                field_name in client_fields,
                "Добавь поле из client_fields.py и выполни makemigrations" if field_name not in client_fields else "",
            ))
    except ImportError as e:
        results.append(check("Импорт core.models.Client", False, str(e)))

    try:
        from core.models import YooKassaPayment
        results.append(check("Модель YooKassaPayment существует", True))

        # Проверяем что таблица создана
        try:
            count = YooKassaPayment.objects.count()
            results.append(check(f"Таблица YooKassaPayment доступна (записей: {count})", True))
        except Exception as e:
            results.append(check("Таблица YooKassaPayment доступна", False,
                                 f"Возможно не выполнена миграция: {e}"))
    except ImportError:
        results.append(check(
            "Модель YooKassaPayment существует",
            False,
            "Добавь модель из yookassa_payment.py и выполни makemigrations",
        ))

    print()

    # --- Проверка URLs ---
    print("[ URL-маршруты ]")

    try:
        from django.urls import reverse
        for url_name, name_label in [
            ("api:yookassa-oauth-connect",   "yookassa-oauth-connect"),
            ("api:yookassa-oauth-callback",  "yookassa-oauth-callback"),
            ("api:yookassa-oauth-disconnect","yookassa-oauth-disconnect"),
            ("api:yookassa-credentials",     "yookassa-credentials"),
            ("api:yookassa-webhook-client",  "yookassa-webhook-client"),
        ]:
            try:
                if "webhook-client" in url_name:
                    import uuid as uuid_mod
                    url = reverse(url_name, kwargs={"client_uuid": uuid_mod.uuid4()})
                else:
                    url = reverse(url_name)
                results.append(check(f"URL {name_label}", True, url))
            except Exception:
                results.append(check(
                    f"URL {name_label}",
                    False,
                    f"Добавь путь в api/urls.py",
                ))
    except Exception as e:
        results.append(check("Проверка URLs", False, str(e)))

    print()

    # --- Проверка Callback URL ---
    print("[ Callback URL ]")

    if site_base_url:
        callback_url = f"{site_base_url}/api/payments/yookassa/callback/"
        print(f"  ℹ️  Callback URL для YooKassa:")
        print(f"       {callback_url}")
        print(f"  ℹ️  Убедись, что именно этот URL указан в настройках OAuth-приложения")
        print(f"       на https://yookassa.ru/oauth/v2/client")

    print()

    # --- Итог ---
    total = len(results)
    passed = sum(results)
    failed = total - passed

    print("=" * 55)
    if failed == 0:
        print(f"  ✅  Все проверки пройдены ({passed}/{total})")
        print("  Можно тестировать OAuth-флоу с реальным клиентом.")
    else:
        print(f"  ❌  Проблемы найдены: {failed} из {total} проверок не прошли")
        print("  Исправь ошибки выше и запусти проверку повторно.")
    print("=" * 55 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)
