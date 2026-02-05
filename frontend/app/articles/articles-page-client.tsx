'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import { Trash2 } from 'lucide-react';
import type { Article, ArticleSeoEvaluationResponse, ArticleStatus } from '@/lib/types';
import { ApiError } from '@/lib/api';
import { articlesApi } from '@/lib/api/articles';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useTenantTimezone } from '@/lib/hooks';
import { formatInTenantTimezone } from '@/lib/timezone';

const STATUS_LABELS: Record<ArticleStatus, string> = {
  wordstat: 'Wordstat',
  context_suggested: 'Контекст предложен',
  context_selected: 'Контекст выбран',
  outline_ready: 'Скелет готов',
  article_ready: 'Статья составлена',
  result_edited: 'Правки внесены',
  failed: 'Ошибка',
};

const STATUS_STYLES: Record<ArticleStatus, string> = {
  wordstat: 'bg-slate-100 text-slate-700',
  context_suggested: 'bg-blue-100 text-blue-800',
  context_selected: 'bg-cyan-100 text-cyan-800',
  outline_ready: 'bg-emerald-100 text-emerald-800',
  article_ready: 'bg-amber-100 text-amber-800',
  result_edited: 'bg-teal-100 text-teal-800',
  failed: 'bg-red-100 text-red-800',
};

function formatDate(value: string | null | undefined, timeZone: string) {
  if (!value) return '—';
  try {
    return formatInTenantTimezone(value, timeZone, {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }) || value;
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

function normalizePhrase(value: string): string {
  return value.toLowerCase().replace(/\s+/g, ' ').trim();
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
  const { timezone: tenantTimezone } = useTenantTimezone();
  const [activeTab, setActiveTab] = useState<'create' | 'evaluate'>('create');
  const [evaluateTab, setEvaluateTab] = useState<'analyze' | 'recommend' | 'rewrite'>('analyze');
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [wordstatRaw, setWordstatRaw] = useState('');
  const [evaluateUrl, setEvaluateUrl] = useState('');
  const [evaluateText, setEvaluateText] = useState('');
  const [evaluateWordstat, setEvaluateWordstat] = useState('');
  const [evaluateResult, setEvaluateResult] = useState<ArticleSeoEvaluationResponse | null>(null);
  const [evaluatingAction, setEvaluatingAction] = useState<'analyze' | 'recommend' | 'rewrite' | null>(null);
  const [articleToDelete, setArticleToDelete] = useState<Article | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

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
  const evaluationInput = useMemo(
    () => evaluateUrl.trim() || evaluateText.trim(),
    [evaluateUrl, evaluateText]
  );

  const onStart = async () => {
    const phrases = parsePhrases(wordstatRaw);
    if (!phrases.length) {
      toast.error('Введите Wordstat фразы (одна строка — одна фраза)');
      return;
    }
    setStarting(true);
    try {
      const created = await articlesApi.start({ phrases });
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

  const onEvaluate = async (action: 'analyze' | 'recommend' | 'rewrite') => {
    const trimmedUrl = evaluateUrl.trim();
    const trimmedText = evaluateText.trim();
    if (!evaluationInput) {
      toast.error('Введите ссылку или текст для анализа');
      return;
    }
    setEvaluatingAction(action);
    try {
      const response = await articlesApi.evaluate({
        url: trimmedUrl || undefined,
        text: trimmedText || undefined,
        wordstat: evaluateWordstat.trim() || undefined,
        action,
      });
      setEvaluateResult(response);
      if (action === 'analyze') {
        toast.success('Аналитика готова');
      } else if (action === 'recommend') {
        toast.success('Рекомендации готовы');
      } else {
        toast.success('SEO план готов');
      }
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
      console.error('Failed to evaluate article', error);
      toast.error('Не удалось выполнить анализ');
    } finally {
      setEvaluatingAction(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!articleToDelete || deletingId) return;
    const articleId = articleToDelete.id;
    setDeletingId(articleId);
    try {
      await articlesApi.delete(articleId);
      setArticles((prev) => prev.filter((article) => article.id !== articleId));
      toast.success('Статья удалена');
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        router.push('/login');
        return;
      }
      console.error('Failed to delete article', error);
      toast.error('Не удалось удалить статью');
    } finally {
      setDeletingId(null);
      setArticleToDelete(null);
    }
  };

  const analysis = evaluateResult?.analysis;
  const aiResult = evaluateResult?.ai;
  const isEvaluating = evaluatingAction !== null;
  const canEvaluate = Boolean(evaluationInput);
  const foundKeywords = analysis?.found_keywords ?? [];
  const missingKeywords = analysis?.missing_keywords ?? [];
  const clusterCoverage = analysis?.cluster_coverage ?? [];
  const visibleClusterCoverage = clusterCoverage.filter((cluster) => cluster.found > 0);
  const visibleFound = foundKeywords.slice(0, 20);
  const normalizedMainQuery = normalizePhrase(evaluateWordstat);
  const allKeywords = [...foundKeywords, ...missingKeywords];
  const mainClusterMatch = normalizedMainQuery
    ? allKeywords.find((item) => normalizePhrase(item.phrase) === normalizedMainQuery)
    : undefined;
  const mainClusterFromQuery = mainClusterMatch ? mainClusterMatch.cluster ?? 'Без кластера' : null;
  const mainClusterBySize = clusterCoverage.reduce<(typeof clusterCoverage)[number] | null>(
    (best, cluster) => {
      if (!best) return cluster;
      if (cluster.total !== best.total) {
        return cluster.total > best.total ? cluster : best;
      }
      if (cluster.found !== best.found) {
        return cluster.found > best.found ? cluster : best;
      }
      return cluster.cluster.localeCompare(best.cluster, 'ru') < 0 ? cluster : best;
    },
    null
  );
  const mainCluster = mainClusterFromQuery ?? mainClusterBySize?.cluster ?? null;
  const mainClusterCoverage = mainCluster
    ? clusterCoverage.find((cluster) => cluster.cluster === mainCluster)
    : null;
  const mainClusterMissing = mainCluster
    ? missingKeywords.filter((item) => (item.cluster ?? 'Без кластера') === mainCluster)
    : [];
  const visibleMainClusterMissing = mainClusterMissing.slice(0, 20);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Статьи</h1>
      <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as typeof activeTab)} className="space-y-4">
        <TabsList>
          <TabsTrigger value="create">Создать</TabsTrigger>
          <TabsTrigger value="evaluate">Оценить</TabsTrigger>
        </TabsList>

        <TabsContent value="create" className="space-y-4">
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
                  Будут использованы все фразы из группы или найденного кластера.
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
                  <TableHead className="w-12 text-right"> </TableHead>
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
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(article.created_at, tenantTimezone)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={article.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                          setArticleToDelete(article);
                        }}
                        aria-label="Удалить"
                        title="Удалить"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}

          <Dialog
            open={articleToDelete != null}
            onOpenChange={(open) => {
              if (!open && !deletingId) {
                setArticleToDelete(null);
              }
            }}
          >
            <DialogContent className="sm:max-w-md bg-white text-gray-900 dark:bg-white dark:text-gray-900 dark:border-gray-200 [&>button]:text-gray-900 dark:[&>button]:text-gray-900 dark:[&>button]:data-[state=open]:bg-gray-100 dark:[&>button]:data-[state=open]:text-gray-600">
              <DialogHeader>
                <DialogTitle>Удалить статью?</DialogTitle>
                <DialogDescription>
                  {articleToDelete
                    ? `Статья «${articleToDelete.wordstat}» будет удалена без возможности восстановления.`
                    : 'Статья будет удалена без возможности восстановления.'}
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setArticleToDelete(null)}
                  disabled={Boolean(deletingId)}
                >
                  Отмена
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => void handleDeleteConfirm()}
                  disabled={Boolean(deletingId)}
                >
                  {deletingId ? 'Удаление…' : 'Удалить'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        <TabsContent value="evaluate" className="space-y-4">
          <div className="space-y-2">
            <div className="text-sm font-semibold">Основной запрос</div>
            <Input
              value={evaluateWordstat}
              onChange={(e) => setEvaluateWordstat(e.target.value)}
              placeholder="Wordstat запрос (необязательно)"
            />
          </div>

          <div className="space-y-2">
            <Input
              value={evaluateUrl}
              onChange={(e) => setEvaluateUrl(e.target.value)}
              placeholder="https://example.com/article"
            />
            <Textarea
              value={evaluateText}
              onChange={(e) => setEvaluateText(e.target.value)}
              placeholder="Вставьте готовую статью для анализа"
              className="min-h-32"
            />
          </div>

          <Tabs
            value={evaluateTab}
            onValueChange={(value) => setEvaluateTab(value as typeof evaluateTab)}
            className="space-y-4"
          >
            <TabsList>
              <TabsTrigger
                value="analyze"
                onClick={() => void onEvaluate('analyze')}
                disabled={isEvaluating || !canEvaluate}
              >
                {evaluatingAction === 'analyze' ? 'Анализируем…' : 'Аналитика'}
              </TabsTrigger>
              <TabsTrigger
                value="recommend"
                onClick={() => void onEvaluate('recommend')}
                disabled={isEvaluating || !canEvaluate}
              >
                {evaluatingAction === 'recommend' ? 'Собираем…' : 'Рекомендации'}
              </TabsTrigger>
              <TabsTrigger
                value="rewrite"
                onClick={() => void onEvaluate('rewrite')}
                disabled={isEvaluating || !canEvaluate}
              >
                {evaluatingAction === 'rewrite' ? 'Готовим…' : 'Работа ИИ'}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="analyze" className="space-y-4">
              {analysis ? (
                <div className="space-y-4">
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-md border bg-background p-3">
                      <div className="text-xs text-muted-foreground">Покрытие Wordstat</div>
                      <div className="text-xl font-semibold">{analysis.coverage_percent}%</div>
                      <div className="text-xs text-muted-foreground">
                        {foundKeywords.length}/{analysis.total_keywords} ключей
                      </div>
                    </div>
                    <div className="rounded-md border bg-background p-3">
                      <div className="text-xs text-muted-foreground">Слова (леммы)</div>
                      <div className="text-xl font-semibold">{analysis.word_count}</div>
                    </div>
                    {evaluateResult?.source?.title ? (
                      <div className="rounded-md border bg-background p-3">
                        <div className="text-xs text-muted-foreground">Заголовок страницы</div>
                        <div className="text-sm font-medium">{evaluateResult.source.title}</div>
                      </div>
                    ) : null}
                  </div>

                  {visibleClusterCoverage.length ? (
                    <div className="space-y-2">
                      <div className="text-sm font-semibold">Покрытие кластеров</div>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Кластер</TableHead>
                            <TableHead className="w-32 text-right">Покрытие</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {visibleClusterCoverage.map((cluster) => (
                            <TableRow key={cluster.cluster}>
                              <TableCell className="text-sm">{cluster.cluster}</TableCell>
                              <TableCell className="text-right text-sm text-muted-foreground">
                                {cluster.found}/{cluster.total}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : null}

                  <div className="space-y-2">
                    <div className="text-sm font-semibold">Найденные ключи</div>
                    {visibleFound.length ? (
                      <div className="space-y-1">
                        {visibleFound.map((item) => (
                          <div key={`${item.phrase}-${item.cluster || ''}`} className="text-sm">
                            <span>{item.phrase}</span>
                            {typeof item.count === 'number' ? (
                              <span className="ml-2 text-xs text-muted-foreground">×{item.count}</span>
                            ) : null}
                            {item.cluster ? (
                              <span className="ml-2 text-xs text-muted-foreground">• {item.cluster}</span>
                            ) : null}
                          </div>
                        ))}
                        {foundKeywords.length > visibleFound.length ? (
                          <div className="text-xs text-muted-foreground">
                            И ещё {foundKeywords.length - visibleFound.length}.
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">Ничего не найдено.</div>
                    )}
                  </div>
                </div>
              ) : null}
            </TabsContent>

            <TabsContent value="recommend" className="space-y-4">
              {analysis ? (
                <div className="space-y-4">
                  <div className="rounded-md border bg-background p-3">
                    <div className="text-xs text-muted-foreground">Главный кластер</div>
                    <div className="text-sm font-semibold">{mainCluster ?? 'Не определен'}</div>
                    {mainClusterCoverage ? (
                      <div className="text-xs text-muted-foreground">
                        Покрытие {mainClusterCoverage.found}/{mainClusterCoverage.total}
                      </div>
                    ) : null}
                  </div>

                  <div className="space-y-2">
                    <div className="text-sm font-semibold">Пропущенные ключи</div>
                    {visibleMainClusterMissing.length ? (
                      <div className="space-y-1">
                        {visibleMainClusterMissing.map((item) => (
                          <div key={`${item.phrase}-${item.cluster || ''}`} className="text-sm">
                            <span>{item.phrase}</span>
                          </div>
                        ))}
                        {mainClusterMissing.length > visibleMainClusterMissing.length ? (
                          <div className="text-xs text-muted-foreground">
                            И ещё {mainClusterMissing.length - visibleMainClusterMissing.length}.
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground">
                        {mainCluster ? 'Все ключи по кластеру покрыты.' : 'Нет данных по кластеру.'}
                      </div>
                    )}
                  </div>
                </div>
              ) : null}

              {aiResult ? (
                <div className="space-y-4 rounded-md border bg-background p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold">AI выводы</div>
                    {aiResult.intent ? (
                      <Badge className="bg-slate-100 text-slate-700">Интент: {aiResult.intent}</Badge>
                    ) : null}
                  </div>

                  {aiResult.strengths?.length ? (
                    <div className="space-y-1">
                      <div className="text-sm font-semibold">Сильные стороны</div>
                      <div className="text-sm text-muted-foreground">{aiResult.strengths.join(' • ')}</div>
                    </div>
                  ) : null}

                  {aiResult.gaps?.length ? (
                    <div className="space-y-1">
                      <div className="text-sm font-semibold">Слабые места</div>
                      <div className="text-sm text-muted-foreground">{aiResult.gaps.join(' • ')}</div>
                    </div>
                  ) : null}

                  {aiResult.recommendations?.length ? (
                    <div className="space-y-1">
                      <div className="text-sm font-semibold">Рекомендации</div>
                      <div className="text-sm text-muted-foreground">{aiResult.recommendations.join(' • ')}</div>
                    </div>
                  ) : null}

                  {aiResult.keyword_advice ? (
                    <div className="grid gap-3 md:grid-cols-3">
                      {aiResult.keyword_advice.include?.length ? (
                        <div className="space-y-1">
                          <div className="text-sm font-semibold">Включить</div>
                          <div className="text-xs text-muted-foreground">
                            {aiResult.keyword_advice.include.join(', ')}
                          </div>
                        </div>
                      ) : null}
                      {aiResult.keyword_advice.exclude?.length ? (
                        <div className="space-y-1">
                          <div className="text-sm font-semibold">Не использовать</div>
                          <div className="text-xs text-muted-foreground">
                            {aiResult.keyword_advice.exclude.join(', ')}
                          </div>
                        </div>
                      ) : null}
                      {aiResult.keyword_advice.separate_article?.length ? (
                        <div className="space-y-1">
                          <div className="text-sm font-semibold">Отдельная статья</div>
                          <div className="text-xs text-muted-foreground">
                            {aiResult.keyword_advice.separate_article.join(', ')}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </TabsContent>

            <TabsContent value="rewrite" className="space-y-4">
              {aiResult ? (
                <div className="space-y-4 rounded-md border bg-background p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="text-sm font-semibold">AI выводы</div>
                    {aiResult.intent ? (
                      <Badge className="bg-slate-100 text-slate-700">Интент: {aiResult.intent}</Badge>
                    ) : null}
                  </div>

                  {aiResult.rewrite_plan ? (
                    <div className="space-y-2">
                      <div className="text-sm font-semibold">SEO-план</div>
                      {aiResult.rewrite_plan.h1 ? (
                        <div className="text-sm">
                          <span className="text-xs text-muted-foreground">H1: </span>
                          {aiResult.rewrite_plan.h1}
                        </div>
                      ) : null}
                      {aiResult.rewrite_plan.h2?.length ? (
                        <div className="text-sm text-muted-foreground">
                          H2: {aiResult.rewrite_plan.h2.join(' • ')}
                        </div>
                      ) : null}
                      {aiResult.rewrite_plan.h3?.length ? (
                        <div className="text-sm text-muted-foreground">
                          H3: {aiResult.rewrite_plan.h3.join(' • ')}
                        </div>
                      ) : null}
                      {aiResult.rewrite_plan.add_blocks?.length ? (
                        <div className="text-sm text-muted-foreground">
                          Добавить: {aiResult.rewrite_plan.add_blocks.join(' • ')}
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {aiResult.rewrite_text ? (
                    <div className="space-y-2">
                      <div className="text-sm font-semibold">Короткий rewrite</div>
                      <pre className="whitespace-pre-wrap rounded-md border bg-muted/20 p-3 text-xs leading-5">
                        {aiResult.rewrite_text}
                      </pre>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </TabsContent>
          </Tabs>
        </TabsContent>
      </Tabs>
    </div>
  );
}
