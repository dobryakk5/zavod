/* eslint-disable react-hooks/exhaustive-deps */
'use client';

import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Loader2, RefreshCw, Search, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { ApiError } from '@/lib/api';
import { seoApi } from '@/lib/api/seo';
import { wordstatApi } from '@/lib/api/wordstat';
import { googleApi } from '@/lib/api/google';
import type { GoogleCseSearchResult, SEOKeywordSet, SEOStatus, WordstatQuery } from '@/lib/types';
import { useRole } from '@/lib/hooks';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

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

export default function SEOPageClient() {
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<'seo' | 'wordstat' | 'competitors'>('seo');
  const [seoSets, setSeoSets] = useState<SEOKeywordSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [wordstatQueries, setWordstatQueries] = useState<WordstatQuery[]>([]);
  const [wordstatLoading, setWordstatLoading] = useState(true);
  const [wordstatRefreshing, setWordstatRefreshing] = useState(false);
  const [wordstatSubmitting, setWordstatSubmitting] = useState(false);
  const [wordstatGroup, setWordstatGroup] = useState('');
  const [selectedQueryId, setSelectedQueryId] = useState<number | null>(null);
  const [phraseCounts, setPhraseCounts] = useState<Record<string, number>>({});
  const [historyEdits, setHistoryEdits] = useState<Record<number, string>>({});
  const [groupNameEdits, setGroupNameEdits] = useState<Record<number, string>>({});
  const [deletingQueries, setDeletingQueries] = useState<Record<number, boolean>>({});
  const [googleSearching, setGoogleSearching] = useState(false);
  const [googleQuery, setGoogleQuery] = useState<string | null>(null);
  const [googleResults, setGoogleResults] = useState<GoogleCseSearchResult[]>([]);
  const [competitorPhrase, setCompetitorPhrase] = useState<string>('');
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

  const topFavorite = useMemo(() => {
    const bestByPhrase = new Map<string, { phrase: string; count: number }>();
    favoriteResults.forEach((row) => {
      const phrase = (row.phrase || '').trim();
      if (!phrase) return;
      const prev = bestByPhrase.get(phrase);
      if (!prev || row.count > prev.count) {
        bestByPhrase.set(phrase, { phrase, count: row.count });
      }
    });
    const list = Array.from(bestByPhrase.values());
    list.sort((a, b) => b.count - a.count || a.phrase.localeCompare(b.phrase));
    return list[0] || null;
  }, [favoriteResults]);

  useEffect(() => {
    const tab = (searchParams.get('tab') || '').trim();
    if (tab === 'competitors' || tab === 'seo' || tab === 'wordstat') {
      setActiveTab(tab as typeof activeTab);
    }
    const q = (searchParams.get('q') || '').trim();
    if (q) {
      setCompetitorPhrase(q);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!competitorPhrase && topFavorite?.phrase) {
      setCompetitorPhrase(topFavorite.phrase);
    }
  }, [competitorPhrase, topFavorite?.phrase]);

  const extractPhrases = (value: string) => {
    const seen = new Set<string>();
    return value
      .split(/\r?\n/)
      .map((item) => item.trim())
      .filter((item) => {
        if (!item || seen.has(item)) return false;
        seen.add(item);
        return true;
      });
  };

  const normalizePhraseList = (values: string[] = []) => {
    const seen = new Set<string>();
    const normalized: string[] = [];
    values.forEach((value) => {
      const text = (value || '').trim();
      if (text && !seen.has(text)) {
        seen.add(text);
        normalized.push(text);
      }
    });
    return normalized;
  };

  const getQueryText = (query: WordstatQuery) => {
    const list =
      Array.isArray(query.phrases) && query.phrases.length
        ? query.phrases
        : query.request_phrase
          ? [query.request_phrase]
          : [];
    return list.join('\n');
  };

  const getQueryTitle = (query: WordstatQuery) => {
    return (query.group_name || '').trim() || query.request_phrase || '';
  };

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

  const fetchWordstatAndRedirect = async (payload: { phrase?: string; phrases?: string[]; group_name?: string }) => {
    const phrase = (payload.phrase || '').trim();
    const normalizedGroup = normalizePhraseList(payload.phrases);
    if (!phrase && normalizedGroup.length === 0) {
      toast.error('Введите фразу или группу фраз для запроса Wordstat');
      return;
    }

    const requestBody: Parameters<typeof wordstatApi.fetch>[0] = {};
    if (phrase) {
      requestBody.phrase = phrase;
    }
    if (normalizedGroup.length) {
      requestBody.phrases = normalizedGroup;
    }
    if (payload.group_name) {
      requestBody.group_name = payload.group_name.trim();
    }

    setWordstatSubmitting(true);
    try {
      const data = await wordstatApi.fetch(requestBody);
      const resultsCount = data.results?.length ?? 0;
      if (phrase || normalizedGroup.length === 1) {
        const key = phrase || normalizedGroup[0];
        setPhraseCounts((prev) => ({ ...prev, [key]: resultsCount }));
      }
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

  const handleWordstatGroupFetch = () => {
    const phrases = extractPhrases(wordstatGroup);
    fetchWordstatAndRedirect({ phrases });
  };

  const rerunWordstatFromText = async (value: string, query?: WordstatQuery) => {
    const phrases = extractPhrases(value);
    const normalizedGroup = normalizePhraseList(phrases);

    if (query && query.id) {
      const existingSet = new Set<string>((query.phrases || []).map((item) => item.trim()));
      const newPhrases = normalizedGroup.filter((p) => !existingSet.has(p));
      if (newPhrases.length === 0) {
        toast.error('Новых фраз нет — добавьте строки, которых еще не было в группе');
        return;
      }
      setWordstatSubmitting(true);
      try {
        const data = await wordstatApi.append(Number(query.id), { phrases: newPhrases });
        setWordstatQueries((prev) => [data, ...prev.filter((item) => item.id !== data.id)]);
        setHistoryEdits((prev) => ({ ...prev, [query.id]: getQueryText(data) }));
        setGroupNameEdits((prev) => ({ ...prev, [query.id]: getQueryTitle(data) }));
        setSelectedQueryId(data.id);
        window.location.href = `/seo/${data.id}`;
        return;
      } catch (error) {
        console.error('Failed to append Wordstat phrases', error);
        const message = error instanceof Error ? error.message : 'Не удалось обновить Wordstat';
        toast.error(message);
      } finally {
        setWordstatSubmitting(false);
      }
    }

    fetchWordstatAndRedirect({ phrases: normalizedGroup });
  };

  const handleSaveGroupName = async (query: WordstatQuery, value: string) => {
    const name = value.trim().slice(0, 255);
    if (!query?.id) return;
    setWordstatSubmitting(true);
    try {
      const data = await wordstatApi.updateGroupName(Number(query.id), name);
      setWordstatQueries((prev) => [data, ...prev.filter((item) => item.id !== data.id)]);
      setGroupNameEdits((prev) => ({ ...prev, [query.id]: getQueryTitle(data) }));
    } catch (error) {
      console.error('Failed to update Wordstat group name', error);
      const message = error instanceof Error ? error.message : 'Не удалось обновить название группы';
      toast.error(message);
    } finally {
      setWordstatSubmitting(false);
    }
  };

  const handleDeleteQuery = async (query: WordstatQuery) => {
    if (!query?.id) return;
    setDeletingQueries((prev) => ({ ...prev, [query.id]: true }));
    try {
      await wordstatApi.remove(Number(query.id));
      setWordstatQueries((prev) => prev.filter((item) => item.id !== query.id));
      setSelectedQueryId((prev) => (prev === query.id ? null : prev));
      setHistoryEdits((prev) => {
        const next = { ...prev };
        delete next[query.id];
        return next;
      });
      setGroupNameEdits((prev) => {
        const next = { ...prev };
        delete next[query.id];
        return next;
      });
    } catch (error) {
      console.error('Failed to delete Wordstat query', error);
      const message = error instanceof Error ? error.message : 'Не удалось удалить запрос Wordstat';
      toast.error(message);
    } finally {
      setDeletingQueries((prev) => {
        const next = { ...prev };
        delete next[query.id];
        return next;
      });
    }
  };

  const handleWordstatRefresh = () => loadWordstatQueries({ silent: true });

  const handleGoogleSearch = async (phrase?: string) => {
    const query = (phrase ?? competitorPhrase ?? '').trim();
    if (!query) return;
    setGoogleSearching(true);
    setGoogleQuery(null);
    setGoogleResults([]);
    try {
      const data = await googleApi.cseSearch(query, 10);
      setGoogleQuery(data.query);
      setGoogleResults(data.results);
    } catch (err) {
      console.error('Failed to search in Google', err);
      if (err instanceof ApiError) {
        try {
          const payload = err.body ? JSON.parse(err.body) : null;
          const message = payload?.detail || payload?.error;
          if (message) {
            toast.error(String(message));
            return;
          }
        } catch {}
      }
      toast.error('Не удалось получить результаты Google');
    } finally {
      setGoogleSearching(false);
    }
  };

  useEffect(() => {
    if (activeTab !== 'competitors') return;
    const q = (competitorPhrase || '').trim();
    if (!q) return;
    if (googleQuery === q) return;
    if (googleSearching) return;
    handleGoogleSearch(q);
  }, [activeTab, competitorPhrase]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2">
        <h1 className="text-3xl font-bold">SEO</h1>
        <p className="text-muted-foreground">
          Инструменты для SEO: готовые AI-группы и прямые выгрузки Wordstat по вашим фразам.
        </p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) => setActiveTab(value as 'seo' | 'wordstat' | 'competitors')}
        className="space-y-6"
      >
        <TabsList>
          <TabsTrigger value="seo">SEO группы</TabsTrigger>
          <TabsTrigger value="wordstat">Wordstat</TabsTrigger>
          <TabsTrigger value="competitors">Конкуренты</TabsTrigger>
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
                                onClick={() => fetchWordstatAndRedirect({ phrases: [keyword] })}
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
                  Введите запросы построчно: строки отправятся в Wordstat и сохранятся в единую таблицу.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <p className="text-sm font-semibold">Запрос</p>
                    <div className="flex flex-col gap-3">
                      <Textarea
                        placeholder="Каждая строка — отдельный запрос Wordstat"
                        value={wordstatGroup}
                        onChange={(e) => setWordstatGroup(e.target.value)}
                        className="min-h-[120px]"
                      />
                      <div className="flex w-full gap-2">
                        <Button type="button" disabled={!canEdit || wordstatSubmitting} onClick={handleWordstatGroupFetch} className="w-full">
                          {wordstatSubmitting ? (
                            <>
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                              Запрос...
                            </>
                          ) : (
                            <>
                              <Search className="mr-2 h-4 w-4" />
                              Ищи запрос
                            </>
                          )}
                        </Button>
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      Строки опрашиваются по очереди, результаты объединяются в общий список для этой группы.
                    </p>
                  </div>
                </div>

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
                      const editedPhrase = historyEdits[query.id] ?? getQueryText(query);
                      const editedGroupName = groupNameEdits[query.id] ?? getQueryTitle(query);
                      const isGroupQuery = editedPhrase.includes('\n') || (query.phrases?.length ?? 0) > 1;
                      return (
                        <div
                          key={query.id}
                          className="w-full rounded-md border border-slate-200 bg-white p-3 transition hover:border-slate-400"
                        >
                          <div className="flex flex-col gap-2">
                            <div className="flex items-center gap-2">
                              <Input
                                value={editedGroupName}
                                onChange={(e) => setGroupNameEdits((prev) => ({ ...prev, [query.id]: e.target.value }))}
                                placeholder="Название группы"
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') {
                                    e.preventDefault();
                                    handleSaveGroupName(query, editedGroupName);
                                  }
                                }}
                                className="flex-1"
                              />
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleSaveGroupName(query, editedGroupName)}
                                disabled={wordstatSubmitting}
                              >
                                Сохранить
                              </Button>
                            </div>
                            <div className="flex items-start justify-between gap-2">
                              {isGroupQuery ? (
                                <Textarea
                                  value={editedPhrase}
                                  onChange={(e) =>
                                    setHistoryEdits((prev) => ({ ...prev, [query.id]: e.target.value }))
                                  }
                                  onKeyDown={(e) => {
                                    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                                      e.preventDefault();
                                      rerunWordstatFromText(editedPhrase, query);
                                    }
                                  }}
                                  className="min-h-[96px] flex-1"
                                />
                              ) : (
                                <Input
                                  value={editedPhrase}
                                  onChange={(e) =>
                                    setHistoryEdits((prev) => ({ ...prev, [query.id]: e.target.value }))
                                  }
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      e.preventDefault();
                                      rerunWordstatFromText(editedPhrase, query);
                                    }
                                  }}
                                  className="flex-1"
                                />
                              )}
                              <Badge variant="outline" className="text-xs font-medium whitespace-nowrap">
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
                                  onClick={() => rerunWordstatFromText(editedPhrase, query)}
                                  disabled={wordstatSubmitting}
                                >
                                  Повторить
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleDeleteQuery(query)}
                                  disabled={deletingQueries[query.id]}
                                  className="border-red-200 text-red-700 hover:bg-red-50 hover:text-red-800"
                                >
                                  <Trash2 className="h-4 w-4" />
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

        <TabsContent value="competitors" className="space-y-6">
          <Card>
            <CardHeader className="space-y-2">
              <CardTitle>Конкуренты</CardTitle>
              <CardDescription>
                Поиск в Google по фразе Wordstat из избранного.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {competitorPhrase ? (
                <div className="space-y-2">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm font-semibold">Фраза</p>
                      <p className="text-sm text-slate-700">{competitorPhrase}</p>
                      {topFavorite?.phrase === competitorPhrase ? (
                        <p className="text-xs text-muted-foreground">
                          {topFavorite.count.toLocaleString('ru-RU')} показов
                        </p>
                      ) : null}
                    </div>
                    <Button
                      type="button"
                      onClick={() => handleGoogleSearch(competitorPhrase)}
                      disabled={googleSearching || wordstatLoading}
                    >
                      {googleSearching ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Ищем...
                        </>
                      ) : (
                        'Найти в Google'
                      )}
                    </Button>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Нет избранных фраз Wordstat — отметьте фразы как избранные и попробуйте снова.
                </p>
              )}
            </CardContent>
          </Card>

          {googleQuery && (
            <Card>
              <CardHeader className="space-y-2">
                <CardTitle>Результаты Google</CardTitle>
                <CardDescription>{googleResults.length ? `${googleResults.length} результатов` : 'Ничего не найдено'}</CardDescription>
              </CardHeader>
              <CardContent>
                {googleResults.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Попробуйте другую фразу в Wordstat.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[72px]">#</TableHead>
                        <TableHead className="w-[220px]">Домен</TableHead>
                        <TableHead>Заголовок</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {googleResults.map((row) => (
                        <TableRow key={`${row.position}-${row.url}`}>
                          <TableCell className="tabular-nums text-muted-foreground">{row.position}</TableCell>
                          <TableCell>
                            <Badge variant="outline" className="text-xs">
                              {row.domain || '—'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <a
                              href={row.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-medium text-slate-900 underline-offset-2 hover:underline"
                            >
                              {row.title}
                            </a>
                            {row.snippet ? (
                              <p className="mt-1 text-xs text-muted-foreground">{row.snippet}</p>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
