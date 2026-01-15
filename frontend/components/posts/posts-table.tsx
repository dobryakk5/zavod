'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ApiError, apiFetch } from '@/lib/api';
import type { PaginatedResponse } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatTemplateDisplayName } from '@/lib/utils';
import { Clapperboard, Image as ImageIcon, Loader2 } from 'lucide-react';
import { subscribeToPostGenerationComplete, subscribeToPostGenerationStart } from '@/lib/post-generation-events';

export type Post = {
  id: number;
  title: string;
  hook_title?: string;
  status: string;
  created_at: string;
  platforms: string[];
  template_name?: string | null;
  has_images?: boolean;
  has_videos?: boolean;
  next_scheduled_at?: string | null;
};

type PostPlaceholder = {
  id: string;
  templateName?: string;
  createdAt: string;
};

const PAGE_SIZE = 25;

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
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [placeholders, setPlaceholders] = useState<PostPlaceholder[]>([]);
  const lastPostIdsRef = useRef<Set<number>>(new Set());

  const status = searchParams.get('status') || '';
  const platform = searchParams.get('platform') || '';
  const pageParam = searchParams.get('page');
  const parsedPage = pageParam ? Number(pageParam) : 1;
  const currentPage = Number.isFinite(parsedPage) && parsedPage > 0 ? Math.floor(parsedPage) : 1;

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
        params.set('page', currentPage.toString());
        params.set('page_size', PAGE_SIZE.toString());

        const query = params.toString();
        const data = await apiFetch<PaginatedResponse<Post>>(`/posts/${query ? `?${query}` : ''}`);
        setTotalCount(data.count);
        setPosts(data.results);

        if (currentPage === 1) {
          const previousIds = new Set(lastPostIdsRef.current);
          const newPostCount = data.results.filter((post) => !previousIds.has(post.id)).length;
          lastPostIdsRef.current = new Set(data.results.map((post) => post.id));

          if (newPostCount > 0) {
            setPlaceholders((prev) => {
              if (prev.length === 0) {
                return prev;
              }
              const removeCount = Math.min(prev.length, newPostCount);
              return prev.slice(removeCount);
            });
          }
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
    [currentPage, platform, router, status]
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
    const unsubscribe = subscribeToPostGenerationComplete(({ count }) => {
      const parsedCount = typeof count === 'number' ? count : Number(count);
      const safeCount = Number.isFinite(parsedCount) && parsedCount > 0 ? Math.floor(parsedCount) : 0;

      setPlaceholders((prev) => {
        if (prev.length === 0) {
          return prev;
        }
        if (!safeCount) {
          return [];
        }
        const removeCount = Math.min(prev.length, safeCount);
        return prev.slice(removeCount);
      });

      if (currentPage === 1) {
        loadPosts({ showLoading: false });
      }
    });

    return unsubscribe;
  }, [currentPage, loadPosts]);

  useEffect(() => {
    if (placeholders.length === 0 || currentPage !== 1) {
      return;
    }

    loadPosts({ showLoading: false });
    const intervalId = setInterval(() => {
      loadPosts({ showLoading: false });
    }, 5000);

    return () => {
      clearInterval(intervalId);
    };
  }, [currentPage, placeholders.length, loadPosts]);

  const updateQuery = useCallback((key: string, value: string, options?: { resetPage?: boolean }) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set(key, value);
    } else {
      params.delete(key);
    }
    if (options?.resetPage) {
      params.delete('page');
    }
    if (key === 'page' && value === '1') {
      params.delete('page');
    }
    const query = params.toString();
    router.push(`/posts${query ? `?${query}` : ''}`);
  }, [router, searchParams]);

  useEffect(() => {
    if (!totalCount) {
      return;
    }
    const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
    if (currentPage > totalPages) {
      updateQuery('page', totalPages.toString());
    }
  }, [currentPage, totalCount, updateQuery]);

  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  const rangeStart = totalCount === 0 ? 0 : (currentPage - 1) * PAGE_SIZE + 1;
  const rangeEnd = totalCount === 0 ? 0 : Math.min(currentPage * PAGE_SIZE, totalCount);
  const visiblePlaceholders = currentPage === 1 ? placeholders : [];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Select
          value={status || 'all'}
          onValueChange={(v) => updateQuery('status', v === 'all' ? '' : v, { resetPage: true })}
        >
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

        <Select
          value={platform || 'all'}
          onValueChange={(v) => updateQuery('platform', v === 'all' ? '' : v, { resetPage: true })}
        >
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

      {!loading && posts.length === 0 && visiblePlaceholders.length === 0 && (
        <div className="text-sm text-muted-foreground">Постов пока нет.</div>
      )}

      {!loading && (posts.length > 0 || visiblePlaceholders.length > 0) && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Заголовок</TableHead>
              <TableHead className="w-36">Медиа</TableHead>
              <TableHead>Тип поста</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {visiblePlaceholders.map((placeholder) => (
              <TableRow key={placeholder.id}>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Новый пост создается
                  </div>
                </TableCell>
                <TableCell />
                <TableCell className="text-sm text-muted-foreground">
                  {placeholder.templateName || 'Тип уточняется'}
                </TableCell>
              </TableRow>
            ))}
            {posts.map((post) => {
              const scheduledAt = post.next_scheduled_at ? new Date(post.next_scheduled_at) : null;
              const scheduledLabel = scheduledAt
                ? scheduledAt.toLocaleString('ru-RU', {
                  day: '2-digit',
                  month: '2-digit',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit',
                })
                : 'не запланировано';

              return (
                <TableRow key={post.id}>
                  <TableCell className="font-medium">
                    <a
                      href={`/posts/${post.id}`}
                      className="text-primary hover:underline"
                    >
                      {post.title || `Пост #${post.id}`}
                    </a>
                    <div className="text-sm text-muted-foreground mt-1">
                      <span className="font-semibold">Запланировано на:</span>{' '}
                      {scheduledLabel}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {post.has_images ? (
                        <div
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-amber-50 text-amber-700 ring-1 ring-amber-100"
                          title="Есть фото"
                        >
                          <ImageIcon className="h-4 w-4" aria-hidden="true" />
                          <span className="sr-only">Есть фото</span>
                        </div>
                      ) : null}
                      {post.has_videos ? (
                        <div
                          className="inline-flex h-8 w-8 items-center justify-center rounded-md bg-sky-50 text-sky-700 ring-1 ring-sky-100"
                          title="Есть видео"
                        >
                          <Clapperboard className="h-4 w-4" aria-hidden="true" />
                          <span className="sr-only">Есть видео</span>
                        </div>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {formatTemplateDisplayName(post.template_name) || 'Без шаблона'}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      {totalPages > 1 && (
        <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
          <div className="text-muted-foreground">
            Показано {rangeStart}-{rangeEnd} из {totalCount}
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage <= 1}
              onClick={() => updateQuery('page', (currentPage - 1).toString())}
            >
              Назад
            </Button>
            <span className="text-muted-foreground">
              Страница {currentPage} из {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages}
              onClick={() => updateQuery('page', (currentPage + 1).toString())}
            >
              Вперед
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
