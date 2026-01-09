# Frontend Development Guide

## Что реализовано

### Backend (Django REST Framework) ✅

1. **Permissions** (`backend/api/permissions.py`):
   - `IsTenantMember` - доступ к чтению для всех участников клиента
   - `IsTenantOwnerOrEditor` - доступ к изменению только для owner/editor
   - `CanGenerateVideo` - генерация видео только в dev режиме или для zavod клиента

2. **Serializers** (`backend/api/serializers.py`):
   - Полные serializers для всех моделей (Post, Topic, Trend, Story, Template, etc.)
   - Разделение на list/detail версии
   - Read-only поля для ContentTemplate (type, tone, length, language)
   - Исключение id и name из ClientSettings

3. **ViewSets** (`backend/api/views.py`):
   - `PostViewSet` - CRUD + генерация (изображения, видео, текст) + quick publish
   - `TopicViewSet` - CRUD + поиск контента + генерация постов + SEO
   - `TrendItemViewSet` - просмотр/удаление + генерация постов/историй
   - `StoryViewSet` - CRUD + генерация постов из эпизодов
   - `ContentTemplateViewSet` - CRUD с ограничением редактирования основных полей
   - `ScheduleViewSet` - CRUD + немедленная публикация
   - `SocialAccountViewSet` - CRUD для соцсетей
   - `ClientSettingsView` - просмотр/обновление настроек клиента

4. **Routing** (`backend/api/urls.py`):
   - DRF Router для автоматической регистрации всех ViewSets
   - Все endpoints доступны через `/api/`

### Frontend API Client ✅

1. **Types** (`frontend/lib/types.ts`):
   - TypeScript типы для всех моделей
   - Status enums, платформы, роли

2. **API Functions** (`frontend/lib/api/`):
   - `posts.ts` - работа с постами + генерация
   - `topics.ts` - работа с темами
   - `trends.ts` - работа с трендами
   - `stories.ts` - работа с историями
   - `templates.ts` - работа с шаблонами
   - `schedules.ts` - работа с расписаниями
   - `socialAccounts.ts` - работа с соцсетями
   - `client.ts` - получение информации о клиенте и настройках

3. **Hooks** (`frontend/lib/hooks/`):
   - `useClient()` - получение информации о клиенте и роли
   - `useRole()` - получение роли пользователя (с флагами canEdit, canView)
   - `useCanGenerateVideo()` - проверка возможности генерации видео

---

## Что нужно реализовать (UI Components)

### Приоритет 1: Posts UI

#### Компоненты:

**`components/posts/post-detail-view.tsx`**
```tsx
import { useState } from 'react';
import { postsApi } from '@/lib/api';
import { useCanGenerateVideo, useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

export function PostDetailView({ postId }: { postId: number }) {
  const { canEdit } = useRole();
  const { canGenerateVideo } = useCanGenerateVideo();
  const [post, setPost] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch post data useEffect...

  const handleGenerateImage = async (model: string) => {
    setLoading(true);
    try {
      await postsApi.generateImage(postId, model);
      // Show success toast
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1>{post?.title}</h1>

      {/* Image generation dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button disabled={!canEdit || loading}>
            Generate Image
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem onClick={() => handleGenerateImage('pollinations')}>
            Pollinations AI
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => handleGenerateImage('nanobanana')}>
            Google Gemini (NanoBanana)
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => handleGenerateImage('huggingface')}>
            HuggingFace FLUX.1
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => handleGenerateImage('flux2')}>
            FLUX.2
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Video generation button */}
      <Button
        disabled={!canEdit || !canGenerateVideo || loading}
        variant={canGenerateVideo ? 'default' : 'secondary'}
        onClick={() => postsApi.generateVideo(postId)}
      >
        {canGenerateVideo ? 'Generate Video' : 'Generate Video (Dev only)'}
      </Button>

      {/* Regenerate text */}
      <Button disabled={!canEdit || loading} onClick={() => postsApi.regenerateText(postId)}>
        Regenerate Text
      </Button>

      {/* Image preview */}
      {post?.image && <img src={post.image} alt={post.title} />}

      {/* Video preview */}
      {post?.video && <video src={post.video} controls />}
    </div>
  );
}
```

**`components/posts/post-form.tsx`**
- Form для создания/редактирования поста
- Использовать `shadcn/ui` Form, Input, Textarea, Select

**`components/posts/quick-publish-dialog.tsx`**
- Dialog выбора соцсети для быстрой публикации
- Список из `socialAccountsApi.list()`

#### Страницы:

**`app/posts/new/page.tsx`**
- Страница создания нового поста

**`app/posts/[id]/page.tsx`**
- Страница просмотра/редактирования поста

---

### Приоритет 2: Topics & Trends UI

#### Компоненты:

**`components/topics/topics-list.tsx`**
- Table список тем с кнопками действий

**`components/topics/topic-actions.tsx`**
```tsx
export function TopicActions({ topicId }: { topicId: number }) {
  const { canEdit } = useRole();

  return (
    <div className="flex gap-2">
      <Button onClick={() => topicsApi.discoverContent(topicId)} disabled={!canEdit}>
        Discover Content
      </Button>
      <Button onClick={() => topicsApi.generatePosts(topicId)} disabled={!canEdit}>
        Generate Posts
      </Button>
      <Button onClick={() => topicsApi.generateSEO(topicId)} disabled={!canEdit}>
        Generate SEO
      </Button>
    </div>
  );
}
```

**`components/trends/trend-card.tsx`**
- Card с информацией о тренде

**`components/trends/generate-from-trend-menu.tsx`**
- DropdownMenu: Generate Post / Generate Story

#### Страницы:

**`app/topics/page.tsx`**
- Список тем

**`app/topics/[id]/page.tsx`**
- Детали темы + список трендов + кнопки действий

---

### Приоритет 3: Templates & Settings UI

#### Компоненты:

**`components/templates/template-form.tsx`**
```tsx
export function TemplateForm({ template }: { template?: ContentTemplate }) {
  const isEditing = !!template;

  return (
    <Form>
      {/* Basic fields - readonly if editing */}
      <FormField name="type">
        {isEditing ? (
          <Badge>{template.type}</Badge>
        ) : (
          <Select {...field} />
        )}
      </FormField>

      {/* Prompt templates */}
      <FormField name="seo_prompt_template">
        <Textarea {...field} />
      </FormField>
      <FormField name="trend_prompt_template">
        <Textarea {...field} />
      </FormField>
      <FormField name="additional_instructions">
        <Textarea {...field} />
      </FormField>
    </Form>
  );
}
```

**`components/settings/client-settings-form.tsx`**
```tsx
export function ClientSettingsForm() {
  const [settings, setSettings] = useState<ClientSettings | null>(null);

  useEffect(() => {
    clientApi.getSettings().then(setSettings);
  }, []);

  const handleSubmit = async (data: Partial<ClientSettings>) => {
    await clientApi.updateSettings(data);
    // Show success toast
  };

  return (
    <Form onSubmit={handleSubmit}>
      {/* Note: NO 'name' field */}
      <FormField name="timezone">
        <Select {...field} />
      </FormField>
      <FormField name="avatar">
        <Textarea {...field} />
      </FormField>
      {/* ... other fields */}
    </Form>
  );
}
```

**`components/settings/social-accounts-manager.tsx`**
- List + Add/Edit/Delete для соцсетей

#### Страницы:

**`app/templates/page.tsx`**
- Список шаблонов

**`app/templates/[id]/page.tsx`**
- Редактирование шаблона (основные поля readonly)

**`app/settings/page.tsx`**
- Tabs: Client Settings | Social Accounts

---

## Примеры использования shadcn/ui

### Form Example

```tsx
import { useForm } from 'react-hook-form';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';

export function MyForm() {
  const form = useForm();

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="title"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Title</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button type="submit">Submit</Button>
      </form>
    </Form>
  );
}
```

### Card Example

```tsx
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';

export function TrendCard({ trend }: { trend: TrendItem }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{trend.title}</CardTitle>
        <CardDescription>Source: {trend.source}</CardDescription>
      </CardHeader>
      <CardContent>
        <p>{trend.description}</p>
      </CardContent>
      <CardFooter>
        <Button onClick={() => trendsApi.generatePost(trend.id)}>
          Generate Post
        </Button>
      </CardFooter>
    </Card>
  );
}
```

### Dialog Example

```tsx
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

export function QuickPublishDialog({ postId }: { postId: number }) {
  const [accounts, setAccounts] = useState([]);

  useEffect(() => {
    socialAccountsApi.list().then(setAccounts);
  }, []);

  const handlePublish = async (accountId: number) => {
    await postsApi.quickPublish(postId, { social_account_id: accountId });
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button>Quick Publish</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Select Social Account</DialogTitle>
          <DialogDescription>Choose where to publish this post</DialogDescription>
        </DialogHeader>
        <div className="grid gap-2">
          {accounts.map((account) => (
            <Button key={account.id} onClick={() => handlePublish(account.id)}>
              {account.platform}: {account.name}
            </Button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
```

---

## Запуск проекта

### Backend

```bash
cd backend
source ../venv/bin/activate  # or: . ../venv/bin/activate
python manage.py migrate
python manage.py runserver
```

### Frontend

```bash
cd frontend
npm run dev
```

---

## Следующие шаги

1. **Создать базовые страницы** для Posts, Topics, Templates, Settings
2. **Реализовать компоненты генерации** с использованием новых API endpoints
3. **Добавить уведомления** (toast) для успешных/ошибочных операций
4. **Добавить loading states** во время выполнения асинхронных операций
5. **Тестирование** всех новых компонентов

---

## Полезные ссылки

- [shadcn/ui Documentation](https://ui.shadcn.com/)
- [API Documentation](./API_DOCUMENTATION.md)
- [Django REST Framework](https://www.django-rest-framework.org/)
