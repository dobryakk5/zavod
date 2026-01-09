'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import type { Article, ArticleStatus } from '@/lib/types';
import { ApiError } from '@/lib/api';
import { articlesApi } from '@/lib/api/articles';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';

const STATUS_LABELS: Record<ArticleStatus, string> = {
  draft: 'Черновик',
  options_ready: 'Выбор вариантов',
  outline_ready: 'Скелет готов',
  failed: 'Ошибка',
};

const STATUS_STYLES: Record<ArticleStatus, string> = {
  draft: 'bg-slate-100 text-slate-700',
  options_ready: 'bg-blue-100 text-blue-800',
  outline_ready: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-red-100 text-red-800',
};

function formatDate(value?: string | null) {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function parsePhrases(raw: string): string[] {
  return raw
    .replace(/\r/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

function StatusBadge({ status }: { status: ArticleStatus }) {
  return (
    <Badge className={`${STATUS_STYLES[status] ?? ''} text-xs font-medium`}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export default function ArticlesPageClient() {
  const router = useRouter();
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [wordstatRaw, setWordstatRaw] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const data = await articlesApi.list();
      setArticles(data);
    } catch (error) {
      console.error('Failed to load articles', error);
      toast.error('Не удалось загрузить статьи');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const firstPhrase = useMemo(() => parsePhrases(wordstatRaw)[0] || '', [wordstatRaw]);

  const onStart = async () => {
    const phrases = parsePhrases(wordstatRaw);
    if (!phrases.length) {
      toast.error('Введите Wordstat фразы (одна строка — одна фраза)');
      return;
    }
    setStarting(true);
    try {
      const created = await articlesApi.start(phrases[0]);
      try {
        await articlesApi.generateContext(created.id);
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          router.push('/login');
          return;
        }
        let messageShown = false;
        if (error instanceof ApiError) {
          try {
            const parsed = JSON.parse(error.body || '{}') as { error?: string };
            if (parsed.error) {
              toast.error(parsed.error);
              messageShown = true;
            }
          } catch {
            // ignore parse errors
          }
        }
        console.error('Failed to generate article context', error);
        if (!messageShown) {
          toast.error('Не удалось сгенерировать контекст');
        }
      }
      router.push(`/articles/${created.id}`);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        router.push('/login');
        return;
      }
      if (error instanceof ApiError) {
        try {
          const parsed = JSON.parse(error.body || '{}') as { error?: string };
          if (parsed.error) {
            toast.error(parsed.error);
            return;
          }
        } catch {
          // ignore parse errors
        }
      }
      console.error('Failed to start article', error);
      toast.error('Не удалось запустить создание статьи');
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Статьи</h1>

      <div className="space-y-2">
        <Textarea
          value={wordstatRaw}
          onChange={(e) => setWordstatRaw(e.target.value)}
          placeholder="Wordstat фразы (одна строка — одна фраза)"
          className="min-h-28"
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={onStart} disabled={starting || !firstPhrase}>
            {starting ? 'Генерируем варианты…' : 'Начать'}
          </Button>
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            Обновить
          </Button>
          {parsePhrases(wordstatRaw).length > 1 ? (
            <div className="text-sm text-muted-foreground">
              Сейчас запускается только первая фраза из списка.
            </div>
          ) : null}
        </div>
      </div>

      {loading ? <div>Загрузка…</div> : null}

      {!loading && articles.length === 0 ? (
        <div className="text-sm text-muted-foreground">Статей пока нет.</div>
      ) : null}

      {!loading && articles.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Wordstat</TableHead>
              <TableHead className="w-44">Дата</TableHead>
              <TableHead className="w-44">Статус</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {articles.map((article) => (
              <TableRow key={article.id}>
                <TableCell className="font-medium">
                  <Link href={`/articles/${article.id}`} className="text-primary hover:underline">
                    {article.wordstat}
                  </Link>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{formatDate(article.created_at)}</TableCell>
                <TableCell>
                  <StatusBadge status={article.status} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : null}
    </div>
  );
}
