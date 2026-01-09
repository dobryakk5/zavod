# Best Practices

В этом документе описаны best practices для разработки, деплоя и поддержки системы Zavod.

## Содержание

- [Разработка](#разработка)
- [Безопасность](#безопасность)
- [Производительность](#производительность)
- [Мониторинг](#мониторинг)
- [Тестирование](#тестирование)
- [CI/CD](#cicd)
- [Multi-tenant](#multi-tenant)

## Разработка

### Код

#### Django Backend

```python
# ❌ Плохо
def get_posts(request):
    posts = Post.objects.all()
    return JsonResponse({'posts': list(posts.values())})

# ✅ Хорошо
class PostViewSet(ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [IsTenantMember]
    
    def get_queryset(self):
        tenant = self.request.tenant
        return Post.objects.filter(client=tenant).select_related('client')
    
    @action(detail=False, methods=['get'])
    def approved(self, request):
        queryset = self.get_queryset().filter(status='approved')
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)
```

#### Next.js Frontend

```typescript
// ❌ Плохо
const PostsPage = () => {
  const [posts, setPosts] = useState([]);
  
  useEffect(() => {
    fetch('/api/posts').then(res => res.json()).then(data => setPosts(data));
  }, []);
  
  return <div>{/* рендеринг */}</div>;
};

// ✅ Хорошо
const PostsPage = () => {
  const { data: posts, isLoading, error } = usePosts();
  
  if (isLoading) return <LoadingSpinner />;
  if (error) return <ErrorBoundary error={error} />;
  
  return (
    <DataTable columns={columns} data={posts} />
  );
};
```

### Git

#### Commit messages

```
# ❌ Плохо
- fix bug
- update
- wip

# ✅ Хорошо
- feat(api): add post generation endpoint
- fix(frontend): resolve CORS issue in auth
- refactor(core): optimize tenant middleware
- docs: update API documentation
- test(backend): add unit tests for post model
```

#### Branch naming

```
# Формат: type/feature-name
feat/post-generation
fix/cors-issue
docs/api-update
test/unit-tests
hotfix/security-patch
```

### Pull Requests

- **Описание**: Четкое описание изменений
- **Тестирование**: Указание, как тестировать изменения
- **Размер**: Небольшие PR (до 400 строк изменений)
- **Ревью**: Минимум 1 ревьювер

## Безопасность

### Backend

#### Environment Variables

```python
# ❌ Плохо
SECRET_KEY = 'hardcoded-secret-key'

# ✅ Хорошо
SECRET_KEY = os.environ.get('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY environment variable must be set")
```

#### SQL Injection

```python
# ❌ Плохо
def get_posts(request):
    query = f"SELECT * FROM posts WHERE client_id = {client_id}"
    cursor.execute(query)

# ✅ Хорошо
def get_posts(request):
    posts = Post.objects.filter(client_id=client_id)
    # или
    cursor.execute("SELECT * FROM posts WHERE client_id = %s", [client_id])
```

#### XSS Protection

```python
# В Django templates автоматическая экранирование
{{ post.title }}  # экранируется автоматически
{{ post.title|safe }}  # только если доверяете контенту

# В API сериализаторах
class PostSerializer(serializers.ModelSerializer):
    class Meta:
        model = Post
        fields = ['id', 'title', 'text']
    
    def validate_text(self, value):
        # Очистка HTML
        import bleach
        return bleach.clean(value, tags=[], strip=True)
```

#### CSRF Protection

```python
# settings.py
CSRF_COOKIE_SECURE = True  # Только HTTPS
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'

# В API views
from django.views.decorators.csrf import csrf_exempt
# Используйте только для API endpoints с токенами
```

### Frontend

#### XSS Protection

```typescript
// ❌ Плохо
<div dangerouslySetInnerHTML={{__html: post.text}} />

// ✅ Хорошо
<div>{post.text}</div>

// Или с безопасным HTML
import DOMPurify from 'dompurify';

const SafeHTML = ({ html }: { html: string }) => (
  <div dangerouslySetInnerHTML={{ 
    __html: DOMPurify.sanitize(html) 
  }} />
);
```

#### Token Storage

```typescript
// ❌ Плохо
localStorage.setItem('token', token);

// ✅ Хорошо
// Используйте httpOnly cookies через backend
// Или secure storage с шифрованием
import SecureStorage from 'secure-web-storage';
const secureStorage = new SecureStorage(localStorage, {
  hash: 'sha256',
  secret: 'your-secret-key'
});
```

### Docker

```dockerfile
# ❌ Плохо
FROM python:3.11
RUN pip install app/
CMD ["python", "app.py"]

# ✅ Хорошо
FROM python:3.11-slim
RUN groupadd -r appuser && useradd -r -g appuser appuser
COPY --from=builder --chown=appuser:appuser /app /app
USER appuser
HEALTHCHECK CMD curl -f http://localhost:8000/health || exit 1
```

## Производительность

### Database

#### Query Optimization

```python
# ❌ Плохо - N+1 problem
posts = Post.objects.all()
for post in posts:
    print(post.client.name)  # Каждый раз запрос в БД

# ✅ Хорошо - select_related
posts = Post.objects.select_related('client').all()
for post in posts:
    print(post.client.name)  # Нет дополнительных запросов

# ✅ Хорошо - prefetch_related для many-to-many
posts = Post.objects.prefetch_related('tags').all()
```

#### Indexes

```python
class Post(models.Model):
    title = models.CharField(max_length=255)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    status = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            # Частые фильтры
            models.Index(fields=['client', 'status']),
            models.Index(fields=['-created_at']),  # Сортировка по дате
            
            # Поиск
            models.Index(fields=['title'], name='post_title_idx'),
            
            # Composite indexes
            models.Index(
                fields=['client', 'status', '-created_at'],
                name='post_client_status_date_idx'
            ),
        ]
```

#### Pagination

```python
# ❌ Плохо
posts = Post.objects.all()
return JsonResponse({'posts': list(posts.values())})

# ✅ Хорошо
from django.core.paginator import Paginator

def get_posts(request):
    posts = Post.objects.all()
    paginator = Paginator(posts, 20)  # 20 постов на страницу
    page = paginator.get_page(request.GET.get('page', 1))
    
    return JsonResponse({
        'posts': list(page.object_list.values()),
        'pagination': {
            'page': page.number,
            'pages': paginator.num_pages,
            'has_next': page.has_next(),
            'has_prev': page.has_previous()
        }
    })
```

### Caching

```python
# Redis cache
from django.core.cache import cache
from django.views.decorators.cache import cache_page

# Кэширование view
@cache_page(60 * 15)  # 15 минут
def get_posts(request):
    # ...

# Кэширование данных
def get_expensive_data():
    cache_key = 'expensive_data'
    data = cache.get(cache_key)
    if data is None:
        data = calculate_expensive_data()
        cache.set(cache_key, data, 3600)  # 1 час
    return data

# Кэширование шаблонов
{% load cache %}
{% cache 500 sidebar %}
    <!-- expensive sidebar -->
{% endcache %}
```

### Celery Optimization

```python
# settings.py
CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000  # 200MB
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Оптимизация задач
@shared_task(bind=True, max_retries=3)
def process_large_task(self, data):
    try:
        # Обработка порциями
        for chunk in chunked(data, 100):
            process_chunk(chunk)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

### Frontend Optimization

```typescript
// ❌ Плохо - частые ререндеры
const PostsList = () => {
  const [posts, setPosts] = useState([]);
  
  useEffect(() => {
    fetchPosts().then(setPosts);
  }, []); // Пустой массив зависимостей
  
  return (
    <div>
      {posts.map(post => (
        <PostItem key={post.id} post={post} />
      ))}
    </div>
  );
};

// ✅ Хорошо - React Query + memoization
const PostsList = () => {
  const { data: posts } = usePosts();
  
  const memoizedPosts = useMemo(() => posts, [posts]);
  
  return (
    <div>
      {memoizedPosts?.map(post => (
        <PostItem key={post.id} post={post} />
      ))}
    </div>
  );
};

// Virtualization для длинных списков
import { FixedSizeList as List } from 'react-window';

const VirtualizedPosts = ({ posts }) => (
  <List
    height={600}
    itemCount={posts.length}
    itemSize={80}
    itemData={posts}
  >
    {({ index, style, data }) => (
      <div style={style}>
        <PostItem post={data[index]} />
      </div>
    )}
  </List>
);
```

## Мониторинг

### Logging

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        }
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/app/logs/django.log',
            'formatter': 'json',
        },
        'celery': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/app/logs/celery.log',
            'formatter': 'json',
        },
    },
    'root': {
        'handlers': ['file'],
    },
    'loggers': {
        'celery': {
            'handlers': ['celery'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# В коде
import logging
logger = logging.getLogger(__name__)

def process_post(post_id):
    logger.info(f"Processing post {post_id}")
    try:
        # обработка
        logger.info(f"Post {post_id} processed successfully")
    except Exception as e:
        logger.error(f"Error processing post {post_id}: {e}")
        raise
```

### Metrics

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge
import time

# Метрики
REQUEST_COUNT = Counter('django_http_requests_total', 'Total HTTP requests')
REQUEST_DURATION = Histogram('django_http_request_duration_seconds', 'HTTP request duration')
ACTIVE_TASKS = Gauge('celery_active_tasks', 'Number of active Celery tasks')

# Middleware для метрик
class MetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        
        response = self.get_response(request)
        
        duration = time.time() - start_time
        REQUEST_COUNT.inc()
        REQUEST_DURATION.observe(duration)
        
        return response

# Celery metrics
@app.task(bind=True)
def my_task(self):
    ACTIVE_TASKS.inc()
    try:
        # выполнение задачи
        pass
    finally:
        ACTIVE_TASKS.dec()
```

### Health Checks

```python
# Health check endpoint
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db import connection
from redis import Redis

@require_GET
def health_check(request):
    """Health check endpoint for monitoring"""
    try:
        # Проверка базы данных
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "ok"
    except Exception:
        db_status = "error"
    
    try:
        # Проверка Redis
        redis = Redis(host='redis', port=6379, db=0)
        redis.ping()
        redis_status = "ok"
    except Exception:
        redis_status = "error"
    
    status = "ok" if db_status == "ok" and redis_status == "ok" else "error"
    
    return JsonResponse({
        "status": status,
        "database": db_status,
        "redis": redis_status,
        "version": "1.0.0"
    })

# Readiness probe
@require_GET
def readiness_check(request):
    """Readiness check - сервис готов принимать трафик"""
    return JsonResponse({"status": "ready"})

# Liveness probe
@require_GET
def liveness_check(request):
    """Liveness check - сервис жив"""
    return JsonResponse({"status": "alive"})
```

## Тестирование

### Unit Tests

```python
# core/tests/test_models.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Client, Post, Topic

User = get_user_model()

class ClientModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client = Client.objects.create(
            name='Test Client',
            slug='test-client'
        )

    def test_client_creation(self):
        self.assertEqual(self.client.name, 'Test Client')
        self.assertEqual(self.client.slug, 'test-client')
        self.assertTrue(self.client.created_at)

    def test_client_slug_uniqueness(self):
        with self.assertRaises(Exception):
            Client.objects.create(
                name='Duplicate Client',
                slug='test-client'
            )

class PostModelTest(TestCase):
    def setUp(self):
        self.client = Client.objects.create(
            name='Test Client',
            slug='test-client'
        )

    def test_post_creation(self):
        post = Post.objects.create(
            client=self.client,
            title='Test Post',
            text='Test content',
            status='draft'
        )
        self.assertEqual(post.title, 'Test Post')
        self.assertEqual(post.status, 'draft')
        self.assertEqual(post.client, self.client)

    def test_post_tenant_isolation(self):
        """Проверка изоляции постов между клиентами"""
        client1 = Client.objects.create(name='Client 1', slug='client-1')
        client2 = Client.objects.create(name='Client 2', slug='client-2')
        
        Post.objects.create(client=client1, title='Post 1', text='Text', status='draft')
        Post.objects.create(client=client2, title='Post 2', text='Text', status='draft')
        
        posts_client1 = Post.objects.filter(client=client1)
        posts_client2 = Post.objects.filter(client=client2)
        
        self.assertEqual(posts_client1.count(), 1)
        self.assertEqual(posts_client2.count(), 1)
        self.assertNotEqual(posts_client1.first().title, posts_client2.first().title)
```

### API Tests

```python
# api/tests/test_views.py
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from core.models import Client, Post

User = get_user_model()

class PostAPITest(TestCase):
    def setUp(self):
        self.client_api = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.client_db = Client.objects.create(
            name='Test Client',
            slug='test-client'
        )
        
        # Добавляем пользователя к клиенту
        from core.models import UserTenantRole
        UserTenantRole.objects.create(
            user=self.user,
            client=self.client_db,
            role='owner'
        )

    def test_unauthorized_access(self):
        """Тест доступа без аутентификации"""
        url = reverse('api:posts-list')
        response = self.client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authorized_access(self):
        """Тест доступа с аутентификацией"""
        self.client_api.force_authenticate(user=self.user)
        url = reverse('api:posts-list')
        response = self.client_api.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_tenant_isolation(self):
        """Тест изоляции данных между клиентами"""
        self.client_api.force_authenticate(user=self.user)
        
        # Создаем посты для разных клиентов
        Post.objects.create(
            client=self.client_db,
            title='Client 1 Post',
            text='Text',
            status='draft'
        )
        
        client2 = Client.objects.create(name='Client 2', slug='client-2')
        Post.objects.create(
            client=client2,
            title='Client 2 Post',
            text='Text',
            status='draft'
        )
        
        url = reverse('api:posts-list')
        response = self.client_api.get(url)
        
        # Пользователь должен видеть только посты своего клиента
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Client 1 Post')
```

### Frontend Tests

```typescript
// __tests__/components/PostList.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PostsList } from '@/components/posts/PostsList';
import { postsApi } from '@/lib/api';

// Mock API
jest.mock('@/lib/api');

const mockPostsApi = postsApi as jest.Mocked<typeof postsApi>;

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const renderWithProviders = (component: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
};

describe('PostsList', () => {
  beforeEach(() => {
    mockPostsApi.posts.mockResolvedValue([]);
  });

  it('renders loading state', () => {
    renderWithProviders(<PostsList />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('renders posts list', async () => {
    const mockPosts = [
      { id: 1, title: 'Test Post', status: 'draft' }
    ];
    mockPostsApi.posts.mockResolvedValue(mockPosts);
    
    renderWithProviders(<PostsList />);
    
    await waitFor(() => {
      expect(screen.getByText('Test Post')).toBeInTheDocument();
    });
  });

  it('renders error state', async () => {
    mockPostsApi.posts.mockRejectedValue(new Error('API Error'));
    
    renderWithProviders(<PostsList />);
    
    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});
```

## CI/CD

### GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI/CD Pipeline

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        cd frontend && npm install
    
    - name: Run linting
      run: |
        flake8 .
        cd frontend && npm run lint
    
    - name: Run tests
      run: |
        python manage.py test
        cd frontend && npm test
    
    - name: Build frontend
      run: cd frontend && npm run build
    
    - name: Security scan
      run: |
        pip install safety
        safety check

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Build and push Docker images
      run: |
        docker build -t zavod/backend:latest ./backend
        docker build -t zavod/frontend:latest ./frontend
        # Push to registry
    
    - name: Deploy to staging
      run: |
        # Deploy logic
        echo "Deploy to staging"
```

### Docker Best Practices

```dockerfile
# Multi-stage build
FROM python:3.11-slim as builder

# Установка зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-dev
    
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.11-slim

# Создание пользователя
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Копирование зависимостей
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копирование приложения
COPY --chown=appuser:appuser . /app
WORKDIR /app

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER appuser
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "-b", "0.0.0.0:8000"]
```

## Multi-tenant

### Data Isolation

```python
# Middleware для tenant определения
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Определяем tenant по session или query параметру
            tenant_id = self.get_tenant_id(request)
            if tenant_id:
                try:
                    tenant = Client.objects.get(id=tenant_id, users=request.user)
                    request.tenant = tenant
                except Client.DoesNotExist:
                    # Пользователь не имеет доступа к этому tenant
                    pass
        return self.get_response(request)
    
    def get_tenant_id(self, request):
        # Приоритет: session > query param > первый доступный
        if 'tenant_id' in request.session:
            return request.session['tenant_id']
        
        tenant_id = request.GET.get('tenant_id')
        if tenant_id and request.user.user_tenant_roles.filter(client_id=tenant_id).exists():
            request.session['tenant_id'] = tenant_id
            return tenant_id
        
        # Первый доступный tenant
        first_role = request.user.user_tenant_roles.first()
        if first_role:
            request.session['tenant_id'] = first_role.client_id
            return first_role.client_id
        
        return None

# Abstract model с tenant полем
class TenantModel(models.Model):
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

# Manager с автоматической фильтрацией
class TenantManager(models.Manager):
    def get_queryset(self):
        queryset = super().get_queryset()
        # Фильтрация только для tenant моделей
        if hasattr(self.model, 'client'):
            from threading import current_thread
            tenant = getattr(current_thread(), 'tenant', None)
            if tenant:
                queryset = queryset.filter(client=tenant)
        return queryset

class Post(TenantModel):
    title = models.CharField(max_length=255)
    text = models.TextField()
    status = models.CharField(max_length=50)
    
    objects = TenantManager()
    
    class Meta:
        verbose_name = "Post"
        verbose_name_plural = "Posts"
```

### Security

```python
# Permissions
from rest_framework.permissions import BasePermission

class IsTenantMember(BasePermission):
    """Проверка, что пользователь является членом tenant"""
    def has_permission(self, request, view):
        user = request.user
        tenant = getattr(request, 'tenant', None)
        
        if not tenant:
            return False
        
        return user.user_tenant_roles.filter(client=tenant).exists()

class IsTenantOwnerOrEditor(BasePermission):
    """Проверка прав owner/editor"""
    def has_permission(self, request, view):
        if not IsTenantMember().has_permission(request, view):
            return False
        
        user = request.user
        tenant = request.tenant
        
        role = user.user_tenant_roles.filter(client=tenant).first()
        if not role:
            return False
        
        return role.role in ['owner', 'editor']

# ViewSet с tenant изоляцией
class TenantViewSet(ModelViewSet):
    permission_classes = [IsTenantMember]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        tenant = getattr(self.request, 'tenant', None)
        if tenant:
            queryset = queryset.filter(client=tenant)
        return queryset
    
    def perform_create(self, serializer):
        tenant = self.request.tenant
        serializer.save(client=tenant)
```

---

**Далее:**
- [Troubleshooting](./troubleshooting.md) - Решение проблем
- [API Documentation](../02-api/overview.md) - API документация
- [Deployment](../07-deployment/docker.md) - Деплоймент
