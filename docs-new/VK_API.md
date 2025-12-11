Отлично — сделаем полностью автоматический OAuth-подключение для ВКонтакте, где админ нажимает кнопку в Next.js, проходит авторизацию VK, а бэкенд на Wagtail/Django получает и безопасно сохраняет токен сообщества (и/или user-token), проверяет, что пользователь — админ нужной группы, и дальше публикует посты с картинками через сервер. Ниже — архитектура + готовые, практические куски кода (Django/Wagtail + Next.js 15) — прямо копируй и вставляй, подставив свои значения.

Я предположу стандартный серверный OAuth flow (response_type=code), `offline` scope (чтобы токен не умирал), и хранение токена в модели `VkIntegration`. Всё происходит на сервере (без хранения client_secret в браузере).

# Архитектура (кратко)

1. Next.js: кнопка «Подключить сообщество» → открывает `/api/vk/connect` на Django (редирект на VK OAuth).
2. Пользователь авторизует приложение в VK, соглашается на права. VK редиректит на `REDIRECT_URI` (Django callback).
3. Django: принимает `code`, меняет на `access_token` через `https://oauth.vk.com/access_token`, получает `access_token`, `user_id`, `expires_in`, возможно `email`.
4. Django: проверяет, что этот `user_id` — админ нужной группы (через VK API `groups.get`/`groups.getById`), сохраняет токен и `group_id` в базу (шифруя / защищая доступ).
5. После сохранения — фронт получает успех. Постинг (с картинками) идёт через сервер: сервер использует сохранённый access_token для `photos.getWallUploadServer` → upload → `photos.saveWallPhoto` → `wall.post`.

# Модель Django (Wagtail) — models.py

```python
# app/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class VkIntegration(models.Model):
    """
    Хранит токен авторизованного админа/интеграцию сообщества.
    В проде: encrypt токен или хранить в секретном хранилище.
    """
    owner = models.ForeignKey(User, on_delete=models.CASCADE)  # кто подключил
    group_id = models.BigIntegerField()  # id группы (положительный)
    access_token = models.TextField()  # токен (шифровать в проде)
    user_id = models.BigIntegerField()   # id пользователя, который дал доступ
    expires_in = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("group_id", "owner")

    def __str__(self):
        return f"VK {self.group_id} by {self.owner}"
```

# Настройки (settings.py)

Добавьте переменные:

```py
VK_CLIENT_ID = "<VK_APP_ID>"
VK_CLIENT_SECRET = "<VK_SECURE_KEY>"
VK_REDIRECT_URI = "https://your-domain.com/vk/callback/"  # тот, что в настройках VK app
VK_API_VERSION = "5.131"
```

В проде используйте переменные окружения.

# Django: urls и views (OAuth start / callback / post)

```python
# app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("vk/connect/", views.vk_connect, name="vk_connect"),
    path("vk/callback/", views.vk_callback, name="vk_callback"),
    path("vk/post_with_photos/", views.post_with_photos, name="vk_post_with_photos"),
]
```

```python
# app/views.py
import secrets
import json
import os
import requests
from urllib.parse import urlencode
from django.shortcuts import redirect, HttpResponse, get_object_or_404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import VkIntegration

API_V = getattr(settings, "VK_API_VERSION", "5.131")

@login_required
def vk_connect(request):
    """
    Перенаправить админа на VK OAuth страницу. Сохраняем state в сессии.
    """
    state = secrets.token_urlsafe(16)
    request.session["vk_oauth_state"] = state
    scope = "wall,photos,groups,offline"
    params = {
        "client_id": settings.VK_CLIENT_ID,
        "display": "page",
        "redirect_uri": settings.VK_REDIRECT_URI,
        "scope": scope,
        "response_type": "code",
        "v": API_V,
        "state": state,
    }
    auth_url = "https://oauth.vk.com/authorize?" + urlencode(params)
    return redirect(auth_url)

@login_required
def vk_callback(request):
    """
    Обмен code -> access_token; проверка прав администратора в группе; сохранение токена.
    Предполагаем, что group_id админа будет передан фронтом/в диалоге или мы предлагаем выбрать группу далее.
    """
    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code or state != request.session.get("vk_oauth_state"):
        return HttpResponse("Invalid OAuth response", status=400)

    token_url = "https://oauth.vk.com/access_token"
    params = {
        "client_id": settings.VK_CLIENT_ID,
        "client_secret": settings.VK_CLIENT_SECRET,
        "redirect_uri": settings.VK_REDIRECT_URI,
        "code": code,
    }
    r = requests.get(token_url, params=params)
    data = r.json()
    if "error" in data:
        return HttpResponse(f"VK token exchange error: {data}", status=400)

    access_token = data.get("access_token")
    user_id = data.get("user_id")
    expires_in = data.get("expires_in")  # может быть None если offline

    # Теперь получим список сообществ, где user — админ, и предложим выбрать группу (или если в запросе был group_id — проверим)
    # В простом варианте — если приложение заранее знает target_group_id, проверяем права:
    # Пример: проверка админства для конкретной группы (если FRONT передал group_id в сессии / GET)
    group_id = request.session.get("vk_target_group") or request.GET.get("group_id")
    if not group_id:
        # Просим пользователя выбрать — можно запрашивать groups.get и отобразить список групп frontend'у.
        # Здесь я просто возвращаю список групп (json) для демонстрации.
        resp = requests.get("https://api.vk.com/method/groups.get", params={
            "user_id": user_id,
            "access_token": access_token,
            "v": API_V,
            "extended": 1
        }).json()
        return HttpResponse(json.dumps({"groups": resp}), content_type="application/json")

    # Проверка: действительно ли user_id — админ group_id
    chk = requests.get("https://api.vk.com/method/groups.getById", params={
        "group_id": group_id,
        "access_token": access_token,
        "v": API_V,
        "fields": "is_admin"
    }).json()
    # groups.getById может вернуть объект с is_admin; но иногда требуется другой метод — это пример.
    items = chk.get("response")
    is_admin = False
    if items and isinstance(items, list):
        item = items[0]
        # VK иногда возвращает 'is_admin' only for user-token; проверка может отличаться.
        is_admin = item.get("is_admin", 0) == 1

    if not is_admin:
        return HttpResponse("Вы не админ указанной группы или не подтвердили права.", status=403)

    # Сохраняем интеграцию
    inst, _ = VkIntegration.objects.update_or_create(
        owner=request.user,
        group_id=int(group_id),
        defaults={
            "access_token": access_token,
            "user_id": int(user_id),
            "expires_in": expires_in
        }
    )

    return HttpResponse("Группа успешно подключена. Закройте это окно и продолжайте в приложении.")
```

> Примечание: VK API иногда возвращает структуру по-разному для community flow vs user token. Если вы хотите, чтобы приложение само предлагало список групп для выбора — в `vk_callback` после получения `access_token` вызовите `groups.get` (`extended=1`) и верните список в фронтенд, пусть админ выберет нужную группу — затем сохраните выбранный `group_id`. Код выше показывает обе идеи.

# Endpoint для публикации поста с картинками (Django)

Делаем endpoint, который принимает multipart/form-data (`message` + `images[]`) и публикует от имени подключенной группы.

```python
# app/views.py (добавим функцию post_with_photos)
from django.views.decorators.http import require_POST
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

@csrf_exempt  # если вызываете из фронтенда, лучше использовать токен авторизации и обычный CSRF
@login_required
@require_POST
def post_with_photos(request):
    """
    Принимает form-data:
      - integration_id (id модели VkIntegration)
      - message
      - files images[] (может быть несколько)
    Публикует и возвращает result.
    """
    integration_id = request.POST.get("integration_id")
    message = request.POST.get("message", "")
    if not integration_id:
        return HttpResponse("integration_id required", status=400)
    inst = get_object_or_404(VkIntegration, id=integration_id, owner=request.user)

    token = inst.access_token
    group_id = inst.group_id

    # Сохраним файлы временно и закинем на upload_url
    attachments = []
    files = request.FILES.getlist("images")
    for f in files:
        # сохраняем временно
        path = default_storage.save(f"tmp/vk_{secrets.token_hex(8)}_{f.name}", ContentFile(f.read()))
        full_path = default_storage.path(path)

        # 1) get upload_url
        r = requests.get("https://api.vk.com/method/photos.getWallUploadServer", params={
            "access_token": token,
            "v": API_V,
            "group_id": group_id
        }).json()
        if "error" in r:
            return HttpResponse(json.dumps(r), content_type="application/json", status=400)
        upload_url = r["response"]["upload_url"]

        # 2) upload file
        with open(full_path, "rb") as imgf:
            up = requests.post(upload_url, files={"photo": imgf}).json()

        # 3) saveWallPhoto
        save = requests.post("https://api.vk.com/method/photos.saveWallPhoto", data={
            "access_token": token,
            "v": API_V,
            "group_id": group_id,
            "photo": up["photo"],
            "server": up["server"],
            "hash": up["hash"]
        }).json()
        if "error" in save:
            return HttpResponse(json.dumps(save), content_type="application/json", status=400)
        p = save["response"][0]
        attachments.append(f"photo{p['owner_id']}_{p['id']}")

        # optional: удаляем временный файл
        default_storage.delete(path)

    # 4) publish
    post = requests.post("https://api.vk.com/method/wall.post", data={
        "access_token": token,
        "v": API_V,
        "owner_id": -group_id,
        "from_group": 1,
        "message": message,
        "attachments": ",".join(attachments)
    }).json()

    return HttpResponse(json.dumps(post), content_type="application/json")
```

# Frontend (Next.js 15) — кнопка «Подключить сообщество» и форма поста

Простой вариант: при клике пользователь переходит на backend `/vk/connect/` (Django редиректит на VK). Можно открыть в popup.

`app/components/VkConnectButton.tsx`:

```tsx
"use client";
export default function VkConnectButton() {
  const start = () => {
    // откроем окно авторизации (можно в popup)
    window.location.href = "/api/proxy-to-django/vk/connect/"; 
    // или если ваш frontend и backend на одном домене — прямой переход
  };
  return <button onClick={start}>Подключить сообщество VK</button>;
}
```

Форма отправки поста (fetch на Django):

```tsx
"use client";
import { useState } from "react";

export default function VkPostForm({ integrationId }) {
  const [msg, setMsg] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);

  const submit = async (e) => {
    e.preventDefault();
    const fd = new FormData();
    fd.append("integration_id", String(integrationId));
    fd.append("message", msg);
    if (files) {
      for (const f of Array.from(files)) fd.append("images", f);
    }
    const res = await fetch("/api/proxy-to-django/vk/post_with_photos/", {
      method: "POST",
      body: fd,
      credentials: "include", // если используете сессионную авторизацию
    });
    const j = await res.json();
    console.log(j);
    alert(JSON.stringify(j));
  };

  return (
    <form onSubmit={submit}>
      <textarea value={msg} onChange={(e) => setMsg(e.target.value)} />
      <input type="file" multiple onChange={(e) => setFiles(e.target.files)} />
      <button type="submit">Опубликовать</button>
    </form>
  );
}
```

> Замечание: если frontend и backend находятся на разных доменах, сделайте proxy-роуты (`/api/proxy-to-django/*`) или настройте CORS и используйте JWT/токены для аутентификации. Для Wagtail/Django чаще удобен вариант, когда Next.js вызывает ваш API прямо (через fetch к вашему домену).

# Важные замечания по безопасности и надежности

* **HTTPS обязательно** для редиректов OAuth (VK требует HTTPS в проде).
* **Хранение токенов**: в проде шифруйте токены или используйте секретное хранилище (HashiCorp Vault, AWS Secrets Manager, KMS). Сейчас используем cryptography.Fernet

Пример:
# utils/crypto.py
from cryptography.fernet import Fernet
import os

FERNET_KEY = os.environ["FERNET_KEY"]  # храните в secret manager / env
fernet = Fernet(FERNET_KEY.encode())

def encrypt_value(plain: str) -> str:
    return fernet.encrypt(plain.encode()).decode()

def decrypt_value(token: str) -> str:
    return fernet.decrypt(token.encode()).decode()

# models.py
from django.db import models
from .utils.crypto import encrypt_value, decrypt_value

class VkIntegration(models.Model):
    owner = models.ForeignKey(...)
    group_id = models.BigIntegerField()
    _access_token = models.TextField(db_column="access_token_encrypted")

    @property
    def access_token(self):
        return decrypt_value(self._access_token)

    @access_token.setter
    def access_token(self, value):
        self._access_token = encrypt_value(value)

-------

FERNET_KEY храните в .env


* **Права**: проверяйте, что авторизованный пользователь действительно админ сообщества. Не полагайтесь только на токен — дополнительно запросите список групп (`groups.get`) и `is_admin` флаг.
* **Offline scope**: если вы запросите `offline`, токен не будет истекать; иначе надо реализовать refresh flow.
* **Разрешения сервера**: API-ключи (`client_secret`) — только на сервере.
* **Асинхронность**: загрузка больших изображений/много изображений — лучше отдать задачу на background worker (Celery) и вернуть job-id на фронт.
* **Логи и мониторинг**: логируйте ошибки VK API и сделайте повторные попытки при краткосрочных ошибках.

# Что можно добавить дальше (предложения)

* UI: дать админу список групп (полученных из `groups.get`), чтобы он выбрал, к какой группе привязать интеграцию.
* Админ-панель Wagtail: добавить модель `VkIntegration` в админку для управления.
* Поддержка нескольких интеграций (несколько групп).
