'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, Loader2, ThumbsDown, ThumbsUp } from 'lucide-react';
import { toast } from 'sonner';
import { wordstatApi } from '@/lib/api/wordstat';
import { articlesApi } from '@/lib/api/articles';
import { ApiError } from '@/lib/api';
import type { WordstatQuery, WordstatResultType } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';

type FavoriteRow = {
  id: number;
  phrase: string;
  count: number;
  queryId: number;
  queryPhrase: string;
  result_type: WordstatResultType;
};

export default function WordstatFavoritesPage() {
  const router = useRouter();
  const [queries, setQueries] = useState<WordstatQuery[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [creatingArticle, setCreatingArticle] = useState<string | null>(null);

  const getQueryLabel = (query: WordstatQuery): string => {
    if ((query.group_name || '').trim()) {
      return query.group_name || '';
    }
    if (Array.isArray(query.phrases) && query.phrases.length) {
      if (query.phrases.length > 1) {
        return `${query.phrases[0]} (+${query.phrases.length - 1})`;
      }
      return query.phrases[0] || '';
    }
    return query.request_phrase || '';
  };

  const load = async () => {
    setLoading(true);
    try {
      const data = await wordstatApi.list();
      setQueries(data);
    } catch (error) {
      console.error('Failed to load Wordstat favorites', error);
      toast.error('Не удалось загрузить Wordstat');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const favorites = useMemo<FavoriteRow[]>(() => {
    const rows: FavoriteRow[] = [];
    queries.forEach((q) => {
      q.results
        .filter((r) => r.result_type === 'favorite')
        .forEach((r) => rows.push({ id: r.id, phrase: r.phrase, count: r.count, queryId: q.id, queryPhrase: getQueryLabel(q), result_type: r.result_type }));
    });
    return rows.sort((a, b) => b.count - a.count || a.phrase.localeCompare(b.phrase));
  }, [queries]);

  const handleResultTypeChange = async (resultId: number, result_type: WordstatResultType) => {
    setUpdating(true);
    setQueries((prev) =>
      prev.map((q) => ({
        ...q,
        results: q.results.map((r) => (r.id === resultId ? { ...r, result_type } : r)),
      }))
    );
    try {
      await wordstatApi.updateResultType(resultId, result_type);
    } catch (error) {
      console.error('Failed to update Wordstat result type', error);
      toast.error('Не удалось обновить метку фразы');
      load();
    } finally {
      setUpdating(false);
    }
  };

  const handleGoogleSearch = (phrase: string) => {
    const q = (phrase || '').trim();
    if (!q) return;
    const params = new URLSearchParams();
    params.set('tab', 'competitors');
    params.set('q', q);
    params.set('save', '1');
    router.push(`/seo?${params.toString()}`);
  };

  const handleCreateArticle = async (phrase: string) => {
    const q = (phrase || '').trim();
    if (!q) return;
    setCreatingArticle(q);
    try {
      const created = await articlesApi.start(q);
      router.push(`/articles/${created.id}`);
    } catch (error) {
      console.error('Failed to create article from favorite phrase', error);
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
      toast.error('Не удалось создать статью по фразе');
    } finally {
      setCreatingArticle(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" onClick={() => router.push('/seo')} className="p-2">
          <ArrowLeft className="h-8 w-8" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Избранное Wordstat</h1>
          <p className="text-muted-foreground">Все фразы, отмеченные как избранные</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Избранные фразы</CardTitle>
          <CardDescription>{favorites.length ? `${favorites.length} фраз` : 'Нет отмеченных избранных фраз'}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем данные...
            </div>
          ) : favorites.length === 0 ? (
            <p className="text-sm text-muted-foreground">Пока нет избранных фраз.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-2/5">Фраза</TableHead>
                  <TableHead className="w-1/5 text-right">Действия</TableHead>
                  <TableHead className="w-1/5 text-right">Показов</TableHead>
                  <TableHead className="w-1/5 text-right">Запрос</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {favorites.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="text-emerald-700">{row.phrase}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <button
                          type="button"
                          onClick={() => handleResultTypeChange(row.id, 'favorite')}
                          className={`rounded-md p-2 transition ${
                            row.result_type === 'favorite' ? 'text-emerald-700' : 'text-slate-600 hover:text-emerald-700'
                          } ${updating ? 'opacity-70' : ''}`}
                          aria-label="Добавить в избранное"
                        >
                          <ThumbsUp className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleResultTypeChange(row.id, 'skip')}
                          className={`rounded-md p-2 transition ${
                            row.result_type === 'skip' ? 'text-slate-400' : 'text-slate-600 hover:text-slate-400'
                          } ${updating ? 'opacity-70' : ''}`}
                          aria-label="Отметить как мимо"
                        >
                          <ThumbsDown className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleGoogleSearch(row.phrase)}
                          className="rounded-md p-2 text-slate-600 transition hover:text-slate-900"
                          title="Google search"
                          aria-label="Google search"
                        >
                          <span className="text-[13px] font-semibold leading-none">G</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleCreateArticle(row.phrase)}
                          disabled={Boolean(creatingArticle)}
                          className={`rounded-md p-2 text-slate-600 transition hover:text-slate-900 ${
                            creatingArticle ? 'opacity-70' : ''
                          }`}
                          title="Создать статью"
                          aria-label="Создать статью"
                        >
                          <span className="inline-flex items-center gap-1 text-[13px] font-semibold leading-none">
                            Т
                            {creatingArticle === row.phrase ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                          </span>
                        </button>
                      </div>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{row.count.toLocaleString('ru-RU')}</TableCell>
                    <TableCell className="text-right">
                      <Badge variant="outline" className="text-xs">
                        {row.queryPhrase}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
