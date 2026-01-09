

1. Опишу общую модель multi-tenant для твоего кейса.
2. Покажу, как это ложится на Wagtail/Django (язык один — Python).
3. Где нужны личные кабинеты — как их собрать на Next.js.
4. Как AI и постинг в соцсети привязать к конкретному заказчику.

---

## 1. Модель multi-tenant под твой сценарий

У тебя по сути **SaaS-платформа**:

* несколько заказчиков (клиентов),
* у каждого свои соцсети, свой контент, своё расписание,
* каждому нужен личный кабинет.

Базовый паттерн:

* Один общий backend (Django + Wagtail + Celery).
* Одна БД (для начала) с **явным полем tenant_id** во всех сущностях:

  * `Client` (арендатор/заказчик),
  * `SocialAccount`,
  * `Post`,
  * `Schedule`,
  * `UserTenantRole`.

Варианты “мультитенантности”:

* **Простой и рабочий для старта** – одна база, все таблицы общие, но в каждой важной таблице есть `client` (FK). Весь код всегда фильтрует по текущему клиенту.
* Более тяжёлый (потом, если вырастешь) – отдельные схемы / БД для каждого клиента (типа django-tenants). Для начала я бы не усложнял.

---

## 2. Ключевые модели (Django/Wagtail)

### 2.1. Клиенты

```python
class Client(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)  # для URL и субдоменов
    logo = models.ImageField(upload_to="client_logos/", blank=True, null=True)
    timezone = models.CharField(max_length=64, default="Europe/Helsinki")
    # billing, тарифы и т.п. можешь добавить потом
```

### 2.2. Пользователи и роли

Оставляем стандартного `User`, добавляем связь пользователь–клиент:

```python
class UserTenantRole(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20,
        choices=(
            ("owner", "Owner"),
            ("editor", "Editor"),
            ("viewer", "Viewer"),
        ),
    )

    class Meta:
        unique_together = ("user", "client")
```

* Один человек может быть **owner** в одном клиенте и, например, просто **viewer** у другого.
* В личном кабинете и в админке ты всегда работаешь в контексте `(user, client)`.

### 2.3. Соцсети клиента

```python
class SocialAccount(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    platform = models.CharField(
        max_length=20,
        choices=(
            ("instagram", "Instagram"),
            ("telegram", "Telegram"),
            ("youtube", "YouTube"),
        ),
    )
    name = models.CharField(max_length=255)  # как ты видишь этот аккаунт
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    extra = models.JSONField(default=dict, blank=True)  # id канала/страницы и прочее

    class Meta:
        unique_together = ("client", "platform", "name")
```

> Важно: **никаких общих токенов** — у каждого клиента свои соцсети и ключи.

### 2.4. Контент и расписание (multi-tenant)

```python
class Post(models.Model):  # можно сделать Wagtail Snippet или модель Page-подобную
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    text = models.TextField(blank=True)
    image = models.ForeignKey("Media", on_delete=models.SET_NULL, null=True, blank=True)
    video = models.ForeignKey("Media", on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=(
            ("draft", "Draft"),
            ("ready", "Ready"),
            ("approved", "Approved"),
            ("scheduled", "Scheduled"),
            ("published", "Published"),
        ),
        default="draft",
    )
    tags = ArrayField(models.CharField(max_length=50), blank=True, default=list)
    source_links = ArrayField(models.URLField(), blank=True, default=list)
    generated_by = models.CharField(max_length=50, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

```python
class Schedule(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="schedules")
    social_account = models.ForeignKey(SocialAccount, on_delete=models.CASCADE)
    scheduled_at = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=(
            ("pending", "Pending"),
            ("in_progress", "In progress"),
            ("published", "Published"),
            ("failed", "Failed"),
        ),
        default="pending",
    )
    external_id = models.CharField(max_length=255, blank=True)
    log = models.TextField(blank=True)
```

`Media` можно сделать либо через Wagtail `Document/Image`, либо своей моделью – тоже с `client`, если медиа должны быть изолированы.

---

## 3. Как сюда вкручивается Wagtail

* Wagtail даёт тебе:

  * готовую админку,
  * версии, поиск, превью,
  * удобный редактор текста и медиа.

**Как включить multi-tenant в Wagtail:**

1. Везде, где есть контент (`Post`, `Media`, `Schedule`), делаешь поле `client`.
2. В админке:

   * в `ModelAdmin` / `Snippet` переопределяешь `get_queryset` так, чтобы показывать только записи выбранного клиента.
   * по `request.user` определяешь, в каком клиенте он сейчас работает (либо один клиент, либо выбор активного клиента).
3. Для Wagtail можно сделать “переключатель клиента” в админке (типа dropdown: “Client A / Client B”), который сохранить в `session` и фильтровать queryset’ы по нему.

---

## 4. Личные кабинеты на Next.js

Тебе нужно, чтобы заказчики видели **только свои** посты/расписания.

Архитектура:

* **Next.js** = фронт для клиентов (личный кабинет).
* **Django/Wagtail** = API (REST или GraphQL) + админка для тебя/редакторов.

Паттерн:

1. При логине пользователь получает JWT/куку от Django с его user_id.
2. В API backend по user_id подтягиваешь список `UserTenantRole` и:

   * либо у пользователя один `client` – всё просто,
   * либо несколько – даёшь ему выбрать активный `client` в UI, передавать `client_id` в запросах.
3. Все API эндпоинты на backend **обязаны фильтровать по client**:

   * `GET /api/posts` → только посты с `client_id`, доступным этому user.
4. В Next.js делаешь:

   * dashboard: список постов для текущего клиента,
   * страницы редактирования / планирования,
   * календарь расписания постов.

Таким образом, **Next.js вообще не знает про других клиентов** — он всегда работает в рамках одного `client_id`.

---

## 5. AI и постинг в контексте клиента

### 5.1. Поиск и генерация (шаги 1–2)

В Celery задачах всегда прокидываешь `client_id`:

```python
@app.task
def generate_posts_for_client(client_id: int, topic: str):
    client = Client.objects.get(id=client_id)
    # 1. Ищем контент (NewsAPI, RSS, YouTube) на тему topic
    # 2. Формируем промпт для OpenAI с учётом tone-of-voice клиента (можно хранить в Client)
    # 3. Создаём Post(client=client, status='draft', ...)
```

То же самое для генерации картинок/видео: всё привязано к `client`.

### 5.2. Постинг (шаг 4)

Планировщик делает:

```python
@app.task
def process_schedules():
    now = timezone.now()
    qs = Schedule.objects.select_related('post', 'social_account', 'client').filter(
        status="pending",
        scheduled_at__lte=now,
    )
    for sch in qs:
        publish_to_platform.delay(sch.id)
```

```python
@app.task
def publish_to_platform(schedule_id: int):
    sch = Schedule.objects.select_related('post', 'social_account', 'client').get(id=schedule_id)
    client = sch.client
    account = sch.social_account
    post = sch.post

    # В зависимости от platform вызываем нужное API:
    if account.platform == "telegram":
        # отправляем через Bot API
        ...
    elif account.platform == "instagram":
        # Instagram Graph API
        ...
    elif account.platform == "youtube":
        # YouTube API
        ...

    # Обновляем sch.status, sch.external_id, sch.log
```

Так каждый `Schedule` и `Post` привязан к конкретному `client`, и никакого пересечения между заказчиками нет.

---

## 6. Payload vs Wagtail при multi-tenant

Если коротко:

* **Wagtail + Django**:

  * Один стек Python.
  * Multi-tenant = просто `client` FK + фильтрация queryset’ов.
  * AI, скрейпинг, Celery, постинг – всё рядом, нормальный монолит.
  * Личные кабинеты – Next.js + DRF/GraphQL.

* **Payload**:

  * CMS и админка классные, но multi-tenant через JS/TS, а генерация/постинг всё равно в Python.
  * Придётся везде тащить `client` и в Payload, и в Python, плюс жить с REST/GraphQL между ними.

С учётом **multi-tenant + AI + сложный backend** я бы точно шёл в **Wagtail/Django**.
