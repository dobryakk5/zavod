'use client';

import { useEffect, useMemo, useState } from 'react';
import { Loader2, RefreshCw, Search } from 'lucide-react';
import { toast } from 'sonner';
import { seoApi } from '@/lib/api/seo';
import { wordstatApi } from '@/lib/api/wordstat';
import type { SEOKeywordSet, SEOStatus, WordstatQuery } from '@/lib/types';
import { useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';

const GROUP_LABELS: Record<string, string> = {
  seo_keywords: 'SEO ключевые фразы',
  seo_pains: 'Боли аудитории',
  seo_desires: 'Желания аудитории',
  seo_objections: 'Возражения и страхи',
  seo_avatar: 'Аватары клиентов',
  legacy: 'Другие группы',
  '': 'Неразмеченная группа',
};

const GROUP_DESCRIPTIONS: Record<string, string> = {
  seo_keywords: 'Готовые низко- и среднечастотные поисковые запросы для текстов и рилс.',
  seo_pains: 'Фразы, которыми описывают свои проблемы потенциальные клиенты.',
  seo_desires: 'Что пользователи ищут, когда хотят получить ваш продукт/услугу.',
  seo_objections: 'Чего боятся и какие вопросы задают перед покупкой.',
  seo_avatar: 'Самоописания и профессии целевой аудитории.',
  legacy: 'Исторические подборки, созданные в ранних версиях конструктора.',
  '': 'Подборка без указанного типа (наследие ранних версий).',
};

const STATUS_LABELS: Record<SEOStatus, string> = {
  pending: 'Ожидает',
  generating: 'Генерация',
  completed: 'Готово',
  failed: 'Ошибка',
};

const STATUS_STYLES: Record<SEOStatus, string> = {
  pending: 'bg-slate-100 text-slate-700',
  generating: 'bg-blue-100 text-blue-800',
  completed: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-red-100 text-red-800',
};

const GROUP_ORDER = ['seo_keywords', 'seo_pains', 'seo_desires', 'seo_objections', 'seo_avatar', 'legacy'];

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

function getKeywords(set: SEOKeywordSet): string[] {
  if (Array.isArray(set.keywords_list) && set.keywords_list.length) {
    return set.keywords_list;
  }
  if (set.keyword_groups) {
    return Object.values(set.keyword_groups)
      .flat()
      .filter((item): item is string => Boolean(item));
  }
  return [];
}

function StatusBadge({ status }: { status: SEOStatus }) {
  return (
    <Badge className={`${STATUS_STYLES[status] ?? ''} text-xs font-medium`}>
      {STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

export default function SEOPage() {
  const [activeTab, setActiveTab] = useState<'seo' | 'wordstat'>('seo');
  const [seoSets, setSeoSets] = useState<SEOKeywordSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [wordstatQueries, setWordstatQueries] = useState<WordstatQuery[]>([]);
  const [wordstatLoading, setWordstatLoading] = useState(true);
  const [wordstatRefreshing, setWordstatRefreshing] = useState(false);
  const [wordstatSubmitting, setWordstatSubmitting] = useState(false);
  const [wordstatPhrase, setWordstatPhrase] = useState('');
  const [selectedQueryId, setSelectedQueryId] = useState<number | null>(null);
  const [phraseCounts, setPhraseCounts] = useState<Record<string, number>>({});
  const [historyEdits, setHistoryEdits] = useState<Record<number, string>>({});
  const { canEdit } = useRole();

  const loadSeoSets = async (opts?: { silent?: boolean }) => {
    if (opts?.silent) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    try {
      const data = await seoApi.list();
      setSeoSets(data);
    } catch (error) {
      console.error('Failed to load SEO keyword sets', error);
      toast.error('Не удалось загрузить SEO группы');
    } finally {
      if (opts?.silent) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    loadSeoSets();
  }, []);

  const loadWordstatQueries = async (opts?: { silent?: boolean }) => {
    if (opts?.silent) {
      setWordstatRefreshing(true);
    } else {
      setWordstatLoading(true);
    }
    try {
      const data = await wordstatApi.list();
      setWordstatQueries(data);
      if (!selectedQueryId && data.length) {
        setSelectedQueryId(data[0].id);
      }
    } catch (error) {
      console.error('Failed to load Wordstat history', error);
      toast.error('Не удалось загрузить историю Wordstat');
    } finally {
      setWordstatLoading(false);
      if (opts?.silent) {
        setWordstatRefreshing(false);
      }
    }
  };

  useEffect(() => {
    loadWordstatQueries({ silent: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const grouped = useMemo(() => {
    const map: Record<string, SEOKeywordSet[]> = {};
    seoSets.forEach((set) => {
      const key = set.group_type || 'legacy';
      if (!map[key]) {
        map[key] = [];
      }
      map[key].push(set);
    });
    return map;
  }, [seoSets]);

  const orderedGroups = useMemo(() => {
    const known = GROUP_ORDER.filter((key) => grouped[key]?.length);
    const rest = Object.keys(grouped).filter((key) => !GROUP_ORDER.includes(key));
    return [...known, ...rest];
  }, [grouped]);

  const selectedWordstatQuery = useMemo(() => {
    if (selectedQueryId) {
      const found = wordstatQueries.find((item) => item.id === selectedQueryId);
      if (found) {
        return found;
      }
    }
    return wordstatQueries[0];
  }, [selectedQueryId, wordstatQueries]);

  const favoriteResults = useMemo(() => {
    const result: { phrase: string; count: number; queryId: number }[] = [];
    wordstatQueries.forEach((q) => {
      q.results
        .filter((r) => r.result_type === 'favorite')
        .forEach((r) => result.push({ phrase: r.phrase, count: r.count, queryId: q.id }));
    });
    return result;
  }, [wordstatQueries]);

  const handleGenerateSEO = async () => {
    setGenerating(true);
    try {
      const response = await seoApi.generate();
      toast.success(response.message || 'Генерация SEO запущена');
      await loadSeoSets({ silent: true });
    } catch (error) {
      console.error('Failed to start SEO generation', error);
      toast.error('Не удалось запустить SEO-анализ');
    } finally {
      setGenerating(false);
    }
  };

  const handleRefresh = () => loadSeoSets({ silent: true });

  const fetchWordstatAndRedirect = async (phraseRaw: string) => {
    const phrase = phraseRaw.trim();
    if (!phrase) {
      toast.error('Введите фразу для запроса Wordstat');
      return;
    }
    setWordstatSubmitting(true);
    try {
      const data = await wordstatApi.fetch({ phrase });
      const resultsCount = data.results?.length ?? 0;
      setPhraseCounts((prev) => ({ ...prev, [phrase]: resultsCount }));
      setWordstatQueries((prev) => [data, ...prev.filter((item) => item.id !== data.id)]);
      setSelectedQueryId(data.id);
      if (resultsCount > 0 && data.id) {
        window.location.href = `/seo/${data.id}`;
      }
    } catch (error) {
      console.error('Failed to fetch Wordstat', error);
      const message = error instanceof Error ? error.message : 'Не удалось получить Wordstat';
      toast.error(message);
    } finally {
      setWordstatSubmitting(false);
    }
  };

  const handleWordstatFetch = () => fetchWordstatAndRedirect(wordstatPhrase);

  const handleWordstatRefresh = () => loadWordstatQueries({ silent: true });

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">SEO</h1>
        <p className="text-muted-foreground">
          Инструменты для SEO: готовые AI-группы и прямые выгрузки Wordstat по вашим фразам.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'seo' | 'wordstat')} className="space-y-6">
        <TabsList>
          <TabsTrigger value="seo">SEO группы</TabsTrigger>
          <TabsTrigger value="wordstat">Wordstat</TabsTrigger>
        </TabsList>

        <TabsContent value="seo" className="space-y-6">
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <h2 className="text-2xl font-semibold">SEO группы</h2>
                <p className="text-muted-foreground">
                  Ключевые поисковые фразы и инсайты, которые используют клиенты, когда ищут ваши продукты или услуги.
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={handleRefresh} disabled={loading || refreshing}>
                  <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? 'animate-spin' : ''}`} />
                  Обновить
                </Button>
                <Button onClick={handleGenerateSEO} disabled={!canEdit || generating}>
                  {generating ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Запуск...
                    </>
                  ) : (
                    'Запустить SEO-анализ'
                  )}
                </Button>
              </div>
            </div>
            {!canEdit && (
              <p className="text-sm text-muted-foreground">
                У вас нет прав на запуск генерации SEO. Попросите владельца или редактора аккаунта.
              </p>
            )}
          </div>

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Загружаем SEO группы...
            </div>
          ) : seoSets.length === 0 ? (
            <Card>
              <CardHeader>
                <CardTitle>Пока нет данных</CardTitle>
                <CardDescription>
                  Создайте SEO группы, чтобы увидеть, как клиенты ищут ваши товары и услуги. Нажмите «Запустить SEO-анализ».
                </CardDescription>
              </CardHeader>
            </Card>
          ) : (
            <>
              <div className="flex flex-col gap-4">
                {orderedGroups.map((group_key) => {
                  const sets = grouped[group_key];
                  if (!sets?.length) return null;
                  const latest = sets[0];
                  const keywords = getKeywords(latest);
                  const keywordGroupsEntries = latest.keyword_groups
                    ? Object.entries(latest.keyword_groups).filter(([, values]) => Array.isArray(values) && values.length)
                    : [];
                  const showKeywordGroups = keywordGroupsEntries.length > 0 && keywords.length === 0;
                  return (
                    <Card key={group_key}>
                      <CardHeader className="space-y-2">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <CardTitle>{GROUP_LABELS[group_key] ?? GROUP_LABELS.legacy}</CardTitle>
                            <CardDescription>{GROUP_DESCRIPTIONS[group_key] ?? GROUP_DESCRIPTIONS.legacy}</CardDescription>
                          </div>
                          <StatusBadge status={latest.status} />
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Обновлено: {formatDate(latest.created_at)}
                          {latest.topic_name ? ` • Тема: ${latest.topic_name}` : ''}
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div>
                      <p className="text-sm font-semibold">Ключевые фразы</p>
                      {keywords.length ? (
                        <ul className="mt-2 space-y-1 text-sm text-slate-700">
                          {keywords.map((keyword, idx) => (
                            <li key={`${keyword}-${idx}`}>
                              <button
                                type="button"
                                onClick={() => fetchWordstatAndRedirect(keyword)}
                                className="text-left text-slate-800 underline-offset-2 hover:underline"
                              >
                                {keyword}
                              </button>
                              {typeof phraseCounts[keyword] === 'number' && (
                                <span className="ml-2 text-xs text-muted-foreground">
                                  ({phraseCounts[keyword]} фраз)
                                </span>
                              )}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-muted-foreground">Фразы появятся после завершения генерации.</p>
                      )}
                        </div>
                        {showKeywordGroups && (
                          <div className="space-y-2">
                            <p className="text-sm font-semibold">Группы запросов</p>
                            <div className="space-y-3 rounded-md border bg-slate-50 p-3">
                              {keywordGroupsEntries.map(([groupName, values]) => (
                                <div key={groupName}>
                                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                                    {groupName || 'Группа'}
                                  </p>
                                  <ul className="mt-1 list-disc space-y-1 pl-4 text-sm text-slate-600">
                                    {values.map((value, index) => (
                                      <li key={`${groupName}-${value}-${index}`}>{value}</li>
                                    ))}
                                  </ul>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                        {latest.error_log && (
                          <div className="rounded-md bg-red-50 p-3 text-sm text-red-600">
                            <p className="font-semibold">Ошибка генерации</p>
                            <p className="mt-1 whitespace-pre-wrap">{latest.error_log}</p>
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>История генераций</CardTitle>
                  <CardDescription>Последние запуски SEO-анализа по всем группам</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {seoSets.slice(0, 10).map((seoSet) => (
                    <div
                      key={seoSet.id}
                      className="flex flex-col gap-1 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-semibold">
                            {GROUP_LABELS[seoSet.group_type] ?? GROUP_LABELS.legacy}
                          </p>
                          <StatusBadge status={seoSet.status} />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {formatDate(seoSet.created_at)}
                          {seoSet.topic_name ? ` • ${seoSet.topic_name}` : ''}
                        </p>
                        {seoSet.error_log && (
                          <p className="text-xs text-red-600">Ошибка: {seoSet.error_log.split('\n')[0]}</p>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {seoSet.keywords_list?.length
                          ? `${seoSet.keywords_list.length} фраз`
                          : Object.values(seoSet.keyword_groups || {}).reduce(
                              (total, arr) => total + (arr?.length || 0),
                              0
                            ) + ' фраз'}
                      </div>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        <TabsContent value="wordstat" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Wordstat</CardTitle>
              <CardDescription>
                Введите поисковую фразу, чтобы запросить Wordstat, сохранить результаты в базу и увидеть частотности в таблице.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <form
                className="flex flex-col gap-3 md:flex-row md:items-center"
                onSubmit={(e) => {
                  e.preventDefault();
                  handleWordstatFetch();
                }}
              >
                <Input
                  placeholder="Например: купить велосипед"
                  value={wordstatPhrase}
                  onChange={(e) => setWordstatPhrase(e.target.value)}
                  className="flex-1"
                />
                <div className="flex w-full gap-2 md:w-auto">
                  <Button type="submit" disabled={!canEdit || wordstatSubmitting}>
                    {wordstatSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Запрос...
                      </>
                    ) : (
                      <>
                        <Search className="mr-2 h-4 w-4" />
                        Получить Wordstat
                      </>
                    )}
                  </Button>
                </div>
              </form>
              {!canEdit && (
                <p className="text-sm text-muted-foreground">
                  У вас нет прав на отправку запросов Wordstat. Попросите владельца или редактора аккаунта.
                </p>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>История поисков</CardTitle>
                <CardDescription>Последние запросы Wordstat для этого клиента</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {wordstatLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Загружаем историю...
                  </div>
                ) : wordstatQueries.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Запросы еще не отправлялись.</p>
                ) : (
                  <div className="space-y-2">
                    {favoriteResults.length > 0 && (
                      <button
                        type="button"
                        onClick={() => window.open('/seo/favorites', '_blank', 'noopener')}
                        className="w-full rounded-md border p-3 text-left transition hover:border-slate-400 border-slate-200 bg-white"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="text-sm font-semibold leading-tight">Избранное</p>
                          <Badge variant="outline" className="text-xs font-medium">
                            {favoriteResults.length} фраз
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground">Все отмеченные избранные фразы</p>
                      </button>
                    )}
                    {wordstatQueries.map((query) => {
                      const editedPhrase = historyEdits[query.id] ?? query.request_phrase;
                      return (
                        <div
                          key={query.id}
                          className="w-full rounded-md border border-slate-200 bg-white p-3 transition hover:border-slate-400"
                        >
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center justify-between gap-2">
                              <Input
                                value={editedPhrase}
                                onChange={(e) =>
                                  setHistoryEdits((prev) => ({ ...prev, [query.id]: e.target.value }))
                                }
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    fetchWordstatAndRedirect(editedPhrase);
                                  }
                                }}
                                className="flex-1"
                              />
                              <Badge variant="outline" className="text-xs font-medium">
                                {query.results?.length ?? 0} фраз
                              </Badge>
                            </div>
                            <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
                              <span>
                                {formatDate(query.created_at)} • {query.total_count} показов
                              </span>
                              <div className="flex gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => window.open(`/seo/${query.id}`, '_blank', 'noopener')}
                                >
                                  Открыть
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => fetchWordstatAndRedirect(editedPhrase)}
                                  disabled={wordstatSubmitting}
                                >
                                  Повторить
                                </Button>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
