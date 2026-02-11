# Чеклист подключения YooKassa OAuth

Отмечай по порядку. Каждый пункт — конкретное действие.

---

## Регистрация приложения в YooKassa

- [ ] Зашёл на https://yookassa.ru/oauth/v2/client
- [ ] Нажал «Зарегистрировать»
- [ ] Указал название платформы (видит клиент)
- [ ] Указал Callback URL: `https://yourapp.com/api/payments/yookassa/callback/`
- [ ] Отметил доступы: Платежи (Создание + Просмотр), Возвраты (Создание + Просмотр)
- [ ] Скопировал Client ID → положил в .env как YOOKASSA_CLIENT_ID
- [ ] Скопировал Client Secret → положил в .env как YOOKASSA_CLIENT_SECRET

---

## Окружение (.env / base.py)

- [ ] YOOKASSA_CLIENT_ID задан
- [ ] YOOKASSA_CLIENT_SECRET задан
- [ ] SITE_BASE_URL задан (https://yourapp.com — без слэша в конце)
- [ ] Старые YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY оставлены (fallback)

---

## Код

- [ ] Добавлены поля в Client (uuid, yookassa_oauth_token, yookassa_connected, yookassa_shop_id, yookassa_secret_key, yookassa_return_url)
- [ ] Добавлена модель YooKassaPayment
- [ ] Выполнено makemigrations + migrate
- [ ] views_payments.py обновлён (мульти-мерчант версия)
- [ ] api/urls.py обновлён (новые 5 путей добавлены)

---

## Проверка

- [ ] `python scripts/check_oauth_setup.py` — все проверки зелёные
- [ ] `python manage.py check` — нет ошибок
- [ ] Эндпоинт GET /api/payments/yookassa/connect/ возвращает redirect_url
- [ ] Callback URL доступен по HTTPS из интернета

---

## Тест с реальным клиентом

- [ ] Клиент нажал «Подключить YooKassa»
- [ ] Редирект на YooKassa прошёл
- [ ] Клиент нажал «Разрешить»
- [ ] В БД появился yookassa_oauth_token у клиента
- [ ] yookassa_connected = True
- [ ] Вебхуки зарегистрированы (проверить через скрипт или в кабинете YooKassa клиента)
- [ ] Тестовый платёж создаётся с ключами клиента
- [ ] Вебхук приходит на /api/payments/webhook/<client_uuid>/

---------------

# YooKassa OAuth — Мульти-мерчант пакет

Пошаговая инструкция по подключению OAuth-мультимерчанта в вашу платформу.

---

## Структура пакета

```
yookassa_oauth_package/
├── README.md                          ← эта инструкция
├── CHECKLIST.md                       ← чеклист для быстрой проверки
│
├── core/
│   └── models/
│       ├── client_fields.py           ← поля для добавления в Client
│       └── yookassa_payment.py        ← новая модель YooKassaPayment
│
├── migrations_example/
│   └── 0001_yookassa_oauth_fields.py  ← пример миграции
│
├── scripts/
│   ├── check_oauth_setup.py           ← проверка настройки окружения
│   ├── register_webhooks.py           ← ручная регистрация вебхуков для клиента
│   └── test_oauth_flow.py             ← симуляция OAuth-флоу для тестов
│
└── env_example.txt                    ← что добавить в .env
```

---

## Шаг 1 — Регистрация OAuth-приложения в YooKassa (один раз)

1. Зайди на https://yookassa.ru/oauth/v2/client
2. Нажми **«Зарегистрировать»**
3. Заполни форму:
   - **Название:** название твоей платформы (видит клиент при выдаче прав)
   - **Описание:** например «Приём платежей через платформу X»
   - **Сайт:** `https://yourapp.com`
   - **Код подтверждения:** выбери «Передавать в Callback URL»
   - **Callback URL:** `https://yourapp.com/api/payments/yookassa/callback/`
4. В разделе **Доступы → API ЮKassa** отметь:
   - ✅ Платежи → Создание
   - ✅ Платежи → Просмотр
   - ✅ Возвраты → Создание
   - ✅ Возвраты → Просмотр
5. Нажми **«Зарегистрировать»**
6. Скопируй **Client ID** и **Client Secret** → положи в `.env`

---

## Шаг 2 — Обновить .env

Добавь в `.env` (см. `env_example.txt`):

```
YOOKASSA_CLIENT_ID=your_client_id_here
YOOKASSA_CLIENT_SECRET=your_client_secret_here
SITE_BASE_URL=https://yourapp.com
```

Существующие переменные оставь — они используются как fallback:
```
YOOKASSA_SHOP_ID=...      # остаётся
YOOKASSA_SECRET_KEY=...   # остаётся
YOOKASSA_RETURN_URL=...   # остаётся
```

---

## Шаг 3 — Обновить models.py

### 3а. Добавить поля в Client

Открой `core/models.py`, найди строку с `plan_expires_at` и сразу после неё вставь
содержимое файла `core/models/client_fields.py`.

### 3б. Добавить модель YooKassaPayment

В конец `core/models.py`, перед строкой `Client.add_to_class(...)`,
вставь содержимое файла `core/models/yookassa_payment.py`.

---

## Шаг 4 — Миграция

```bash
python manage.py makemigrations
python manage.py migrate
```

Ожидаемый вывод makemigrations:
```
Migrations for 'core':
  core/migrations/XXXX_yookassa_oauth_fields.py
    - Add field uuid to client
    - Add field yookassa_connected to client
    - Add field yookassa_oauth_token to client
    - Add field yookassa_return_url to client
    - Add field yookassa_secret_key to client
    - Add field yookassa_shop_id to client
    - Create model YooKassaPayment
```

---

## Шаг 5 — Обновить urls.py (api/urls.py)

В импорты добавить:
```python
from .views_payments import (
    YooKassaOAuthRedirectView,
    YooKassaOAuthCallbackView,
    YooKassaOAuthDisconnectView,
    YooKassaSaveCredentialsView,
)
```

В urlpatterns добавить рядом с существующими payments-путями:
```python
# Мульти-мерчант вебхук с client_uuid
path('payments/webhook/<uuid:client_uuid>/', YooKassaWebhookView.as_view(), name='yookassa-webhook-client'),

# OAuth-флоу
path('payments/yookassa/connect/',      YooKassaOAuthRedirectView.as_view(),    name='yookassa-oauth-connect'),
path('payments/yookassa/callback/',     YooKassaOAuthCallbackView.as_view(),    name='yookassa-oauth-callback'),
path('payments/yookassa/disconnect/',   YooKassaOAuthDisconnectView.as_view(),  name='yookassa-oauth-disconnect'),

# Ручные ключи (альтернатива OAuth)
path('payments/yookassa/credentials/', YooKassaSaveCredentialsView.as_view(),  name='yookassa-credentials'),
```

---

## Шаг 6 — Обновить views_payments.py

Заменить `views_payments.py` на версию из пакета
(файл уже был подготовлен с полной поддержкой мульти-мерчанта).

---

## Шаг 7 — Проверить настройку

```bash
python scripts/check_oauth_setup.py
```

---

## Шаг 8 — Зарегистрировать вебхуки для существующих клиентов

Если у тебя уже есть клиенты с ключами в БД:

```bash
# Для всех клиентов сразу
python scripts/register_webhooks.py --all

# Для конкретного клиента по id
python scripts/register_webhooks.py --client-id 42
```

---

## Как это работает для клиента

1. Клиент заходит в настройки платформы → вкладка «Оплата»
2. Нажимает **«Подключить YooKassa»**
3. Фронт делает `GET /api/payments/yookassa/connect/` → получает `redirect_url`
4. Клиент редиректится на страницу YooKassa
5. Логинится в **свой** кабинет YooKassa, нажимает **«Разрешить»**
6. YooKassa редиректит на `https://yourapp.com/api/payments/yookassa/callback/?code=...&state=<client_uuid>`
7. Бэкенд автоматически:
   - обменивает code → OAuth-токен
   - сохраняет токен в `client.yookassa_oauth_token`
   - регистрирует вебхуки для этого клиента
8. Клиент видит статус «Подключено ✓»

---

## Приоритет ключей при создании платежа

```
OAuth-токен клиента           ← наивысший приоритет (bearer auth)
       ↓ нет
shop_id + secret_key клиента  ← ручные ключи (basic auth)
       ↓ нет
Глобальные ключи из .env      ← fallback (старое поведение)
```

---

## Частые вопросы

**Q: Нужно ли менять что-то в существующих платежах?**
Нет. Старые платежи продолжают работать через глобальные ключи.

**Q: Что видит клиент на странице YooKassa при авторизации?**
Название и описание приложения, которые ты указал при регистрации OAuth-приложения.

**Q: Как долго живёт OAuth-токен?**
5 лет. После истечения клиент должен переподключиться.

**Q: Можно ли отозвать токен?**
Да — через `POST /api/payments/yookassa/disconnect/` или вручную в кабинете YooKassa.

**Q: Что если клиент не хочет OAuth и хочет ввести ключи вручную?**
Используй эндпоинт `POST /api/payments/yookassa/credentials/` с `{shop_id, secret_key}`.
Он проверит ключи через YooKassa API и зарегистрирует вебхуки автоматически.
