# Yandex Direct API Client

Независимый клиент для работы с Yandex Direct API с полной поддержкой rate limiting, обработки ошибок и соблюдением всех ограничений API.

## Установка

Клиент использует только стандартную библиотеку Python и `requests`. Убедитесь, что установлен `requests`:

```bash
pip install requests
```

## Быстрый старт

```python
from yandex_direct_api_client import YandexDirectAPIClient

# Инициализация клиента
client = YandexDirectAPIClient(
    access_token="ваш_токен_доступа",
    login="ваш_логин",
    use_sandbox=True  # Используйте True для тестирования
)

# Получение списка кампаний
campaigns = client.get_campaigns()
print(f"Найдено кампаний: {len(campaigns)}")

# Получение полных данных по кампаниям
full_data = client.get_full_campaign_data()
```

## Основные методы

### Campaigns.get
```python
campaigns = client.get_campaigns(
    campaign_ids=[12345, 67890],  # Опционально
    states=['ON'],  # Опционально
    types=['TEXT_CAMPAIGN']  # Опционально
)
```

### AdGroups.get
```python
ad_groups = client.get_ad_groups(
    campaign_ids=[12345]
)
```

### Keywords.get
```python
keywords = client.get_keywords(
    ad_group_ids=[111, 222]
)
```

### Ads.get
```python
ads = client.get_ads(
    ad_group_ids=[111, 222]
)
```

### Bids.get
```python
bids = client.get_bids(
    keyword_ids=[1001, 1002]
)
```

### Reports.get
```python
report = client.get_report(
    report_type='ACCOUNT_PERFORMANCE_REPORT',
    date_range_type='LAST_7_DAYS',
    format='TSV'
)
```

## Обработка ошибок

```python
from yandex_direct_api_client import RateLimitError, APIRequestError

try:
    campaigns = client.get_campaigns()
except RateLimitError as e:
    print(f"Превышен лимит запросов: {e}")
    # Подождите перед следующим запросом
except APIRequestError as e:
    print(f"Ошибка API: {e}")
    # Проверьте токен и параметры
```

## Rate Limiting

Клиент автоматически контролирует частоту запросов:
- Максимум 4 запроса в секунду (лимит API: 5)
- Максимум 9,000 запросов в день (лимит API: 10,000)
- Максимум 90 запросов Reports.get в день (лимит API: 100)

Вы можете настроить rate limiter:

```python
from yandex_direct_api_client import RateLimiter, YandexDirectAPIClient

rate_limiter = RateLimiter(
    requests_per_second=3.0,  # Более консервативный лимит
    requests_per_day=8000,
    reports_per_day=80
)

client = YandexDirectAPIClient(
    access_token="ваш_токен",
    login="ваш_логин",
    rate_limiter=rate_limiter
)
```

## Получение токена доступа

Для получения OAuth токена доступа к Yandex Direct API:

1. Зарегистрируйте приложение в [Yandex OAuth](https://oauth.yandex.ru/)
2. Получите Client ID и Client Secret
3. Получите токен через OAuth flow
4. Используйте токен для инициализации клиента

Подробнее: [Документация Yandex Direct API](https://yandex.ru/dev/direct/doc/ru/)

## Документация для заявки

Для подачи заявки на полный доступ к Direct Pro используйте файл `YANDEX_DIRECT_API_DOCUMENTATION.md`, который содержит:
- Список используемых методов
- Схему и последовательность вызовов
- Частоту вызова каждого метода
- Описание обработки ошибок
- Описание учета ограничений API

## Логирование

Клиент использует стандартный модуль `logging`. Для настройки уровня логирования:

```python
import logging

logging.basicConfig(level=logging.DEBUG)  # Для детального логирования
```

## Примеры использования

См. раздел `if __name__ == "__main__"` в файле `yandex_direct_api_client.py` для примеров использования.

