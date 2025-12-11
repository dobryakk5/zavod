# Permissions

В этом документе описана система прав доступа и безопасности в backend части системы Zavod.

## Содержание

- [Multi-tenant архитектура](#multi-tenant-архитектура)
- [User Roles](#user-roles)
- [Permissions](#permissions)
- [Tenant Middleware](#tenant-middleware)
- [ViewSet Permissions](#viewset-permissions)
- [API Security](#api-security)
- [Testing](#testing)

## Multi-tenant архитектура

### Tenant Model

```python
# core/models.py
class Client(models.Model):
    """Клиент (tenant)"""
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
    
    def __str__(self):
        return self.name

class UserTenantRole(models.Model):
    """Роли пользователей в рамках tenant"""
    ROLE_CHOICES = [
        ('owner', 'Owner'),
        ('editor', 'Editor'),
        ('viewer', 'Viewer'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [('user', 'client')]
        verbose_name = "User Tenant Role"
        verbose_name_plural = "User Tenant Roles"
    
    def __str__(self):
        return f"{self.user.username} - {self.client.name} - {self.role}"
```

### Abstract Tenant Model

```python
# core/models.py
class TenantModel(models.Model):
    """Абстрактная модель с tenant полем"""
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        verbose_name="Клиент"
    )
    
    class Meta:
        abstract = True
    
    def clean(self):
        # Проверка, что объект принадлежит клиенту
        if not self.client_id:
            raise ValidationError("Объект должен принадлежать клиенту")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

class TenantManager(models.Manager):
    """Manager с автоматической фильтрацией по tenant"""
    def get_queryset(self):
        queryset = super().get_queryset()
        # Фильтрация только для tenant моделей
        if hasattr(self.model, 'client'):
            from threading import current_thread
            tenant = getattr(current_thread(), 'tenant', None)
            if tenant:
                queryset = queryset.filter(client=tenant)
        return queryset

# Пример использования
class Post(TenantModel):
    title = models.CharField(max_length=255)
    text = models.TextField()
    status = models.CharField(max_length=50)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
```

## User Roles

### Role Constants

```python
# core/constants.py
USER_ROLES = {
    'OWNER': 'owner',
    'EDITOR': 'editor',
    'VIEWER': 'viewer',
}

USER_ROLE_CHOICES = [
    (USER_ROLES['OWNER'], 'Owner'),
    (USER_ROLES['EDITOR'], 'Editor'),
    (USER_ROLES['VIEWER'], 'Viewer'),
]

# Права для каждой роли
ROLE_PERMISSIONS = {
    USER_ROLES['OWNER']: [
        'view', 'add', 'change', 'delete',  # Все права
        'publish', 'schedule', 'manage_users'
    ],
    USER_ROLES['EDITOR']: [
        'view', 'add', 'change',  # Права на просмотр, создание, редактирование
        'publish', 'schedule'
    ],
    USER_ROLES['VIEWER']: [
        'view'  # Только просмотр
    ],
}
```

### User Model Extension

```python
# core/models.py
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError

class User(AbstractUser):
    """Расширенная модель пользователя"""
    telegram_id = models.CharField(max_length=50, blank=True, null=True)
    photo_url = models.URLField(blank=True, null=True)
    is_dev = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
    
    def get_client_role(self, client):
        """Получение роли пользователя в клиенте"""
        role_obj = UserTenantRole.objects.filter(user=self, client=client).first()
        return role_obj.role if role_obj else None
    
    def has_client_permission(self, client, permission):
        """Проверка права пользователя в клиенте"""
        role = self.get_client_role(client)
        if not role:
            return False
        
        return permission in ROLE_PERMISSIONS.get(role, [])
    
    def has_client_role(self, client, roles):
        """Проверка роли пользователя"""
        if isinstance(roles, str):
            roles = [roles]
        
        role = self.get_client_role(client)
        return role in roles
    
    def get_client_roles(self):
        """Получение всех ролей пользователя"""
        return UserTenantRole.objects.filter(user=self).select_related('client')
    
    def is_client_owner(self, client):
        """Проверка, является ли пользователь owner"""
        return self.has_client_role(client, 'owner')
    
    def is_client_editor(self, client):
        """Проверка, является ли пользователь editor или owner"""
        return self.has_client_role(client, ['editor', 'owner'])
    
    def is_client_viewer(self, client):
        """Проверка, является ли пользователь viewer, editor или owner"""
        return self.has_client_role(client, ['viewer', 'editor', 'owner'])
```

## Permissions

### Base Permissions

```python
# core/permissions.py
from rest_framework.permissions import BasePermission
from django.contrib.auth import get_user_model

User = get_user_model()

class IsTenantMember(BasePermission):
    """Доступ для всех участников клиента (owner, editor, viewer)"""
    
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        
        # Dev пользователи имеют доступ ко всему
        if user.is_dev:
            return True
        
        # Проверка, что пользователь является участником клиента
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        return user.is_client_viewer(tenant)
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Dev пользователи имеют доступ ко всему
        if user.is_dev:
            return True
        
        # Проверка принадлежности объекта клиенту пользователя
        tenant = getattr(request, 'tenant', None)
        if not tenant:
            return False
        
        # Для tenant моделей проверяем client
        if hasattr(obj, 'client'):
            return obj.client == tenant
        
        # Для моделей, связанных с tenant через related field
        if hasattr(obj, 'post') and hasattr(obj.post, 'client'):
            return obj.post.client == tenant
        
        return False

class IsTenantOwnerOrEditor(BasePermission):
    """Доступ только для owner и editor"""
    
    def has_permission(self, request, view):
        if not IsTenantMember().has_permission(request, view):
            return False
        
        user = request.user
        tenant = getattr(request, 'tenant', None)
        
        if user.is_dev:
            return True
        
        if not tenant:
            return False
        
        return user.is_client_editor(tenant)
    
    def has_object_permission(self, request, view, obj):
        if not IsTenantOwnerOrEditor().has_object_permission(request, view, obj):
            return False
        
        # Object-level permission уже проверена в IsTenantMember
        return True

class IsTenantOwner(BasePermission):
    """Доступ только для owner"""
    
    def has_permission(self, request, view):
        if not IsTenantMember().has_permission(request, view):
            return False
        
        user = request.user
        tenant = getattr(request, 'tenant', None)
        
        if user.is_dev:
            return True
        
        if not tenant:
            return False
        
        return user.is_client_owner(tenant)
    
    def has_object_permission(self, request, view, obj):
        if not IsTenantOwner().has_object_permission(request, view, obj):
            return False
        
        return True

class CanGenerateVideo(BasePermission):
    """Генерация видео только в DEBUG=True или для client.slug='zavod'"""
    
    def has_permission(self, request, view):
        from django.conf import settings
        
        # Dev пользователи могут генерировать видео
        if request.user.is_dev:
            return True
        
        # Проверка DEBUG режима
        if settings.DEBUG:
            return True
        
        # Проверка специального клиента
        tenant = getattr(request, 'tenant', None)
        if tenant and tenant.slug == 'zavod':
            return True
        
        return False
```

### Custom Permissions

```python
# core/permissions.py (продолжение)
class CanPublishPost(BasePermission):
    """Право на публикацию постов"""
    
    def has_permission(self, request, view):
        if not IsTenantOwnerOrEditor().has_permission(request, view):
            return False
        
        user = request.user
        tenant = getattr(request, 'tenant', None)
        
        if user.is_dev:
            return True
        
        if not tenant:
            return False
        
        # Editor и Owner могут публиковать
        return user.has_client_permission(tenant, 'publish')

class CanSchedulePost(BasePermission):
    """Право на планирование постов"""
    
    def has_permission(self, request, view):
        if not IsTenantOwnerOrEditor().has_permission(request, view):
            return False
        
        user = request.user
        tenant = getattr(request, 'tenant', None)
        
        if user.is_dev:
            return True
        
        if not tenant:
            return False
        
        return user.has_client_permission(tenant, 'schedule')

class CanManageUsers(BasePermission):
    """Право на управление пользователями"""
    
    def has_permission(self, request, view):
        if not IsTenantOwner().has_permission(request, view):
            return False
        
        user = request.user
        tenant = getattr(request, 'tenant', None)
        
        if user.is_dev:
            return True
        
        if not tenant:
            return False
        
        return user.has_client_permission(tenant, 'manage_users')
```

## Tenant Middleware

### Tenant Determination

```python
# core/middleware.py
from django.utils.deprecation import MiddlewareMixin
from .models import Client, UserTenantRole
from threading import current_thread

class TenantMiddleware(MiddlewareMixin):
    """Middleware для определения tenant"""
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Определяем tenant по session или query параметру
            tenant = self.get_tenant_for_user(request.user, request)
            if tenant:
                request.tenant = tenant
                # Сохраняем tenant в поток для TenantManager
                current_thread().tenant = tenant
    
    def get_tenant_for_user(self, user, request):
        """Определение tenant для пользователя"""
        
        # 1. Проверка session
        tenant_id = request.session.get('tenant_id')
        if tenant_id:
            try:
                tenant = Client.objects.get(id=tenant_id, users=user)
                return tenant
            except Client.DoesNotExist:
                # Пользователь не имеет доступа к этому tenant
                request.session.pop('tenant_id', None)
        
        # 2. Проверка query параметра
        tenant_id = request.GET.get('tenant_id')
        if tenant_id and user.user_tenant_roles.filter(client_id=tenant_id).exists():
            try:
                tenant = Client.objects.get(id=tenant_id, users=user)
                request.session['tenant_id'] = tenant_id
                return tenant
            except Client.DoesNotExist:
                pass
        
        # 3. Первый доступный tenant
        first_role = user.user_tenant_roles.first()
        if first_role:
            request.session['tenant_id'] = first_role.client_id
            return first_role.client
        
        return None

class TenantSessionMiddleware(MiddlewareMixin):
    """Middleware для управления tenant в session"""
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Автоматическая установка tenant при первом входе
            if not request.session.get('tenant_id'):
                first_role = request.user.user_tenant_roles.first()
                if first_role:
                    request.session['tenant_id'] = first_role.client_id
    
    def process_response(self, request, response):
        # Очистка tenant из session при выходе
        if hasattr(request, 'user') and not request.user.is_authenticated:
            request.session.pop('tenant_id', None)
        return response
```

### Tenant Utils

```python
# core/utils.py
from django.core.exceptions import PermissionDenied
from .models import Client, UserTenantRole

def get_active_client(user):
    """Получение активного клиента для пользователя"""
    if user.is_dev:
        return Client.objects.first()
    
    first_role = user.user_tenant_roles.first()
    return first_role.client if first_role else None

def check_tenant_permission(user, client, permission):
    """Проверка права пользователя в клиенте"""
    if user.is_dev:
        return True
    
    if not client:
        return False
    
    return user.has_client_permission(client, permission)

def require_tenant_permission(permission):
    """Декоратор для проверки прав tenant"""
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            tenant = getattr(request, 'tenant', None)
            if not tenant:
                raise PermissionDenied("No active tenant")
            
            if not check_tenant_permission(request.user, tenant, permission):
                raise PermissionDenied(f"Permission '{permission}' required")
            
            return view_func(request, *args, **kwargs)
        
        return _wrapped_view
    return decorator
```

## ViewSet Permissions

### Base ViewSet

```python
# api/views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from core.permissions import IsTenantMember
from core.utils import get_active_client

class TenantViewSet(viewsets.ModelViewSet):
    """Базовый ViewSet для tenant моделей"""
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = getattr(self.request, 'tenant', None)
        
        if tenant:
            # Фильтрация по tenant
            if hasattr(self.get_serializer_class().Meta.model, 'client'):
                queryset = queryset.filter(client=tenant)
            elif hasattr(self.get_serializer_class().Meta.model, 'post'):
                # Для моделей, связанных с Post
                queryset = queryset.filter(post__client=tenant)
        
        return queryset
    
    def perform_create(self, serializer):
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            serializer.save(client=tenant)
        else:
            serializer.save()
    
    def list(self, request, *args, **kwargs):
        # Дополнительная проверка на случай, если tenant не установлен
        if not hasattr(request, 'tenant'):
            return Response(
                {'error': 'No active tenant'},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().list(request, *args, **kwargs)
```

### Specific ViewSets

```python
# api/views.py (продолжение)
from core.permissions import (
    IsTenantOwnerOrEditor,
    IsTenantOwner,
    CanGenerateVideo,
    CanPublishPost,
    CanSchedulePost
)

class PostViewSet(TenantViewSet):
    """ViewSet для постов"""
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PostDetailSerializer
        return PostSerializer
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsTenantOwnerOrEditor, CanGenerateVideo])
    def generate_video(self, request, pk=None):
        """Генерация видео для поста"""
        post = self.get_object()
        # Логика генерации видео
        return Response({'status': 'video generation started'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsTenantOwnerOrEditor, CanPublishPost])
    def quick_publish(self, request, pk=None):
        """Быстрая публикация поста"""
        post = self.get_object()
        # Логика публикации
        return Response({'status': 'post published'})

class TopicViewSet(TenantViewSet):
    """ViewSet для тем"""
    serializer_class = TopicSerializer
    permission_classes = [IsAuthenticated, IsTenantOwnerOrEditor]
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsTenantOwnerOrEditor])
    def discover_content(self, request, pk=None):
        """Поиск контента для темы"""
        topic = self.get_object()
        # Логика поиска контента
        return Response({'status': 'content discovery started'})

class ClientSettingsView(APIView):
    """Настройки клиента"""
    permission_classes = [IsAuthenticated, IsTenantMember]
    
    def get(self, request):
        tenant = request.tenant
        settings = ClientSettings.objects.get(client=tenant)
        serializer = ClientSettingsSerializer(settings)
        return Response(serializer.data)
    
    def patch(self, request):
        tenant = request.tenant
        settings = ClientSettings.objects.get(client=tenant)
        serializer = ClientSettingsSerializer(settings, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=400)
```

## API Security

### Authentication

```python
# config/settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}

# JWT Settings
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': False,
    
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'JWK_URL': None,
    'LEEWAY': 0,
    
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
    
    'JTI_CLAIM': 'jti',
    
    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=60),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}
```

### Security Headers

```python
# config/settings.py
# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_SECONDS = 31536000
SECURE_REDIRECT_EXEMPT = []
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_SSL_REDIRECT = False  # Включить в production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# CORS settings
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

CORS_ALLOW_CREDENTIALS = True

# CSRF settings
CSRF_COOKIE_SECURE = True  # Только HTTPS
CSRF_COOKIE_HTTPONLY = False  # Должен быть доступен для фронтенда
CSRF_COOKIE_SAMESITE = 'Strict'
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
```

### Rate Limiting

```python
# api/throttling.py
from rest_framework.throttling import UserRateThrottle

class PostCreateThrottle(UserRateThrottle):
    """Ограничение создания постов"""
    scope = 'post_create'

class ImageGenerateThrottle(UserRateThrottle):
    """Ограничение генерации изображений"""
    scope = 'image_generate'

class VideoGenerateThrottle(UserRateThrottle):
    """Ограничение генерации видео"""
    scope = 'video_generate'

# config/settings.py
REST_FRAMEWORK = {
    # ... другие настройки ...
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'api.throttling.PostCreateThrottle',
        'api.throttling.ImageGenerateThrottle',
        'api.throttling.VideoGenerateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'post_create': '10/hour',
        'image_generate': '50/hour',
        'video_generate': '5/hour',
    }
}
```

## Testing

### Unit Tests

```python
# core/tests/test_permissions.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView
from core.models import Client, UserTenantRole
from core.permissions import IsTenantMember, IsTenantOwnerOrEditor
from core.middleware import TenantMiddleware

User = get_user_model()

class PermissionsTest(TestCase):
    def setUp(self):
        self.client1 = Client.objects.create(name='Client 1', slug='client-1')
        self.client2 = Client.objects.create(name='Client 2', slug='client-2')
        
        self.user1 = User.objects.create_user(
            username='user1',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='testpass123'
        )
        self.dev_user = User.objects.create_user(
            username='dev',
            password='testpass123',
            is_dev=True
        )
        
        # Назначаем роли
        UserTenantRole.objects.create(
            user=self.user1,
            client=self.client1,
            role='owner'
        )
        UserTenantRole.objects.create(
            user=self.user2,
            client=self.client1,
            role='viewer'
        )
    
    def test_is_tenant_member_permission(self):
        """Тест разрешения для участников tenant"""
        permission = IsTenantMember()
        factory = APIRequestFactory()
        
        # User1 является участником client1
        request = factory.get('/')
        request.user = self.user1
        
        # Устанавливаем tenant
        middleware = TenantMiddleware()
        middleware.process_request(request)
        
        self.assertTrue(permission.has_permission(request, None))
        
        # User2 не является участником client2
        request.user = self.user2
        request.session['tenant_id'] = self.client2.id
        middleware.process_request(request)
        
        self.assertFalse(permission.has_permission(request, None))
        
        # Dev пользователь имеет доступ ко всему
        request.user = self.dev_user
        middleware.process_request(request)
        
        self.assertTrue(permission.has_permission(request, None))
    
    def test_is_tenant_owner_or_editor_permission(self):
        """Тест разрешения для owner и editor"""
        permission = IsTenantOwnerOrEditor()
        factory = APIRequestFactory()
        
        request = factory.get('/')
        middleware = TenantMiddleware()
        
        # User1 (owner) имеет доступ
        request.user = self.user1
        middleware.process_request(request)
        
        self.assertTrue(permission.has_permission(request, None))
        
        # User2 (viewer) не имеет доступ
        request.user = self.user2
        middleware.process_request(request)
        
        self.assertFalse(permission.has_permission(request, None))
    
    def test_object_level_permissions(self):
        """Тест object-level permissions"""
        from core.models import Post
        
        permission = IsTenantMember()
        factory = APIRequestFactory()
        
        # Создаем пост для client1
        post = Post.objects.create(
            client=self.client1,
            title='Test Post',
            text='Test',
            status='draft'
        )
        
        request = factory.get('/')
        middleware = TenantMiddleware()
        
        # User1 может видеть пост client1
        request.user = self.user1
        middleware.process_request(request)
        
        self.assertTrue(permission.has_object_permission(request, None, post))
        
        # User2 не может видеть пост client1 (он viewer)
        request.user = self.user2
        middleware.process_request(request)
        
        self.assertTrue(permission.has_object_permission(request, None, post))
        
        # Dev пользователь может видеть все
        request.user = self.dev_user
        middleware.process_request(request)
        
        self.assertTrue(permission.has_object_permission(request, None, post))
```

### Integration Tests

```python
# api/tests/test_views_permissions.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from core.models import Client, UserTenantRole

User = get_user_model()

class ViewSetPermissionsTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client1 = Client.objects.create(name='Client 1', slug='client-1')
        
        self.user1 = User.objects.create_user(
            username='user1',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            password='testpass123'
        )
        
        UserTenantRole.objects.create(
            user=self.user1,
            client=self.client1,
            role='owner'
        )
        UserTenantRole.objects.create(
            user=self.user2,
            client=self.client1,
            role='viewer'
        )
    
    def test_post_creation_permissions(self):
        """Тест прав на создание постов"""
        # Viewer не может создавать посты
        self.client.force_authenticate(user=self.user2)
        response = self.client.post('/api/posts/', {
            'title': 'Test',
            'text': 'Test',
            'status': 'draft'
        })
        
        self.assertEqual(response.status_code, 403)
        
        # Owner может создавать посты
        self.client.force_authenticate(user=self.user1)
        response = self.client.post('/api/posts/', {
            'title': 'Test',
            'text': 'Test',
            'status': 'draft'
        })
        
        self.assertEqual(response.status_code, 201)
    
    def test_tenant_isolation(self):
        """Тест изоляции tenant"""
        from core.models import Post
        
        # Создаем пост для client1
        Post.objects.create(
            client=self.client1,
            title='Client1 Post',
            text='Test',
            status='draft'
        )
        
        # Viewer может видеть посты своего клиента
        self.client.force_authenticate(user=self.user2)
        response = self.client.get('/api/posts/')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Client1 Post')
```

---

**Далее:**
- [Setup](./setup.md) - Настройка backend
- [API Documentation](../02-api/overview.md) - API документация
- [Security Best Practices](../08-guides/best-practices.md) - Best practices
