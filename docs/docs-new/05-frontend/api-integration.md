# API Integration

В этом документе описана интеграция frontend части системы Zavod с backend API.

## Содержание

- [Архитектура](#архитектура)
- [API Client](#api-client)
- [React Query](#react-query)
- [Аутентификация](#аутентификация)
- [Обработка ошибок](#обработка-ошибок)
- [Типы данных](#типы-данных)
- [Примеры использования](#примеры-использования)

## Архитектура

### Структура API слоя

```
frontend/
├── lib/
│   ├── api/
│   │   ├── client.ts          # Базовый API клиент
│   │   ├── index.ts           # Экспорт всех API функций
│   │   ├── auth.ts            # Авторизация
│   │   ├── posts.ts           # Посты
│   │   ├── topics.ts          # Темы
│   │   ├── trends.ts          # Тренды
│   │   ├── stories.ts         # Истории
│   │   ├── templates.ts       # Шаблоны
│   │   ├── schedules.ts       # Публикации
│   │   ├── social-accounts.ts # Социальные сети
│   │   └── client.ts          # Клиент
│   └── types.ts               # TypeScript типы
├── components/
│   ├── ui/                    # UI компоненты (shadcn/ui)
│   ├── auth/                  # Авторизация
│   ├── layout/                # Layout компоненты
│   ├── posts/                 # Посты
│   ├── topics/                # Темы
│   ├── templates/             # Шаблоны
│   └── settings/              # Настройки
└── lib/
    ├── hooks/                 # Кастомные hooks
    └── contexts/              # Context API
```

### Принципы

1. **Разделение ответственности**: Каждый модуль отвечает за свою область
2. **Типизация**: Полная типизация с использованием TypeScript
3. **Кэширование**: Использование React Query для кэширования и управления состоянием
4. **Повторное использование**: Максимальное переиспользование кода
5. **Обработка ошибок**: Централизованная обработка ошибок

## API Client

### Базовый клиент

```typescript
// lib/api/client.ts
import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';

// Интерсепторы для логирования
const logRequest = (config: AxiosRequestConfig) => {
  console.log(`[API] ${config.method?.toUpperCase()} ${config.url}`);
  console.log('[API] Request:', config.data);
  return config;
};

const logResponse = (response: AxiosResponse) => {
  console.log(`[API] ${response.status} ${response.config.url}`);
  console.log('[API] Response:', response.data);
  return response;
};

const handleError = (error: any) => {
  console.error('[API] Error:', error.response?.data || error.message);
  return Promise.reject(error);
};

// Создание базового клиента
export const createApiClient = (baseURL: string): AxiosInstance => {
  const client = axios.create({
    baseURL,
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: 30000,
  });

  // Интерсепторы
  client.interceptors.request.use(logRequest, handleError);
  client.interceptors.response.use(logResponse, handleError);

  return client;
};

// Экспорт базового клиента
const apiClient = createApiClient(
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
);

export default apiClient;
```

### Аутентификация

```typescript
// lib/api/client.ts (продолжение)
import { getAuthToken } from './auth';

// Интерсептор для аутентификации
apiClient.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Функция получения токена
export const getAuthToken = (): string | null => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('token');
  }
  return null;
};

// Функция установки токена
export const setAuthToken = (token: string): void => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('token', token);
  }
};

// Функция удаления токена
export const clearAuthToken = (): void => {
  if (typeof window !== 'undefined') {
    localStorage.removeItem('token');
  }
};
```

### API Fetch функция

```typescript
// lib/api/client.ts (продолжение)
import { ApiError } from './types';

export interface ApiFetchOptions extends AxiosRequestConfig {
  params?: Record<string, any>;
  data?: any;
}

export async function apiFetch<T = any>(
  url: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  try {
    const response = await apiClient({
      url,
      ...options,
      params: {
        ...options.params,
        // Добавляем общие параметры
      },
    });
    return response.data;
  } catch (error: any) {
    if (error.response) {
      // Сервер вернул ошибку
      const apiError: ApiError = {
        status: error.response.status,
        message: error.response.data?.detail || 'Server error',
        data: error.response.data,
      };
      throw apiError;
    } else if (error.request) {
      // Запрос был сделан, но ответа не получено
      throw new Error('Network error: No response received');
    } else {
      // Ошибка при настройке запроса
      throw new Error(`Request error: ${error.message}`);
    }
  }
}
```

## React Query

### Query Client Setup

```typescript
// lib/query-client.ts
import { QueryClient } from '@tanstack/react-query';

export const createQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Не ретраить 4xx ошибки
        if (error && typeof error === 'object' && 'status' in error) {
          const status = (error as any).status;
          if (status >= 400 && status < 500) {
            return false;
          }
        }
        return failureCount < 3;
      },
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
      staleTime: 5 * 60 * 1000, // 5 минут
      cacheTime: 10 * 60 * 1000, // 10 минут
    },
    mutations: {
      retry: 1,
    },
  },
});
```

### Query Provider

```tsx
// app/providers.tsx
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState } from 'react';

export default function QueryProviders({
  children,
}: {
  children: React.ReactNode;
}) {
  const [queryClient] = useState(() => createQueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

### Кастомные Hooks

```typescript
// lib/hooks/use-posts.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { postsApi } from '@/lib/api';

export const usePosts = (params?: { status?: string; platform?: string }) => {
  return useQuery({
    queryKey: ['posts', params],
    queryFn: () => postsApi.list(params),
    select: (data) => data.results || data, // Поддержка пагинации
  });
};

export const usePost = (id: number) => {
  return useQuery({
    queryKey: ['posts', id],
    queryFn: () => postsApi.get(id),
    enabled: !!id,
  });
};

export const useCreatePost = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: postsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] });
    },
  });
};

export const useUpdatePost = (id: number) => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<PostFormData>) => postsApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] });
      queryClient.invalidateQueries({ queryKey: ['posts', id] });
    },
  });
};

export const useDeletePost = () => {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: postsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['posts'] });
    },
  });
};
```

## Аутентификация

### Auth API

```typescript
// lib/api/auth.ts
import apiClient from './client';
import { AuthResponse, TelegramUser } from './types';

export const authApi = {
  // Telegram аутентификация
  telegram: (userData: TelegramUser) =>
    apiClient.post<AuthResponse>('/api/auth/telegram', userData),
  
  // Dev mode login
  devLogin: () =>
    apiClient.put<AuthResponse>('/api/auth/telegram/dev'),
  
  // Logout
  logout: () =>
    apiClient.delete('/api/auth/telegram/logout'),
  
  // Получение информации о клиенте
  clientInfo: () =>
    apiClient.get('/api/client/info/'),
};
```

### Auth Context

```typescript
// lib/contexts/auth-context.tsx
'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi } from '@/lib/api';

interface User {
  id: number;
  telegram_id: string;
  first_name: string;
  last_name: string;
  username: string;
  photo_url: string | null;
  is_dev: boolean;
}

interface Client {
  id: number;
  name: string;
  slug: string;
}

interface AuthContextType {
  user: User | null;
  client: Client | null;
  role: string | null;
  loading: boolean;
  login: (data: AuthResponse) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [client, setClient] = useState<Client | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Проверка аутентификации при загрузке
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('token');
      if (token) {
        const response = await authApi.clientInfo();
        setUser(response.data.user);
        setClient(response.data.client);
        setRole(response.data.role);
      }
    } catch (error) {
      // Пользователь не авторизован
      console.error('Auth check failed:', error);
    } finally {
      setLoading(false);
    }
  };

  const login = (data: AuthResponse) => {
    setUser(data.user);
    setClient(data.client);
    setRole(data.role);
    localStorage.setItem('token', data.tokens.access);
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setUser(null);
      setClient(null);
      setRole(null);
      localStorage.removeItem('token');
    }
  };

  return (
    <AuthContext.Provider value={{ user, client, role, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

### Protected Route

```tsx
// components/layout/protected-route.tsx
'use client';

import { useAuth } from '@/lib/contexts/auth-context';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { TelegramAuth } from '@/components/auth/telegram-auth';

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <LoadingSpinner />
      </div>
    );
  }

  if (!user) {
    return <TelegramAuth />;
  }

  return <>{children}</>;
}
```

## Обработка ошибок

### Error Boundaries

```tsx
// components/error-boundary.tsx
'use client';

import { Component, ErrorInfo, ReactNode } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="container mx-auto px-4 py-8">
          <Alert variant="destructive">
            <AlertTitle>Что-то пошло не так</AlertTitle>
            <AlertDescription>
              {this.state.error?.message || 'Произошла ошибка. Пожалуйста, перезагрузите страницу.'}
            </AlertDescription>
          </Alert>
          <div className="mt-4">
            <Button onClick={() => window.location.reload()}>
              Перезагрузить страницу
            </Button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
```

### API Error Handler

```typescript
// lib/api/error-handler.ts
import { ApiError } from './types';

export class ApiErrorHandler {
  static handle(error: ApiError): string {
    switch (error.status) {
      case 401:
        return 'Требуется авторизация. Пожалуйста, войдите в систему.';
      case 403:
        return 'Доступ запрещен. У вас недостаточно прав.';
      case 404:
        return 'Ресурс не найден.';
      case 422:
        return 'Некорректные данные. Пожалуйста, проверьте введенные данные.';
      case 500:
        return 'Ошибка сервера. Пожалуйста, попробуйте позже.';
      default:
        return error.message || 'Произошла ошибка.';
    }
  }

  static isAuthError(error: ApiError): boolean {
    return error.status === 401;
  }

  static isValidationError(error: ApiError): boolean {
    return error.status === 422;
  }
}
```

### Toast Notifications

```typescript
// lib/hooks/use-toast.ts
import { useToast as useShadcnToast } from '@/components/ui/use-toast';

export const useApiToast = () => {
  const { toast } = useShadcnToast();

  const showSuccess = (message: string) => {
    toast({
      title: 'Успешно',
      description: message,
      variant: 'default',
    });
  };

  const showError = (error: ApiError) => {
    toast({
      title: 'Ошибка',
      description: ApiErrorHandler.handle(error),
      variant: 'destructive',
    });
  };

  const showWarning = (message: string) => {
    toast({
      title: 'Внимание',
      description: message,
      variant: 'default',
    });
  };

  return { showSuccess, showError, showWarning };
};
```

## Типы данных

### Base Types

```typescript
// lib/types.ts
export interface BaseEntity {
  id: number;
  created_at: string;
  updated_at: string;
}

export type PostStatus = 'draft' | 'ready' | 'approved' | 'scheduled' | 'published';
export type ScheduleStatus = 'pending' | 'in_progress' | 'published' | 'failed';
export type StoryStatus = 'generating' | 'completed' | 'posts_created';
export type Platform = 'instagram' | 'telegram' | 'youtube';
export type ContentType = 'selling' | 'informative' | 'educational' | 'entertainment';
export type Tone = 'professional' | 'friendly' | 'enthusiastic' | 'serious';
export type Length = 'short' | 'medium' | 'long';
export type Language = 'ru' | 'en';
export type TrendSource = 'rss' | 'google_trends' | 'telegram' | 'youtube' | 'instagram' | 'vkontakte';
export type UserRole = 'owner' | 'editor' | 'viewer';

export interface User extends BaseEntity {
  telegram_id: string;
  first_name: string;
  last_name: string;
  username: string;
  photo_url: string | null;
  is_dev: boolean;
}

export interface Client extends BaseEntity {
  name: string;
  slug: string;
}

export interface Post extends BaseEntity {
  client: Client;
  title: string;
  text: string;
  status: PostStatus;
  tags: string[];
  images: PostImage[];
  videos: PostVideo[];
  generated_by: string;
  source_links: string[];
  episode_number?: number;
  regeneration_count: number;
  published_at?: string;
}

export interface PostImage extends BaseEntity {
  post: Post;
  image: string;
  prompt: string;
  model: string;
  is_published: boolean;
}

export interface PostVideo extends BaseEntity {
  post: Post;
  video: string;
  prompt: string;
  is_published: boolean;
}

export interface Topic extends BaseEntity {
  client: Client;
  name: string;
  description: string;
  is_active: boolean;
  use_google_trends: boolean;
  use_instagram: boolean;
  google_trends_query: string;
  instagram_hashtags: string[];
  instagram_accounts: string[];
  vkontakte_groups: string[];
  telegram_channels: string[];
  rss_feeds: string[];
  last_discovery_at?: string;
  last_generation_at?: string;
  last_seo_generation_at?: string;
}

export interface TrendItem extends BaseEntity {
  topic: Topic;
  title: string;
  description: string;
  url?: string;
  source: TrendSource;
  source_url?: string;
  published_at?: string;
  used_for_post?: Post;
  used_for_post_title?: string;
}

export interface Story extends BaseEntity {
  client: Client;
  title: string;
  trend_item: TrendItem;
  trend_title: string;
  template: ContentTemplate;
  episode_count: number;
  status: StoryStatus;
}

export interface StoryEpisode extends BaseEntity {
  story: Story;
  order: number;
  title: string;
  text?: string;
  post?: Post;
}

export interface ContentTemplate extends BaseEntity {
  client: Client;
  name: string;
  type: ContentType;
  tone: Tone;
  length: Length;
  language: Language;
  seo_prompt_template: string;
  trend_prompt_template: string;
  additional_instructions: string;
  include_hashtags: boolean;
  max_hashtags: number;
  is_default: boolean;
}

export interface SEOKeywordSet extends BaseEntity {
  client: Client;
  topic: Topic;
  keywords: string[];
  group_type: 'topic' | 'trend';
}

export interface SocialAccount extends BaseEntity {
  client: Client;
  platform: Platform;
  name: string;
  username: string;
  access_token: string;
  refresh_token?: string;
  is_active: boolean;
  extra: Record<string, any>;
}

export interface Schedule extends BaseEntity {
  client: Client;
  post: Post;
  social_account: SocialAccount;
  scheduled_at: string;
  status: ScheduleStatus;
  external_id?: string;
  log?: string;
  published_at?: string;
}

export interface ClientSettings extends BaseEntity {
  client: Client;
  auto_generate_images: boolean;
  auto_generate_videos: boolean;
  default_image_model: string;
  default_video_model: string;
  image_generation_timeout: number;
  video_generation_timeout: number;
  fallback_ai_model: string;
}

export interface ClientInfo {
  user: User;
  client: Client;
  role: UserRole;
}

export interface AuthResponse {
  success: boolean;
  user: User;
  client: Client | null;
  role: string | null;
  tokens: {
    access: string;
    refresh: string;
  };
}

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  hash: string;
}

export interface ApiError {
  status: number;
  message: string;
  data?: any;
}
```

## Примеры использования

### Posts Page

```tsx
// app/posts/page.tsx
'use client';

import { usePosts, useDeletePost } from '@/lib/hooks/use-posts';
import { DataTable } from '@/components/ui/data-table';
import { columns } from './columns';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

export default function PostsPage() {
  const { data: posts, isLoading, error } = usePosts();
  const deletePost = useDeletePost();
  const { toast } = useToast();

  const handleDelete = async (postId: number) => {
    try {
      await deletePost.mutateAsync(postId);
      toast({
        title: 'Успешно',
        description: 'Пост удален',
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось удалить пост',
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return <div>Загрузка...</div>;
  }

  if (error) {
    return <div>Ошибка загрузки постов</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Посты</h1>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Новый пост
        </Button>
      </div>
      
      <DataTable columns={columns} data={posts || []} />
    </div>
  );
}
```

### Post Form

```tsx
// components/posts/post-form.tsx
'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { PostFormData } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { useCreatePost, useUpdatePost } from '@/lib/hooks/use-posts';

const formSchema = z.object({
  title: z.string().min(1, 'Заголовок обязателен'),
  text: z.string().min(1, 'Текст обязателен'),
  status: z.enum(['draft', 'ready', 'approved', 'scheduled', 'published']),
  tags: z.array(z.string()),
});

interface PostFormProps {
  initialData?: PostFormData;
  onSuccess?: () => void;
}

export function PostForm({ initialData, onSuccess }: PostFormProps) {
  const form = useForm<PostFormData>({
    resolver: zodResolver(formSchema),
    defaultValues: initialData || {
      title: '',
      text: '',
      status: 'draft',
      tags: [],
    },
  });

  const createPost = useCreatePost();
  const updatePost = useUpdatePost(initialData?.id || 0);

  const onSubmit = async (data: PostFormData) => {
    try {
      if (initialData) {
        await updatePost.mutateAsync(data);
      } else {
        await createPost.mutateAsync(data);
      }
      onSuccess?.();
    } catch (error) {
      console.error('Error saving post:', error);
    }
  };

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Заголовок</label>
          <Input {...form.register('title')} />
          {form.formState.errors.title && (
            <p className="text-red-500 text-sm">{form.formState.errors.title.message}</p>
          )}
        </div>
      </div>
      
      <div className="space-y-2">
        <label className="text-sm font-medium">Текст</label>
        <Textarea {...form.register('text')} rows={10} />
        {form.formState.errors.text && (
          <p className="text-red-500 text-sm">{form.formState.errors.text.message}</p>
        )}
      </div>
      
      <div className="flex gap-2">
        <Button type="submit" disabled={createPost.isPending || updatePost.isPending}>
          {createPost.isPending || updatePost.isPending ? 'Сохранение...' : 'Сохранить'}
        </Button>
      </div>
    </form>
  );
}
```

### Topics with Infinite Query

```tsx
// app/topics/page.tsx
'use client';

import { useInfiniteQuery } from '@tanstack/react-query';
import { topicsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Plus } from 'lucide-react';

export default function TopicsPage() {
  const {
    data,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    isLoading,
    error,
  } = useInfiniteQuery({
    queryKey: ['topics'],
    queryFn: ({ pageParam = 1 }) => topicsApi.list({ page: pageParam }),
    getNextPageParam: (lastPage, pages) => {
      // Логика определения следующей страницы
      if (lastPage.next) {
        return pages.length + 1;
      }
      return undefined;
    },
  });

  if (isLoading) {
    return <div>Загрузка...</div>;
  }

  if (error) {
    return <div>Ошибка загрузки тем</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Темы</h1>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          Новая тема
        </Button>
      </div>
      
      <div className="grid gap-4">
        {data?.pages.map((page, pageIndex) => (
          <div key={pageIndex} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {page.results.map((topic) => (
              <Card key={topic.id}>
                <CardHeader>
                  <CardTitle>{topic.name}</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-600">{topic.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        ))}
      </div>
      
      {hasNextPage && (
        <Button onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
          {isFetchingNextPage ? 'Загрузка...' : 'Загрузить еще'}
        </Button>
      )}
    </div>
  );
}
```

---

**Далее:**
- [UI Components](./ui-components.md) - UI компоненты
- [Authentication](../02-api/telegram-auth.md) - Аутентификация
- [Backend Integration](../06-backend/setup.md) - Backend интеграция
