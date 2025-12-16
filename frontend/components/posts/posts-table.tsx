'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ApiError, apiFetch } from '@/lib/api';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatTemplateDisplayName } from '@/lib/utils';
import { Loader2 } from 'lucide-react';
import { subscribeToPostGenerationStart } from '@/lib/post-generation-events';

export type Post = {
  id: number;
  title: string;
  hook_title?: string;
  status: string;
  created_at: string;
  platforms: string[];
  template_name?: string | null;
};

type PostPlaceholder = {
  id: string;
  templateName?: string;
  createdAt: string;
};

const STATUS_OPTIONS = [
  { value: '', label: 'Все статусы' },
  { value: 'draft', label: 'Черновики' },
  { value: 'approved', label: 'Одобрено' },
  { value: 'scheduled', label: 'Запланировано' },
  { value: 'published', label: 'Опубликовано' }
];

const PLATFORM_OPTIONS = [
  { value: '', label: 'Все платформы' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'telegram', label: 'Telegram' },
  { value: 'youtube', label: 'YouTube' },
  { value: 'vkontakte', label: 'VKontakte' }
];

export function PostsTable() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [placeholders, setPlaceholders] = useState<PostPlaceholder[]>([]);
  const lastPostIdsRef = useRef<Set<number>>(new Set());

  const status = searchParams.get('status') || '';
  const platform = searchParams.get('platform') || '';

  const loadPosts = useCallback(
    async ({ showLoading = true }: { showLoading?: boolean } = {}) => {
      if (showLoading) {
        setLoading(true);
      }
      setError(null);
      try {
        const params = new URLSearchParams();
        if (status) params.set('status', status);
        if (platform) params.set('platform', platform);

        const query = params.toString();
        const data = await apiFetch<Post[]>(`/posts/${query ? `?${query}` : ''}`);
        const previousIds = new Set(lastPostIdsRef.current);
        setPosts(data);

        const newPostCount = data.filter((post) => !previousIds.has(post.id)).length;
        lastPostIdsRef.current = new Set(data.map((post) => post.id));

        if (newPostCount > 0) {
          setPlaceholders((prev) => {
            if (prev.length === 0) {
              return prev;
            }
            const removeCount = Math.min(prev.length, newPostCount);
            return prev.slice(removeCount);
          });
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.push('/login');
        } else {
          setError('Не удалось загрузить посты');
        }
      } finally {
        if (showLoading) {
          setLoading(false);
        }
      }
    },
    [platform, router, status]
  );

  useEffect(() => {
    loadPosts();
  }, [loadPosts]);

  useEffect(() => {
    const unsubscribe = subscribeToPostGenerationStart(({ count, templateName }) => {
      const parsedCount = typeof count === 'number' ? count : Number(count);
      const safeCount =
        Number.isFinite(parsedCount) && parsedCount ? Math.max(1, Math.floor(parsedCount)) : 1;
      const createdAt = new Date().toISOString();
      const newPlaceholders: PostPlaceholder[] = Array.from({ length: safeCount }, (_, index) => ({
        id: `placeholder-${createdAt}-${index}-${Math.random().toString(36).slice(2, 8)}`,
        templateName,
        createdAt,
      }));
      setPlaceholders((prev) => [...prev, ...newPlaceholders]);
    });

    return unsubscribe;
  }, []);

  useEffect(() => {
    if (placeholders.length === 0) {
      return;
    }

    loadPosts({ showLoading: false });
    const intervalId = setInterval(() => {
      loadPosts({ showLoading: false });
    }, 5000);

    return () => {
      clearInterval(intervalId);
    };
  }, [placeholders.length, loadPosts]);

  const updateQuery = (key: string, value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    const query = params.toString();
    router.push(`/posts${query ? `?${query}` : ''}`);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Select value={status || 'all'} onValueChange={(v) => updateQuery('status', v === 'all' ? '' : v)}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Статус" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value || 'all'} value={option.value || 'all'}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={platform || 'all'} onValueChange={(v) => updateQuery('platform', v === 'all' ? '' : v)}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Платформа" />
          </SelectTrigger>
          <SelectContent>
            {PLATFORM_OPTIONS.map((option) => (
              <SelectItem key={option.value || 'all'} value={option.value || 'all'}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {error && <div className="text-sm text-destructive">{error}</div>}
      {loading && <div>Загрузка...</div>}

      {!loading && posts.length === 0 && placeholders.length === 0 && (
        <div className="text-sm text-muted-foreground">Постов пока нет.</div>
      )}

      {!loading && (posts.length > 0 || placeholders.length > 0) && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Заголовок</TableHead>
              <TableHead>Тип поста</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {placeholders.map((placeholder) => (
              <TableRow key={placeholder.id}>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Новый пост создается
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {placeholder.templateName || 'Тип уточняется'}
                </TableCell>
              </TableRow>
            ))}
            {posts.map((post) => (
              <TableRow key={post.id}>
                <TableCell className="font-medium">
                  <a
                    href={`/posts/${post.id}`}
                    className="text-primary hover:underline"
                  >
                    {post.title || `Пост #${post.id}`}
                  </a>
                  <div className="text-sm text-muted-foreground mt-1">
                    <span className="font-semibold">Цепляющий заголовок:</span>{' '}
                    {post.hook_title?.trim() || 'не сгенерирован'}
                  </div>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {formatTemplateDisplayName(post.template_name) || 'Без шаблона'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
