# Аутентификация API

В этом документе описана система аутентификации и авторизации API Zavod.

## Содержание

- [Типы аутентификации](#типы-аутентификации)
- [Telegram WebApp Auth](#telegram-webapp-auth)
- [JWT Token Auth](#jwt-token-auth)
- [Права доступа](#права-доступа)
- [Multi-tenant изоляция](#multi-tenant-изоляция)

## Типы аутентификации

Система поддерживает два типа аутентификации:

1. **Telegram WebApp Auth** - для frontend приложений
2. **JWT Token Auth** - для программного доступа

## Telegram WebApp Auth

### Описание

Используется для аутентификации пользователей через Telegram WebApp. Подходит для frontend приложений.

### Эндпоинты

#### Авторизация

**POST** `/api/auth/telegram`

**Тело запроса:**
```json
{
  "id": 123456789,
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe",
  "photo_url": "https://t.me/i/userpic/320/username.jpg",
  "auth_date": 1234567890,
  "hash": "calculated_hash"
}
```

**Проверка хеша:**
Хеш должен быть рассчитан по алгоритму Telegram:
1. Собрать все поля (кроме hash) в формате `key=<value>`
2. Отсортировать по алфавиту
3. Объединить через `\n`
4. Посчитать SHA256 от полученной строки с секретом

**Ответ:**
```json
{
  "user": {
    "telegramId": "123456789",
    "firstName": "John",
    "lastName": "Doe",
    "username": "johndoe",
    "photoUrl": "https://t.me/i/userpic/320/username.jpg",
    "authDate": "2024-01-01T00:00:00Z",
    "isDev": false
  }
}
```

#### Dev Mode Login

**PUT** `/api/auth/telegram`

Только в DEBUG режиме. Автоматически создает/логинит dev пользователя.

**Ответ:**
```json
{
  "user": {
    "telegramId": "1",
    "firstName": "Dev",
    "lastName": "User",
    "username": "dev_user",
    "photoUrl": null,
    "authDate": "2024-01-01T00:00:00Z",
    "isDev": true
  }
}
```

#### Logout

**DELETE** `/api/auth/telegram`

Удаляет сессию пользователя.

**Ответ:**
```json
{
  "success": true
}
```

### Frontend интеграция

```typescript
// Пример использования в Next.js
import { useMutation } from '@tanstack/react-query';

const useTelegramAuth = () => {
  return useMutation({
    mutationFn: (authData: TelegramAuthData) =>
      fetch('/api/auth/telegram', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(authData),
      }).then(res => res.json())
  });
};
```

## JWT Token Auth

### Описание

Стандартная JWT аутентификация для программного доступа к API.

### Эндпоинты

#### Получение токена

**POST** `/api/auth/token/`

**Тело запроса:**
```json
{
  "username": "user@example.com",
  "password": "password123"
}
```

**Ответ:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### Обновление токена

**POST** `/api/auth/refresh/`

**Тело запроса:**
```json
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

**Ответ:**
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

#### Logout

**POST** `/api/auth/logout/`

Удаляет refresh токен из cookies.

**Ответ:**
```json
{
  "success": true
}
```

### Использование токена

Токен передается в заголовке:

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...
```

### Пример запроса

```bash
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
     http://localhost:8000/api/posts/
```

## Права доступа

### Роли пользователей

Каждый пользователь имеет роль в рамках клиента:

- **owner** - Полный доступ
- **editor** - Создание и редактирование
- **viewer** - Только чтение

### Проверка прав

#### Backend (Django)

```python
from rest_framework.permissions import BasePermission

class IsTenantOwnerOrEditor(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        client = get_active_client(user)
        role = get_user_role(user, client)
        return role in ['owner', 'editor']

class IsTenantMember(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        client = get_active_client(user)
        return UserTenantRole.objects.filter(
            user=user, client=client
        ).exists()
```

#### Frontend

```typescript
// Хук для проверки прав
export const useRole = () => {
  const { data: clientInfo } = useClient();
  
  const role = clientInfo?.role;
  const canEdit = role === 'owner' || role === 'editor';
  const canView = role === 'owner' || role === 'editor' || role === 'viewer';
  
  return { role, canEdit, canView };
};
```

### Примеры использования

```python
# Только для owner и editor
class PostViewSet(ModelViewSet):
    permission_classes = [IsTenantOwnerOrEditor]

# Для всех авторизованных пользователей клиента
class TopicViewSet(ReadOnlyModelViewSet):
    permission_classes = [IsTenantMember]
```

## Multi-tenant изоляция

### Принципы

1. **Данные изолированы** по `client_id`
2. **Пользователи видят только свои данные**
3. **Нет пересечения между клиентами**

### Реализация

#### Middleware

```python
class TenantMiddleware:
    def __call__(self, request):
        if request.user.is_authenticated:
            # Определяем активного клиента
            client = self.get_active_client(request.user)
            request.tenant = client
        return self.get_response(request)
    
    def get_active_client(self, user):
        # Логика определения клиента
        # Например, по session или query параметру
        pass
```

#### QuerySet фильтрация

```python
class TenantManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        # Фильтрация по client_id если модель имеет client поле
        if hasattr(self.model, 'client'):
            from .middleware import get_tenant
            tenant = get_tenant()
            if tenant:
                queryset = queryset.filter(client=tenant)
        return queryset

class TenantModel(models.Model):
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    
    objects = TenantManager()
    
    class Meta:
        abstract = True
```

#### ViewSet фильтрация

```python
class TenantViewSet(ModelViewSet):
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = self.request.tenant
        if tenant:
            queryset = queryset.filter(client=tenant)
        return queryset
```

### Безопасность

- **Никогда не доверяйте client_id от клиента**
- **Всегда фильтруйте queryset по активному клиенту**
- **Проверяйте права доступа к каждому объекту**
- **Используйте HTTPS для передачи токенов**

---

**Далее:**
- [Clients](./clients.md) - Работа с клиентами
- [Posts](./posts.md) - Работа с постами
- [Permissions](../06-backend/permissions.md) - Подробнее о правах доступа
