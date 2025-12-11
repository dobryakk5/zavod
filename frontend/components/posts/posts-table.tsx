'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ApiError, apiFetch } from '@/lib/api';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { formatTemplateDisplayName } from '@/lib/utils';

export type Post = {
  id: number;
  title: string;
  status: string;
  created_at: string;
  platforms: string[];
  template_name?: string | null;
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
  { value: 'youtube', label: 'YouTube' }
];

export function PostsTable() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const status = searchParams.get('status') || '';
  const platform = searchParams.get('platform') || '';

  useEffect(() => {
    const loadPosts = async () => {
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (status) params.set('status', status);
        if (platform) params.set('platform', platform);

        const query = params.toString();
        const data = await apiFetch<Post[]>(`/posts/${query ? `?${query}` : ''}`);
        setPosts(data);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          router.push('/login');
        } else {
          setError('Не удалось загрузить посты');
        }
      } finally {
        setLoading(false);
      }
    };

    loadPosts();
  }, [platform, router, status]);

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

      {!loading && posts.length === 0 && <div className="text-sm text-muted-foreground">Постов пока нет.</div>}

      {!loading && posts.length > 0 && (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Заголовок</TableHead>
              <TableHead>Тип поста</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {posts.map((post) => (
              <TableRow key={post.id}>
                <TableCell className="font-medium">
                  <a
                    href={`/posts/${post.id}`}
                    className="text-primary hover:underline"
                  >
                    {post.title || `Пост #${post.id}`}
                  </a>
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
