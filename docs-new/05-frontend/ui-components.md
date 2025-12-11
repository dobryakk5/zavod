# UI Components

В этом документе описана система UI компонентов для frontend части системы Zavod.

## Содержание

- [Архитектура](#архитектура)
- [shadcn/ui](#shadcnui)
- [Кастомные компоненты](#кастомные-компоненты)
- [Типографика](#типографика)
- [Цвета](#цвета)
- [Примеры использования](#примеры-использования)

## Архитектура

### Структура компонентов

```
frontend/
├── components/
│   ├── ui/                    # Базовые UI компоненты (shadcn/ui)
│   │   ├── button.tsx         # Кнопка
│   │   ├── input.tsx          # Инпут
│   │   ├── textarea.tsx       # Текстовое поле
│   │   ├── card.tsx           # Карточка
│   │   ├── table.tsx          # Таблица
│   │   ├── modal.tsx          # Модальное окно
│   │   ├── toast.tsx          # Уведомления
│   │   └── ...
│   ├── auth/                  # Авторизация
│   │   ├── telegram-auth.tsx  # Telegram аутентификация
│   │   └── dev-login.tsx      # Dev login
│   ├── layout/                # Layout компоненты
│   │   ├── app-shell.tsx      # Главный layout
│   │   ├── protected-route.tsx # Защищенный маршрут
│   │   └── navigation.tsx     # Навигация
│   ├── posts/                 # Посты
│   │   ├── post-form.tsx      # Форма поста
│   │   ├── post-detail.tsx    # Детали поста
│   │   ├── post-list.tsx      # Список постов
│   │   └── generate-image-menu.tsx # Меню генерации изображения
│   ├── topics/                # Темы
│   │   ├── topics-list.tsx    # Список тем
│   │   ├── topic-form.tsx     # Форма темы
│   │   └── topic-actions.tsx  # Действия с темой
│   ├── trends/                # Тренды
│   │   ├── trend-card.tsx     # Карточка тренда
│   │   └── generate-from-trend-menu.tsx # Меню генерации из тренда
│   ├── stories/               # Истории
│   │   ├── stories-list.tsx   # Список историй
│   │   ├── story-detail.tsx   # Детали истории
│   │   └── generate-posts-button.tsx # Генерация постов из истории
│   ├── templates/             # Шаблоны
│   │   ├── templates-list.tsx # Список шаблонов
│   │   └── template-form.tsx  # Форма шаблона
│   └── settings/              # Настройки
│       ├── client-settings-form.tsx # Форма настроек клиента
│       └── social-accounts-manager.tsx # Менеджер социальных сетей
└── lib/
    ├── hooks/                 # Кастомные hooks
    │   ├── use-posts.ts       # Работа с постами
    │   ├── use-topics.ts      # Работа с темами
    │   └── use-auth.ts        # Аутентификация
    └── contexts/              # Context API
        └── auth-context.tsx   # Auth context
```

### Принципы

1. **Reusability** - Максимальное переиспользование компонентов
2. **Consistency** - Единый стиль и поведение
3. **Accessibility** - Поддержка a11y стандартов
4. **Type Safety** - Полная типизация TypeScript
5. **Performance** - Оптимизация производительности

## shadcn/ui

### Установка и настройка

```bash
# Установка shadcn/ui
npx shadcn-ui@latest init

# Добавление компонентов
npx shadcn-ui@latest add button
npx shadcn-ui@latest add form
npx shadcn-ui@latest add input
npx shadcn-ui@latest add card
npx shadcn-ui@latest add table
npx shadcn-ui@latest add modal
npx shadcn-ui@latest add toast
```

### Конфигурация

```typescript
// components/ui/button.tsx
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline:
          "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
```

### Tailwind конфигурация

```typescript
// tailwind.config.ts
import { fontFamily } from "tailwindcss/defaultTheme";

/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["src/app/**/*.{ts,tsx}", "src/components/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: `var(--radius)`,
        md: `calc(var(--radius) - 2px)`,
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", ...fontFamily.sans],
      },
      boxShadow: {
        "card": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
        "card-hover": "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
      },
    },
  },
  plugins: [],
}
```

## Кастомные компоненты

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
import { useToast } from '@/components/ui/use-toast';
import { Loader2 } from 'lucide-react';

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
  const { toast } = useToast();

  const onSubmit = async (data: PostFormData) => {
    try {
      if (initialData) {
        await updatePost.mutateAsync(data);
        toast({
          title: 'Успешно',
          description: 'Пост обновлен',
        });
      } else {
        await createPost.mutateAsync(data);
        toast({
          title: 'Успешно',
          description: 'Пост создан',
        });
      }
      onSuccess?.();
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось сохранить пост',
        variant: 'destructive',
      });
    }
  };

  const isLoading = createPost.isPending || updatePost.isPending;

  return (
    <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">Заголовок</label>
          <Input 
            {...form.register('title')} 
            disabled={isLoading}
            placeholder="Введите заголовок поста"
          />
          {form.formState.errors.title && (
            <p className="text-red-500 text-sm">{form.formState.errors.title.message}</p>
          )}
        </div>
        
        <div className="space-y-2">
          <label className="text-sm font-medium">Статус</label>
          <select 
            {...form.register('status')}
            disabled={isLoading}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="draft">Черновик</option>
            <option value="ready">Готов к публикации</option>
            <option value="approved">Одобрен</option>
            <option value="scheduled">Запланирован</option>
            <option value="published">Опубликован</option>
          </select>
        </div>
      </div>
      
      <div className="space-y-2">
        <label className="text-sm font-medium">Текст</label>
        <Textarea 
          {...form.register('text')} 
          rows={10}
          disabled={isLoading}
          placeholder="Введите текст поста"
        />
        {form.formState.errors.text && (
          <p className="text-red-500 text-sm">{form.formState.errors.text.message}</p>
        )}
      </div>
      
      <div className="space-y-2">
        <label className="text-sm font-medium">Теги</label>
        <Input 
          {...form.register('tags')} 
          disabled={isLoading}
          placeholder="Введите теги через запятую"
        />
      </div>
      
      <div className="flex gap-2">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Сохранение...
            </>
          ) : (
            'Сохранить'
          )}
        </Button>
        
        <Button 
          type="button" 
          variant="outline" 
          onClick={() => form.reset()}
          disabled={isLoading}
        >
          Сбросить
        </Button>
      </div>
    </form>
  );
}
```

### Data Table

```tsx
// components/ui/data-table.tsx
'use client';

import * as React from "react"
import {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table"
import { ArrowUpDown } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

interface DataTableProps<TData, TValue> {
  columns: ColumnDef<TData, TValue>[]
  data: TData[]
}

export function DataTable<TData, TValue>({
  columns,
  data,
}: DataTableProps<TData, TValue>) {
  const [sorting, setSorting] = React.useState<SortingState>([])
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({})

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    onSortingChange: setSorting,
    getSortedRowModel: getSortedRowModel(),
    onColumnFiltersChange: setColumnFilters,
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
    },
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Input
          placeholder="Поиск..."
          value={(table.getColumn("title")?.getFilterValue() as string) ?? ""}
          onChange={(event) =>
            table.getColumn("title")?.setFilterValue(event.target.value)
          }
          className="max-w-sm"
        />
        
        <div className="flex items-center space-x-2">
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

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  return (
                    <TableHead key={header.id}>
                      {header.isPlaceholder
                        ? null
                        : flexRender(
                            header.column.columnDef.header,
                            header.getContext()
                          )}
                    </TableHead>
                  )
                })}
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
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  Нет данных.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-end space-x-2">
        <div className="flex-1 text-sm text-muted-foreground">
          {table.getFilteredSelectedRowModel().rows.length} из{" "}
          {table.getFilteredRowModel().rows.length} строк выбрано.
        </div>
        <div className="space-x-2">
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
    </div>
  )
}
```

### Generate Image Menu

```tsx
// components/posts/generate-image-menu.tsx
'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { useGenerateImage } from '@/lib/hooks/use-posts';
import { useToast } from '@/components/ui/use-toast';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Image as ImageIcon } from 'lucide-react';

interface GenerateImageMenuProps {
  postId: number;
}

export function GenerateImageMenu({ postId }: GenerateImageMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const generateImage = useGenerateImage();
  const { toast } = useToast();

  const handleGenerate = async (model: string) => {
    try {
      await generateImage.mutateAsync({ postId, model });
      toast({
        title: 'Успешно',
        description: 'Изображение генерируется',
      });
      setIsOpen(false);
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось начать генерацию изображения',
        variant: 'destructive',
      });
    }
  };

  return (
    <DropdownMenu open={isOpen} onOpenChange={setIsOpen}>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <ImageIcon className="mr-2 h-4 w-4" />
          Сгенерировать изображение
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuItem onClick={() => handleGenerate('pollinations')}>
          Pollinations AI
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleGenerate('nanobanana')}>
          Google Gemini (NanoBanana)
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleGenerate('huggingface')}>
          HuggingFace FLUX.1
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleGenerate('flux2')}>
          Stable Diffusion (Flux.2)
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

### Trend Card

```tsx
// components/trends/trend-card.tsx
'use client';

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useGeneratePostFromTrend, useGenerateStoryFromTrend } from '@/lib/hooks/use-trends';
import { useToast } from '@/components/ui/use-toast';
import { Plus, Sparkles } from 'lucide-react';

interface TrendCardProps {
  trend: TrendItem;
}

export function TrendCard({ trend }: TrendCardProps) {
  const generatePost = useGeneratePostFromTrend();
  const generateStory = useGenerateStoryFromTrend();
  const { toast } = useToast();

  const handleGeneratePost = async () => {
    try {
      await generatePost.mutateAsync(trend.id);
      toast({
        title: 'Успешно',
        description: 'Пост генерируется',
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось начать генерацию поста',
        variant: 'destructive',
      });
    }
  };

  const handleGenerateStory = async () => {
    try {
      await generateStory.mutateAsync(trend.id);
      toast({
        title: 'Успешно',
        description: 'История генерируется',
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось начать генерацию истории',
        variant: 'destructive',
      });
    }
  };

  return (
    <Card className="hover:shadow-lg transition-shadow duration-200">
      <CardHeader>
        <CardTitle className="text-lg">{trend.title}</CardTitle>
        <CardDescription>
          Источник: {trend.source} • {new Date(trend.published_at).toLocaleDateString()}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-gray-600">{trend.description}</p>
      </CardContent>
      <CardFooter className="flex justify-between">
        <Button 
          onClick={handleGeneratePost}
          disabled={generatePost.isPending}
          className="flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          {generatePost.isPending ? 'Генерация...' : 'Создать пост'}
        </Button>
        
        <Button 
          variant="outline"
          onClick={handleGenerateStory}
          disabled={generateStory.isPending}
          className="flex items-center gap-2"
        >
          <Sparkles className="h-4 w-4" />
          {generateStory.isPending ? 'Генерация...' : 'Создать историю'}
        </Button>
      </CardFooter>
    </Card>
  );
}
```

## Типографика

### Typography Component

```tsx
// components/ui/typography.tsx
import * as React from "react"

interface TypographyProps {
  variant?: 'h1' | 'h2' | 'h3' | 'h4' | 'p' | 'small' | 'muted';
  className?: string;
  children: React.ReactNode;
}

const typographyVariants = {
  h1: "scroll-m-20 text-4xl font-extrabold tracking-tight lg:text-5xl",
  h2: "scroll-m-20 text-3xl font-semibold tracking-tight",
  h3: "scroll-m-20 text-2xl font-semibold tracking-tight",
  h4: "scroll-m-20 text-xl font-semibold tracking-tight",
  p: "leading-7 [&:not(:first-child)]:mt-6",
  small: "text-sm font-medium leading-none",
  muted: "text-sm text-muted-foreground",
};

export function Typography({ variant = 'p', className, children }: TypographyProps) {
  const Component = variant;
  
  return (
    <Component className={`${typographyVariants[variant]} ${className || ''}`}>
      {children}
    </Component>
  );
}
```

### Text Styles

```css
/* styles/typography.css */
.text-display {
  @apply text-5xl font-bold tracking-tight;
}

.text-heading {
  @apply text-3xl font-semibold tracking-tight;
}

.text-subheading {
  @apply text-xl font-medium;
}

.text-body {
  @apply text-base leading-relaxed;
}

.text-caption {
  @apply text-sm text-gray-600;
}

.text-micro {
  @apply text-xs text-gray-500 uppercase tracking-wide;
}
```

## Цвета

### Color Palette

```typescript
// styles/colors.ts
export const colors = {
  primary: {
    50: '#eff6ff',
    100: '#dbeafe',
    200: '#bfdbfe',
    300: '#93c5fd',
    400: '#60a5fa',
    500: '#3b82f6',
    600: '#2563eb',
    700: '#1d4ed8',
    800: '#1e40af',
    900: '#1e3a8a',
  },
  secondary: {
    50: '#f8fafc',
    100: '#f1f5f9',
    200: '#e2e8f0',
    300: '#cbd5e1',
    400: '#94a3b8',
    500: '#64748b',
    600: '#475569',
    700: '#334155',
    800: '#1f2937',
    900: '#0f172a',
  },
  success: {
    50: '#ecfdf5',
    100: '#d1fae5',
    200: '#a7f3d0',
    300: '#6ee7b7',
    400: '#34d399',
    500: '#10b981',
    600: '#059669',
    700: '#047857',
    800: '#065f46',
    900: '#064e3b',
  },
  warning: {
    50: '#fffbeb',
    100: '#fef3c7',
    200: '#fde68a',
    300: '#fcd34d',
    400: '#fbbf24',
    500: '#f59e0b',
    600: '#d97706',
    700: '#b45309',
    800: '#92400e',
    900: '#78350f',
  },
  danger: {
    50: '#fef2f2',
    100: '#fee2e2',
    200: '#fecaca',
    300: '#fca5a5',
    400: '#f87171',
    500: '#ef4444',
    600: '#dc2626',
    700: '#b91c1c',
    800: '#991b1b',
    900: '#7f1d1d',
  },
};
```

### Status Badges

```tsx
// components/ui/status-badge.tsx
import * as React from "react"

interface StatusBadgeProps {
  status: string;
  className?: string;
}

const statusColors = {
  draft: 'bg-gray-100 text-gray-800',
  ready: 'bg-blue-100 text-blue-800',
  approved: 'bg-green-100 text-green-800',
  scheduled: 'bg-yellow-100 text-yellow-800',
  published: 'bg-purple-100 text-purple-800',
  pending: 'bg-orange-100 text-orange-800',
  failed: 'bg-red-100 text-red-800',
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const statusColor = statusColors[status as keyof typeof statusColors] || statusColors.draft;
  
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColor} ${className}`}>
      {status}
    </span>
  );
}
```

## Примеры использования

### Dashboard Page

```tsx
// app/dashboard/page.tsx
'use client';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { usePosts, useTopics, useTrends } from '@/lib/hooks';
import { DataTable } from '@/components/ui/data-table';
import { columns } from './columns';
import { TrendCard } from '@/components/trends/trend-card';
import { Plus } from 'lucide-react';

export default function DashboardPage() {
  const { data: posts } = usePosts();
  const { data: topics } = useTopics();
  const { data: trends } = useTrends();

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Dashboard</h1>
          <p className="text-gray-600">Обзор вашей контент-стратегии</p>
        </div>
        <Button className="flex items-center gap-2">
          <Plus className="h-4 w-4" />
          Новый пост
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Посты</CardTitle>
            <CardDescription>Статистика по постам</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{posts?.length || 0}</div>
            <p className="text-sm text-gray-600">Всего постов</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Темы</CardTitle>
            <CardDescription>Активные темы</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{topics?.length || 0}</div>
            <p className="text-sm text-gray-600">Активных тем</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Тренды</CardTitle>
            <CardDescription>Популярные тренды</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{trends?.length || 0}</div>
            <p className="text-sm text-gray-600">Новых трендов</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Последние посты</CardTitle>
            <CardDescription>Недавно созданные посты</CardDescription>
          </CardHeader>
          <CardContent>
            <DataTable columns={columns} data={posts || []} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Популярные тренды</CardTitle>
            <CardDescription>Тренды для генерации контента</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {trends?.slice(0, 3).map((trend) => (
                <TrendCard key={trend.id} trend={trend} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

### Post Detail Page

```tsx
// app/posts/[id]/page.tsx
'use client';

import { usePost, useGenerateImage, useGenerateVideo } from '@/lib/hooks/use-posts';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { GenerateImageMenu } from '@/components/posts/generate-image-menu';
import { useToast } from '@/components/ui/use-toast';
import { Loader2, Image as ImageIcon, Video } from 'lucide-react';

export default function PostDetailPage({ params }: { params: { id: string } }) {
  const { data: post, isLoading } = usePost(parseInt(params.id));
  const generateImage = useGenerateImage();
  const generateVideo = useGenerateVideo();
  const { toast } = useToast();

  const handleGenerateVideo = async () => {
    try {
      await generateVideo.mutateAsync(parseInt(params.id));
      toast({
        title: 'Успешно',
        description: 'Видео генерируется',
      });
    } catch (error) {
      toast({
        title: 'Ошибка',
        description: 'Не удалось начать генерацию видео',
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (!post) {
    return <div>Пост не найден</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">{post.title}</h1>
          <p className="text-gray-600">{post.client.name}</p>
        </div>
        <div className="flex gap-2">
          <GenerateImageMenu postId={post.id} />
          <Button 
            onClick={handleGenerateVideo}
            disabled={generateVideo.isPending}
            variant="outline"
            className="flex items-center gap-2"
          >
            <Video className="h-4 w-4" />
            {generateVideo.isPending ? 'Генерация...' : 'Сгенерировать видео'}
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Контент</CardTitle>
            <CardDescription>Текст и медиа</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold mb-2">Текст</h3>
              <p className="text-gray-700 whitespace-pre-wrap">{post.text}</p>
            </div>
            
            {post.images.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold mb-2">Изображения</h3>
                <div className="grid grid-cols-2 gap-4">
                  {post.images.map((image) => (
                    <Card key={image.id}>
                      <CardContent className="p-4">
                        <img src={image.image} alt={image.prompt} className="w-full h-48 object-cover rounded" />
                        <p className="text-sm text-gray-600 mt-2">{image.prompt}</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}

            {post.videos.length > 0 && (
              <div>
                <h3 className="text-lg font-semibold mb-2">Видео</h3>
                <div className="grid grid-cols-2 gap-4">
                  {post.videos.map((video) => (
                    <Card key={video.id}>
                      <CardContent className="p-4">
                        <video src={video.video} controls className="w-full h-48 object-cover rounded" />
                        <p className="text-sm text-gray-600 mt-2">{video.prompt}</p>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Информация</CardTitle>
            <CardDescription>Детали поста</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <h4 className="text-sm font-medium text-gray-600">Статус</h4>
              <p className="text-lg">{post.status}</p>
            </div>
            
            <div>
              <h4 className="text-sm font-medium text-gray-600">Теги</h4>
              <div className="flex flex-wrap gap-2 mt-1">
                {post.tags.map((tag) => (
                  <span key={tag} className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-sm">
                    #{tag}
                  </span>
                ))}
              </div>
            </div>
            
            <div>
              <h4 className="text-sm font-medium text-gray-600">Источники</h4>
              <div className="flex flex-wrap gap-2 mt-1">
                {post.source_links.map((link, index) => (
                  <a key={index} href={link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                    Ссылка {index + 1}
                  </a>
                ))}
              </div>
            </div>
            
            <div>
              <h4 className="text-sm font-medium text-gray-600">Дата создания</h4>
              <p className="text-lg">{new Date(post.created_at).toLocaleDateString()}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
```

---

**Далее:**
- [API Integration](./api-integration.md) - API интеграция
- [Authentication](../02-api/telegram-auth.md) - Аутентификация
- [Best Practices](../08-guides/best-practices.md) - Best practices
