# Frontend разработка

Этот раздел содержит документацию по frontend части системы Zavod, построенной на Next.js.

## Содержание

- [Технологии](#технологии)
- [Структура проекта](#структура-проекта)
- [UI Компоненты](#ui-компоненты)
- [API интеграция](#api-интеграция)
- [Аутентификация](#аутентификация)
- [Разработка](#разработка)

## Технологии

### Основной стек

- **Next.js 15** - React фреймворк
- **TypeScript** - Типизация
- **Tailwind CSS** - Стили
- **shadcn/ui** - Компоненты
- **React Query** - Управление состоянием
- **Lucide React** - Иконки

### Дополнительные зависимости

```json
{
  "dependencies": {
    "@tanstack/react-query": "^5.0.0",
    "lucide-react": "^0.294.0",
    "react-hook-form": "^7.48.0",
    "zod": "^3.23.0",
    "clsx": "^2.0.0",
    "class-variance-authority": "^0.7.0"
  }
}
```

## Структура проекта

```
frontend/
├── app/                    # App Router
│   ├── layout.tsx         # Общий layout
│   ├── page.tsx           # Главная страница
│   ├── login/             # Страница авторизации
│   ├── dashboard/         # Админка
│   ├── posts/             # Управление постами
│   ├── topics/            # Темы и тренды
│   ├── templates/         # Шаблоны контента
│   ├── settings/          # Настройки клиента
│   └── analytics/         # Статистика
├── components/            # Компоненты
│   ├── ui/               # UI компоненты (shadcn/ui)
│   ├── auth/             # Авторизация
│   ├── layout/           # Layout компоненты
│   ├── posts/            # Посты
│   ├── topics/           # Темы
│   ├── templates/        # Шаблоны
│   └── settings/         # Настройки
├── lib/                  # Библиотеки
│   ├── api/             # API клиент
│   ├── hooks/           # Кастомные hooks
│   ├── types.ts         # TypeScript типы
│   └── utils.ts         # Утилиты
├── public/              # Статические файлы
└── styles/              # Стили
```

### App Router структура

Next.js 15 использует App Router с серверным рендерингом:

- **`app/layout.tsx`** - Общий layout для всех страниц
- **`app/page.tsx`** - Главная страница
- **`app/login/page.tsx`** - Страница авторизации
- **`app/(dashboard)/`** - Protected routes (через группировку)

### Protected Routes

Для защищенных маршрутов используется группировка:

```
app/
├── (dashboard)/         # Группа защищенных маршрутов
│   ├── layout.tsx      # Layout для авторизованных
│   ├── page.tsx        # Dashboard
│   ├── posts/          # Посты
│   └── settings/       # Настройки
└── login/              # Публичная страница
```

## UI Компоненты

### shadcn/ui

Проект использует [shadcn/ui](https://ui.shadcn.com/) для базовых компонентов:

```bash
# Установка shadcn/ui
npx shadcn-ui@latest init

# Добавление компонентов
npx shadcn-ui@latest add button
npx shadcn-ui@latest add form
npx shadcn-ui@latest add input
npx shadcn-ui@latest add card
```

### Кастомные компоненты

#### Telegram Auth

```tsx
// components/auth/TelegramAuth.tsx
'use client';

export function TelegramAuth() {
  const { mutate: login, isPending } = useTelegramAuth();
  
  const handleAuth = (user: TelegramUser) => {
    login(user);
  };
  
  return (
    <div>
      <button onClick={handleAuth} disabled={isPending}>
        Войти через Telegram
      </button>
    </div>
  );
}
```

#### Post Form

```tsx
// components/posts/post-form.tsx
'use client';

export function PostForm({ post }: { post?: Post }) {
  const { register, handleSubmit, control } = useForm<PostFormData>({
    defaultValues: post || {}
  });
  
  const onSubmit = handleSubmit((data) => {
    // Сохранение поста
  });
  
  return (
    <form onSubmit={onSubmit}>
      <Input {...register('title')} placeholder="Заголовок" />
      <Controller
        control={control}
        name="text"
        render={({ field }) => (
          <Textarea {...field} placeholder="Текст поста" />
        )}
      />
      <Button type="submit">Сохранить</Button>
    </form>
  );
}
```

#### Data Table

```tsx
// components/ui/data-table.tsx
'use client';

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[];
  data: TData[];
}

export function DataTable<TData, TValue>({
  columns,
  data,
}: DataTableProps<TData, TValue>) {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationModel: getPaginationRowModel(),
  });

  return (
    <div>
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map((headerGroup) => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <TableHead key={header.id}>
                  {header.isPlaceholder
                    ? null
                    : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows?.length ? (
            table.getRowModel().rows.map((row) => (
              <TableRow
                key={row.id}
                data-state={row.getIsSelected() && "selected"}
              >
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id}>
                    {flexRender(
                      cell.column.columnDef.cell,
                      cell.getContext()
                    )}
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : (
            <TableRow>
              <TableCell colSpan={columns.length} className="h-24 text-center">
                Нет данных
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      
      <div className="flex items-center justify-end space-x-2 py-4">
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.previousPage()}
          disabled={!table.getCanPreviousPage()}
        >
          Назад
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => table.nextPage()}
          disabled={!table.getCanNextPage()}
        >
          Вперед
        </Button>
      </div>
    </div>
  );
}
```

## API интеграция

### API Client

```tsx
// lib/api/client.ts
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Interceptor для аутентификации
apiClient.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default apiClient;
```

### API Functions

```tsx
// lib/api/posts.ts
import apiClient from './client';
import { Post, PostFormData } from '@/lib/types';

export const postsApi = {
  // Список постов
  list: (params?: { status?: string; platform?: string }) =>
    apiClient.get<Post[]>('/api/posts/', { params }),
  
  // Получение поста
  get: (id: number) => apiClient.get<Post>(`/api/posts/${id}/`),
  
  // Создание поста
  create: (data: PostFormData) =>
    apiClient.post<Post>('/api/posts/', data),
  
  // Обновление поста
  update: (id: number, data: Partial<PostFormData>) =>
    apiClient.patch<Post>(`/api/posts/${id}/`, data),
  
  // Удаление поста
  delete: (id: number) => apiClient.delete(`/api/posts/${id}/`),
  
  // Генерация изображения
  generateImage: (id: number, model: string) =>
    apiClient.post(`/api/posts/${id}/generate_image/`, { model }),
  
  // Генерация видео
  generateVideo: (id: number) =>
    apiClient.post(`/api/posts/${id}/generate_video/`),
  
  // Регенерация текста
  regenerateText: (id: number) =>
    apiClient.post(`/api/posts/${id}/regenerate_text/`),
  
  // Быстрая публикация
  quickPublish: (id: number, data: { social_account_id: number }) =>
    apiClient.post(`/api/posts/${id}/quick_publish/`, data),
};
```

### React Query

```tsx
// lib/hooks/use-posts.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { postsApi } from '@/lib/api';

export const usePosts = (params?: { status?: string }) => {
  return useQuery({
    queryKey: ['posts', params],
    queryFn: () => postsApi.list(params).then(res => res.data),
  });
};

export const usePost = (id: number) => {
  return useQuery({
    queryKey: ['posts', id],
    queryFn: () => postsApi.get(id).then(res => res.data),
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
```

## Аутентификация

### Telegram WebApp Auth

```tsx
// lib/api/auth.ts
import apiClient from './client';

export const authApi = {
  // Telegram аутентификация
  telegram: (userData: TelegramAuthData) =>
    apiClient.post('/api/auth/telegram', userData),
  
  // Dev mode login
  devLogin: () => apiClient.put('/api/auth/telegram'),
  
  // Logout
  logout: () => apiClient.delete('/api/auth/telegram'),
  
  // Получение информации о клиенте
  clientInfo: () => apiClient.get('/api/client/info/'),
};
```

### Auth Context

```tsx
// lib/contexts/auth-context.tsx
'use client';

import { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  client: Client | null;
  role: string | null;
  loading: boolean;
  login: (userData: TelegramAuthData) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
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
      const response = await authApi.clientInfo();
      setUser(response.data.user);
      setClient(response.data.client);
      setRole(response.data.role);
    } catch (error) {
      // Пользователь не авторизован
    } finally {
      setLoading(false);
    }
  };

  const login = async (userData: TelegramAuthData) => {
    const response = await authApi.telegram(userData);
    setUser(response.data.user);
    setClient(response.data.client);
    setRole(response.data.role);
  };

  const logout = async () => {
    await authApi.logout();
    setUser(null);
    setClient(null);
    setRole(null);
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

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { loading, user } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return <>{children}</>;
}
```

## Разработка

### Запуск проекта

```bash
# Установка зависимостей
npm install

# Запуск в dev режиме
npm run dev

# Сборка
npm run build

# Запуск production версии
npm run start
```

### Environment Variables

Создайте `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_TELEGRAM_BOT_USERNAME=your_bot_username
NEXT_PUBLIC_DEV_MODE=false
```

### Стили

Проект использует Tailwind CSS:

```css
/* styles/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Кастомные стили */
@layer components {
  .btn-primary {
    @apply bg-blue-500 hover:bg-blue-600 text-white;
  }
}
```

### Типы

```tsx
// lib/types.ts
export interface User {
  id: number;
  telegramId: string;
  firstName: string;
  lastName: string;
  username: string;
  photoUrl: string | null;
  isDev: boolean;
}

export interface Client {
  id: number;
  name: string;
  slug: string;
}

export interface Post {
  id: number;
  title: string;
  text: string;
  status: PostStatus;
  tags: string[];
  images: PostImage[];
  videos: PostVideo[];
  createdAt: string;
  updatedAt: string;
}

export type PostStatus = 'draft' | 'ready' | 'approved' | 'scheduled' | 'published';
```

### Testing

```tsx
// __tests__/api.test.ts
import { postsApi } from '@/lib/api';

describe('Posts API', () => {
  it('should fetch posts', async () => {
    const response = await postsApi.list();
    expect(response.data).toBeInstanceOf(Array);
  });
});
```

---

**Далее:**
- [API Integration](./api-integration.md) - Подробнее об интеграции с API
- [UI Components](./ui-components.md) - Документация по компонентам
- [Deployment](../07-deployment/docker.md) - Деплоймент frontend
