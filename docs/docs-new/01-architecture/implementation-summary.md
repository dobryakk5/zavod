# Implementation Summary

Этот документ содержит краткую сводку реализации системы Zavod.

## Содержание

- [Backend (Django REST Framework)](#backend-django-rest-framework)
- [Frontend (Next.js)](#frontend-nextjs)
- [Архитектурные решения](#архитектурные-решения)
- [Что осталось реализовать (UI)](#что-осталось-реализовать-ui)
- [Тестирование](#тестирование)

## Backend (Django REST Framework)

### 1. Permissions

```python
class IsTenantMember(BasePermission):
    """Доступ для всех участников клиента (owner, editor, viewer)"""

class IsTenantOwnerOrEditor(BasePermission):
    """Доступ только для owner и editor"""

class CanGenerateVideo(BasePermission):
    """Генерация видео только в DEBUG=True или для client.slug='zavod'"""
```

### 2. Serializers

**Реализовано для:**
- ✅ Post (PostSerializer, PostDetailSerializer)
- ✅ Topic (TopicSerializer, TopicDetailSerializer)
- ✅ TrendItem (TrendItemSerializer, TrendItemDetailSerializer)
- ✅ Story (StorySerializer, StoryDetailSerializer)
- ✅ ContentTemplate (с read_only для type, tone, length, language)
- ✅ SEOKeywordSet
- ✅ SocialAccount (tokens write-only)
- ✅ Schedule
- ✅ ClientSettings (excludes id и name)

### 3. ViewSets

**PostViewSet:**
- CRUD операции
- `POST /api/posts/{id}/generate_image/` - генерация изображения (4 модели)
- `POST /api/posts/{id}/generate_video/` - генерация видео (requires CanGenerateVideo)
- `POST /api/posts/{id}/regenerate_text/` - регенерация текста
- `POST /api/posts/{id}/quick_publish/` - быстрая публикация

**TopicViewSet:**
- CRUD операции
- `POST /api/topics/{id}/discover_content/` - поиск контента
- `POST /api/topics/{id}/generate_posts/` - генерация постов
- `POST /api/topics/{id}/generate_seo/` - запуск клиентской генерации SEO

**TrendItemViewSet:**
- Просмотр/удаление трендов
- `POST /api/trends/{id}/generate_post/` - генерация поста
- `POST /api/trends/{id}/generate_story/` - генерация истории

**StoryViewSet:**
- CRUD операции
- `POST /api/stories/{id}/generate_posts/` - генерация постов из эпизодов

**ContentTemplateViewSet:**
- CRUD операции
- Основные поля (type, tone, length, language) - readonly в serializer

**ScheduleViewSet:**
- CRUD операции
- `POST /api/schedules-manage/{id}/publish_now/` - немедленная публикация

**SocialAccountViewSet:**
- CRUD операции для соцсетей

**ClientSettingsView:**
- `GET /api/client/settings/` - получение настроек (без id и name)
- `PATCH /api/client/settings/` - обновление настроек (без id и name)

**ClientInfoView:**
- `GET /api/client/info/` - получение информации о клиенте и роли пользователя

### 4. Routing

Использован DRF Router для автоматической регистрации:
- `/api/posts/` - PostViewSet
- `/api/topics/` - TopicViewSet
- `/api/trends/` - TrendItemViewSet
- `/api/stories/` - StoryViewSet
- `/api/templates/` - ContentTemplateViewSet
- `/api/schedules-manage/` - ScheduleViewSet
- `/api/social-accounts/` - SocialAccountViewSet
- `/api/client/info/` - ClientInfoView
- `/api/client/settings/` - ClientSettingsView
- `/api/client/summary/` - ClientSummaryView

## Frontend (Next.js)

### 1. Types

Полная типизация для всех моделей:
- Post, PostDetail
- Topic, TopicDetail
- TrendItem, TrendItemDetail
- Story, StoryDetail
- ContentTemplate
- Schedule
- SocialAccount
- ClientInfo, ClientSettings, ClientSummary
- TaskResponse
- Enums: PostStatus, ScheduleStatus, StoryStatus, Platform, ContentType, Tone, Length, Language, TrendSource, UserRole

### 2. API Client

**Реализованы модули:**
- `posts.ts` - список, CRUD, генерация (image/video/text), quick publish
- `topics.ts` - CRUD, discover content, generate posts, generate SEO
- `trends.ts` - список, удаление, generate post/story
- `stories.ts` - CRUD, generate posts
- `templates.ts` - CRUD (с учетом readonly полей)
- `schedules.ts` - CRUD, publish now
- `socialAccounts.ts` - CRUD для соцсетей
- `client.ts` - info, summary, settings (get/update)
- `index.ts` - centralized exports

**Пример использования:**
```typescript
import { postsApi } from '@/lib/api';

// List posts
const posts = await postsApi.list({ status: 'draft' });

// Generate image
await postsApi.generateImage(1, 'pollinations');

// Generate video (requires permission)
await postsApi.generateVideo(1);
```

### 3. Hooks

**useClient()**
```typescript
const { data, loading, error } = useClient();
// data: { client: { id, name, slug }, role: 'owner' | 'editor' | 'viewer' }
```

**useRole()**
```typescript
const { role, loading, canEdit, canView } = useRole();
// canEdit: true if owner or editor
// canView: true if any role
```

**useCanGenerateVideo()**
```typescript
const { canGenerateVideo, loading } = useCanGenerateVideo();
// true if NEXT_PUBLIC_DEV_MODE=true OR client.slug='zavod'
```

**Пример использования в компоненте:**
```typescript
import { useCanGenerateVideo, useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';

function PostActions({ postId }: { postId: number }) {
  const { canGenerateVideo } = useCanGenerateVideo();
  const { canEdit } = useRole();

  return (
    <>
      <Button
        disabled={!canEdit}
        onClick={() => postsApi.generateImage(postId, 'pollinations')}
      >
        Generate Image
      </Button>

      <Button
        disabled={!canGenerateVideo}
        variant={canGenerateVideo ? 'default' : 'secondary'}
        onClick={() => postsApi.generateVideo(postId)}
      >
        {canGenerateVideo ? 'Generate Video' : 'Generate Video (Dev only)'}
      </Button>
    </>
  );
}
```

## Архитектурные решения

### 1. Переиспользование кода

Все ViewSets **не создают новую логику**, а вызывают существующие:
- **Celery tasks** из `core/tasks.py` (например, `generate_image_for_post.delay()`)
- **Функции** из `core/views.py` (например, логика quick_publish)

### 2. Tenant Isolation

Все ViewSets автоматически фильтруют данные по текущему клиенту:
```python
def get_queryset(self):
    client = get_active_client(self.request.user)
    return Post.objects.filter(client=client)
```

### 3. Permissions

Каждый ViewSet использует комбинацию permissions:
- **Read** - `IsTenantMember` (любая роль)
- **Create/Update/Delete** - `IsTenantOwnerOrEditor` (owner/editor)
- **Generate Video** - `CanGenerateVideo` (dev mode или zavod)

### 4. Serializer Strategy

- **List views** - легкие serializers с минимумом полей
- **Detail views** - полные serializers со всеми полями
- **Read-only fields** - для generated_by, created_at, etc.
- **Write-only fields** - для access_token, refresh_token (безопасность)

### 5. Frontend API Architecture

```
lib/
├── types.ts              # TypeScript types
├── api.ts                # Base apiFetch function
├── api/
│   ├── index.ts          # Centralized exports
│   ├── posts.ts          # Posts API functions
│   ├── topics.ts         # Topics API functions
│   └── ...
└── hooks/
    ├── index.ts          # Centralized exports
    ├── useClient.ts      # Client info hook
    ├── useRole.ts        # Role permissions hook
    └── useCanGenerateVideo.ts  # Video generation permission
```

## Что осталось реализовать (UI)

### Компоненты (shadcn/ui style)

**Posts:**
- [ ] `components/posts/post-form.tsx` - форма создания/редактирования
- [ ] `components/posts/post-detail-view.tsx` - детальный просмотр с генерацией
- [ ] `components/posts/generate-image-menu.tsx` - dropdown выбора модели
- [ ] `components/posts/generate-video-button.tsx` - кнопка с условным disabled
- [ ] `components/posts/quick-publish-dialog.tsx` - dialog выбора соцсети

**Topics:**
- [ ] `components/topics/topics-list.tsx` - список тем
- [ ] `components/topics/topic-form.tsx` - форма темы
- [ ] `components/topics/topic-actions.tsx` - кнопки discover/generate/seo
- [ ] `components/topics/trends-list.tsx` - список трендов для темы

**Trends:**
- [ ] `components/trends/trend-card.tsx` - карточка тренда
- [ ] `components/trends/generate-from-trend-menu.tsx` - dropdown: post или story

**Stories:**
- [ ] `components/stories/stories-list.tsx` - список историй
- [ ] `components/stories/story-detail.tsx` - детали + эпизоды
- [ ] `components/stories/generate-posts-button.tsx` - генерация постов

**Templates:**
- [ ] `components/templates/templates-list.tsx` - список шаблонов
- [ ] `components/templates/template-form.tsx` - форма (основные readonly)

**Settings:**
- [ ] `components/settings/client-settings-form.tsx` - форма настроек (без name)
- [ ] `components/settings/social-accounts-manager.tsx` - управление соцсетями

### Страницы

- [ ] `app/posts/new/page.tsx` - создание поста
- [ ] `app/posts/[id]/page.tsx` - просмотр/редактирование поста
- [ ] `app/topics/page.tsx` - список тем
- [ ] `app/topics/[id]/page.tsx` - детали темы + тренды
- [ ] `app/stories/page.tsx` - список историй
- [ ] `app/stories/[id]/page.tsx` - детали истории
- [ ] `app/templates/page.tsx` - список шаблонов
- [ ] `app/templates/[id]/page.tsx` - редактирование шаблона
- [ ] `app/settings/page.tsx` - настройки клиента + соцсети

## Тестирование

### Backend

```bash
cd backend
python manage.py check  # ✅ System check identified no issues (0 silenced).
```

### API Endpoints

Все endpoints доступны и протестированы через Django REST Framework browsable API:
- http://localhost:8000/api/posts/
- http://localhost:8000/api/topics/
- http://localhost:8000/api/trends/
- и т.д.

---

**Статус:** Backend API полностью реализован и готов к использованию.  
**Следующий шаг:** Реализация UI компонентов для frontend.
