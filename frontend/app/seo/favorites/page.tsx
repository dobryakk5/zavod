'use client';

import { Fragment, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ChevronDown, ChevronRight, Loader2, ThumbsDown, ThumbsUp } from 'lucide-react';
import { toast } from 'sonner';
import { wordstatApi } from '@/lib/api/wordstat';
import { articlesApi } from '@/lib/api/articles';
import { ApiError } from '@/lib/api';
import type { WordstatCluster, WordstatQuery, WordstatResultType } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

type FavoriteRow = {
  id: number;
  phrase: string;
  count: number;
  queryId: number;
  result_type: WordstatResultType;
  clusterId?: number | null;
  clusterName?: string | null;
};

export default function WordstatFavoritesPage() {
  const router = useRouter();
  const [queries, setQueries] = useState<WordstatQuery[]>([]);
  const [clusters, setClusters] = useState<WordstatCluster[]>([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [creatingArticle, setCreatingArticle] = useState<string | null>(null);
  const [clusterizing, setClusterizing] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState<Record<string, boolean>>({});

  const clusterNameById = useMemo(() => {
    const map = new Map<number, string>();
    clusters.forEach((cluster) => {
      map.set(cluster.id, cluster.name);
    });
    return map;
  }, [clusters]);

  const clusterOptions = useMemo(() => [{ id: null, name: 'Без кластера' }, ...clusters], [clusters]);

  const formatClusterLabel = (name?: string | null) => {
    const base = (name || 'Без кластера').trim();
    return `${base.slice(0, 5)}...`;
  };

  const load = async () => {
    setLoading(true);
    try {
      const [queriesResult, clustersResult] = await Promise.allSettled([wordstatApi.list(), wordstatApi.listClusters()]);
      if (queriesResult.status === 'fulfilled') {
        setQueries(queriesResult.value);
      } else {
        setQueries([]);
        toast.error('Не удалось загрузить Wordstat');
      }
      if (clustersResult.status === 'fulfilled') {
        setClusters(clustersResult.value);
      } else {
        setClusters([]);
      }
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
        .forEach((r) =>
          rows.push({
            id: r.id,
            phrase: r.phrase,
            count: r.count,
            queryId: q.id,
            result_type: r.result_type,
            clusterId: r.cluster ?? null,
            clusterName: r.cluster_name ?? null,
          })
        );
    });
    return rows.sort((a, b) => b.count - a.count || a.phrase.localeCompare(b.phrase));
  }, [queries]);

  const hasClusters = clusters.length > 0;

  const groupedFavorites = useMemo(() => {
    if (!favorites.length) return [];
    const rowsByCluster = new Map<number, FavoriteRow[]>();
    const unclustered: FavoriteRow[] = [];
    const clusterNames = new Map(clusters.map((cluster) => [cluster.id, cluster.name]));

    favorites.forEach((row) => {
      if (row.clusterId) {
        if (!rowsByCluster.has(row.clusterId)) rowsByCluster.set(row.clusterId, []);
        rowsByCluster.get(row.clusterId)!.push(row);
        return;
      }
      unclustered.push(row);
    });

    const grouped: Array<{ key: string; title: string; rows: FavoriteRow[]; total: number }> = [];
    rowsByCluster.forEach((rows, clusterId) => {
      const total = rows.reduce((sum, row) => sum + row.count, 0);
      grouped.push({
        key: `cluster-${clusterId}`,
        title: clusterNames.get(clusterId) || `Кластер #${clusterId}`,
        rows,
        total,
      });
    });

    const unclusteredGroup = unclustered.length
      ? {
          key: 'unclustered',
          title: 'Без кластера',
          rows: unclustered,
          total: unclustered.reduce((sum, row) => sum + row.count, 0),
        }
      : null;

    grouped.sort((a, b) => b.total - a.total);

    if (grouped.length) {
      return unclusteredGroup ? [...grouped, unclusteredGroup] : grouped;
    }

    return [
      unclusteredGroup || {
        key: 'unclustered',
        title: 'Без кластера',
        rows: favorites,
        total: favorites.reduce((sum, row) => sum + row.count, 0),
      },
    ];
  }, [clusters, favorites]);

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

  const handleClusterChange = async (resultId: number, clusterId: number | null) => {
    setUpdating(true);
    const clusterName = clusterId ? clusterNameById.get(clusterId) || null : null;
    setQueries((prev) =>
      prev.map((q) => ({
        ...q,
        results: q.results.map((r) => (r.id === resultId ? { ...r, cluster: clusterId, cluster_name: clusterName } : r)),
      }))
    );
    try {
      await wordstatApi.updateCluster(resultId, clusterId);
    } catch (error) {
      console.error('Failed to update Wordstat cluster', error);
      toast.error('Не удалось обновить кластер');
      load();
    } finally {
      setUpdating(false);
    }
  };

  const renderClusterDropdown = (row: FavoriteRow) => (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs text-slate-600 transition hover:text-slate-900"
          disabled={updating}
          title={row.clusterName || 'Без кластера'}
          aria-label="Выбрать кластер"
        >
          {formatClusterLabel(row.clusterName)}
          <ChevronDown className="h-3 w-3" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent
        align="end"
        className="border-slate-200 bg-white text-slate-900 dark:border-slate-200 dark:bg-white dark:text-slate-900"
      >
        <DropdownMenuRadioGroup
          value={row.clusterId ? String(row.clusterId) : 'none'}
          onValueChange={(value) => handleClusterChange(row.id, value === 'none' ? null : Number.parseInt(value, 10))}
        >
          {clusterOptions.map((option) => (
            <DropdownMenuRadioItem
              key={option.id ?? 'none'}
              value={option.id ? String(option.id) : 'none'}
              className="text-slate-900 focus:bg-slate-100 focus:text-slate-900 dark:text-slate-900 dark:focus:bg-slate-100 dark:focus:text-slate-900"
            >
              {option.name}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );

  const toggleGroup = (groupKey: string) => {
    setExpandedGroups((prev) => ({ ...prev, [groupKey]: !prev[groupKey] }));
  };

  const handleClusterize = async () => {
    if (!favorites.length) return;
    setClusterizing(true);
    try {
      await wordstatApi.clusterFavorites();
      toast.success('Кластеры обновлены');
      await load();
    } catch (error) {
      console.error('Failed to cluster Wordstat favorites', error);
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
      toast.error('Не удалось кластеризовать фразы');
    } finally {
      setClusterizing(false);
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
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Избранные фразы</CardTitle>
            <Button
              onClick={() => void handleClusterize()}
              disabled={loading || clusterizing || favorites.length === 0}
            >
              {clusterizing ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Кластеризуем...
                </span>
              ) : (
                'Кластеризовать'
              )}
            </Button>
          </div>
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
                  <TableHead className="w-[45%]">Фраза</TableHead>
                  <TableHead className="w-[10%] text-right">Кластер</TableHead>
                  <TableHead className="w-[25%] text-right">Действия</TableHead>
                  <TableHead className="w-[20%] text-right">Показов</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {hasClusters
                  ? groupedFavorites.map((group) => {
                      const isExpanded = Boolean(expandedGroups[group.key]);
                      return (
                        <Fragment key={group.key}>
                          <TableRow>
                            <TableCell colSpan={4} className="bg-slate-50 p-0">
                              <button
                                type="button"
                                onClick={() => toggleGroup(group.key)}
                                aria-expanded={isExpanded}
                                className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold text-slate-700"
                              >
                                <span className="inline-flex items-center gap-2">
                                  {isExpanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                                  {group.title}
                                </span>
                                <span className="text-[11px] text-slate-500">
                                  {group.total.toLocaleString('ru-RU')} показов
                                </span>
                              </button>
                            </TableCell>
                          </TableRow>
                          {isExpanded
                            ? group.rows.map((row) => (
                                <TableRow key={row.id}>
                                  <TableCell className="text-emerald-700">{row.phrase}</TableCell>
                                  <TableCell className="text-right">{renderClusterDropdown(row)}</TableCell>
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
                                </TableRow>
                              ))
                            : null}
                        </Fragment>
                      );
                    })
                  : favorites.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell className="text-emerald-700">{row.phrase}</TableCell>
                        <TableCell className="text-right">{renderClusterDropdown(row)}</TableCell>
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
