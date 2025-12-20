'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Loader2, ArrowLeft, ThumbsDown, ThumbsUp } from 'lucide-react';
import { toast } from 'sonner';
import { wordstatApi } from '@/lib/api/wordstat';
import type { WordstatQuery, WordstatResultType } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';

export default function WordstatDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [query, setQuery] = useState<WordstatQuery | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [filterType, setFilterType] = useState<WordstatResultType | 'all'>('all');
  const [phraseDraft, setPhraseDraft] = useState<string>('');

  const loadQuery = async () => {
    if (!params?.id) return;
    setLoading(true);
    try {
      const data = await wordstatApi.get(params.id);
      setQuery(data);
      setPhraseDraft(data.request_phrase || '');
    } catch (error) {
      console.error('Failed to load Wordstat query', error);
      toast.error('Не удалось загрузить данные Wordstat');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQuery();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params?.id]);

  const counts = useMemo(() => {
    if (!query) return { total: 0, favorites: 0, skipped: 0, requests: 0, associations: 0 };
    return {
      total: query.results.length,
      favorites: query.results.filter((r) => r.result_type === 'favorite').length,
      skipped: query.results.filter((r) => r.result_type === 'skip').length,
      requests: query.results.filter((r) => r.result_type === 'top_request').length,
      associations: query.results.filter((r) => r.result_type === 'association').length,
    };
  }, [query]);

  const filteredResults = useMemo(() => {
    if (!query) return [];
    if (filterType === 'all') return query.results;
    return query.results.filter((r) => r.result_type === filterType);
  }, [filterType, query]);

  const resultTypeLabel = (type: WordstatResultType) => {
    switch (type) {
      case 'association':
        return 'Ассоциация';
      case 'favorite':
        return 'Избранное';
      case 'skip':
        return 'Мимо';
      default:
        return 'Запрос';
    }
  };

  const handleRepeat = async () => {
    const phrase = phraseDraft.trim();
    if (!phrase) {
      toast.error('Введите фразу для запроса Wordstat');
      return;
    }
    setUpdating(true);
    try {
      const data = await wordstatApi.fetch({ phrase });
      setQuery(data);
      setPhraseDraft(data.request_phrase || phrase);
      if (data.id) {
        router.push(`/seo/${data.id}`);
      }
    } catch (error) {
      console.error('Failed to repeat Wordstat query', error);
      toast.error('Не удалось выполнить запрос Wordstat');
    } finally {
      setUpdating(false);
    }
  };

  const handleResultTypeChange = async (resultId: number, result_type: WordstatResultType) => {
    if (!query) return;
    setUpdating(true);
    setQuery((prev) =>
      prev
        ? {
            ...prev,
            results: prev.results.map((r) => (r.id === resultId ? { ...r, result_type } : r)),
          }
        : prev
    );
    try {
      await wordstatApi.updateResultType(resultId, result_type);
    } catch (error) {
      console.error('Failed to update Wordstat result type', error);
      toast.error('Не удалось обновить метку фразы');
      loadQuery();
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" onClick={() => router.push('/seo')} className="p-2">
          <ArrowLeft className="h-8 w-8" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">Wordstat</h1>
          <p className="text-muted-foreground">Запросы и частотности из Яндекс Wordstat</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Wordstat запрос</CardTitle>
          <CardDescription>
            {query ? `Создано: ${new Date(query.created_at).toLocaleString('ru-RU')}` : 'Пожалуйста, подождите'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем данные...
            </div>
          ) : !query ? (
            <p className="text-sm text-muted-foreground">Данные недоступны</p>
          ) : (
            <>
              <div className="flex flex-col gap-2">
                <Input
                  value={phraseDraft}
                  onChange={(e) => setPhraseDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleRepeat();
                    }
                  }}
                />
                <Button variant="outline" onClick={handleRepeat} disabled={updating} className="w-fit">
                  {updating ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Запрос...
                    </>
                  ) : (
                    'Повторить Wordstat'
                  )}
                </Button>
              </div>
              <div className="flex flex-wrap gap-2 text-sm">
                <Badge
                  variant={filterType === 'all' ? 'secondary' : 'outline'}
                  className="text-xs cursor-pointer"
                  onClick={() => setFilterType('all')}
                >
                  Все: {counts.total}
                </Badge>
                <Badge
                  variant={filterType === 'top_request' ? 'secondary' : 'outline'}
                  className="text-xs cursor-pointer"
                  onClick={() => setFilterType('top_request')}
                >
                  Запросы: {counts.requests}
                </Badge>
                <Badge
                  variant={filterType === 'association' ? 'secondary' : 'outline'}
                  className="text-xs cursor-pointer"
                  onClick={() => setFilterType('association')}
                >
                  Ассоциации: {counts.associations}
                </Badge>
                <Badge
                  variant={filterType === 'favorite' ? 'secondary' : 'outline'}
                  className="text-xs cursor-pointer"
                  onClick={() => setFilterType('favorite')}
                >
                  Избранное: {counts.favorites}
                </Badge>
                <Badge
                  variant={filterType === 'skip' ? 'secondary' : 'outline'}
                  className="text-xs cursor-pointer"
                  onClick={() => setFilterType('skip')}
                >
                  Мимо: {counts.skipped}
                </Badge>
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-1/2">Фраза</TableHead>
                    <TableHead className="w-28 text-right">Действия</TableHead>
                    <TableHead className="w-1/6 text-right">Показов</TableHead>
                    <TableHead className="w-1/6 text-right">Тип</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredResults.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell
                        className={`${
                          row.result_type === 'skip'
                            ? 'text-slate-400'
                            : row.result_type === 'favorite'
                              ? 'text-emerald-700'
                              : ''
                        }`}
                      >
                        {row.phrase}
                      </TableCell>
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
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{row.count.toLocaleString('ru-RU')}</TableCell>
                      <TableCell className="text-right">
                        <Badge variant="outline" className="text-xs">
                          {row.result_type === 'association'
                            ? 'Ассоциация'
                            : row.result_type === 'favorite'
                              ? 'Избранное'
                              : row.result_type === 'skip'
                                ? 'Мимо'
                                : 'Запрос'}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
