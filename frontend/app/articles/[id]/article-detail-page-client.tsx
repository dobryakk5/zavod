'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import type { Article, ArticleBlock, ArticleStatus, ClientProduct, ProductType } from '@/lib/types';
import { ApiError } from '@/lib/api';
import { articlesApi } from '@/lib/api/articles';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { productTypesApi } from '@/lib/api/productTypes';

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

function ensureArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item)).map((s) => s.trim()).filter(Boolean);
}

function parseKeywordsCsv(raw: string): string[] {
  return (raw || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
    .slice(0, 2);
}

function ToggleList({
  title,
  items,
  selected,
  onChange,
}: {
  title: string;
  items: string[];
  selected: Set<string>;
  onChange: (next: Set<string>) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="text-sm font-semibold">{title}</div>
      <div className="space-y-2">
        {items.map((item) => {
          const checked = selected.has(item);
          return (
            <label key={item} className="flex items-start gap-3 rounded-md border bg-background px-3 py-2">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4"
                checked={checked}
                onChange={() => {
                  const next = new Set(selected);
                  if (checked) next.delete(item);
                  else next.add(item);
                  onChange(next);
                }}
              />
              <span className="text-sm leading-5">{item}</span>
            </label>
          );
        })}
        {items.length === 0 ? <div className="text-sm text-muted-foreground">Нет вариантов.</div> : null}
      </div>
    </div>
  );
}

export default function ArticleDetailPageClient() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const articleId = Number(params.id);
  const [loading, setLoading] = useState(true);
  const [article, setArticle] = useState<Article | null>(null);

  const [activeTab, setActiveTab] = useState<'wordstat' | 'context' | 'structure' | 'seo'>('context');
  const initialTabSetRef = useRef(false);

  const [wordstatDraft, setWordstatDraft] = useState('');
  const [savingWordstat, setSavingWordstat] = useState(false);
  const [audienceDraft, setAudienceDraft] = useState('');
  const [savingAudience, setSavingAudience] = useState(false);

  const [outlineDraft, setOutlineDraft] = useState('');
  const [savingOutline, setSavingOutline] = useState(false);

  const [blocksLoading, setBlocksLoading] = useState(false);
  const [blocks, setBlocks] = useState<ArticleBlock[]>([]);
  const [savingBlockId, setSavingBlockId] = useState<number | null>(null);
  const [generatingBlockId, setGeneratingBlockId] = useState<number | null>(null);
  const [generatingBlueprint, setGeneratingBlueprint] = useState(false);

  const [productsLoading, setProductsLoading] = useState(false);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [types, setTypes] = useState<ProductType[]>([]);
  const [savingChoices, setSavingChoices] = useState(false);
  const [generatingOutline, setGeneratingOutline] = useState(false);

  const [whyNowSelected, setWhyNowSelected] = useState<Set<string>>(new Set());
  const [solutionSelected, setSolutionSelected] = useState<Set<string>>(new Set());
  const [leadProductId, setLeadProductId] = useState<number | null>(null);
  const [tripwireProductId, setTripwireProductId] = useState<number | null>(null);

  const saveTimerRef = useRef<number | null>(null);
  const hydratedRef = useRef(false);

  const outline = useMemo(() => (outlineDraft || '').trim(), [outlineDraft]);
  const whyNowOptions = useMemo(() => ensureArray(article?.options_why_now), [article?.options_why_now]);
  const solutionOptions = useMemo(() => ensureArray(article?.options_solution), [article?.options_solution]);

  const typeKeyById = useMemo(() => {
    const map = new Map<number, string>();
    for (const type of types) {
      if (typeof type.id === 'number') {
        map.set(type.id, String(type.name || '').trim().toLowerCase());
      }
    }
    return map;
  }, [types]);

  const leadProducts = useMemo(() => {
    return products.filter((p) => {
      const typeId = p.product_type_id ?? null;
      if (!typeId) return false;
      return typeKeyById.get(typeId) === 'lead';
    });
  }, [products, typeKeyById]);

  const tripwireProducts = useMemo(() => {
    return products.filter((p) => {
      const typeId = p.product_type_id ?? null;
      if (!typeId) return false;
      return typeKeyById.get(typeId) === 'tripwire';
    });
  }, [products, typeKeyById]);

  const leadProductName = useMemo(() => {
    if (!leadProductId) return '';
    return leadProducts.find((p) => p.id === leadProductId)?.name ?? '';
  }, [leadProductId, leadProducts]);

  const tripwireProductName = useMemo(() => {
    if (!tripwireProductId) return '';
    return tripwireProducts.find((p) => p.id === tripwireProductId)?.name ?? '';
  }, [tripwireProductId, tripwireProducts]);

  useEffect(() => {
    if (!Number.isFinite(articleId) || !articleId) {
      toast.error('Некорректный id статьи');
      router.push('/articles');
      return;
    }

    const load = async () => {
      setLoading(true);
      try {
        const data = await articlesApi.get(articleId);
        setArticle(data);
        setWordstatDraft(data.wordstat || '');
        setAudienceDraft(String(data.audience || ''));
        setWhyNowSelected(new Set(ensureArray(data.selected_why_now)));
        setSolutionSelected(new Set(ensureArray(data.selected_solution)));
        setLeadProductId(typeof data.lead_product_id === 'number' ? data.lead_product_id : null);
        setTripwireProductId(typeof data.tripwire_product_id === 'number' ? data.tripwire_product_id : null);
        setOutlineDraft(String(data.outline_markdown || ''));
        if (!initialTabSetRef.current) {
          setActiveTab(data.status === 'outline_ready' ? 'structure' : 'context');
          initialTabSetRef.current = true;
        }
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          router.push('/login');
          return;
        }
        console.error('Failed to load article', error);
        toast.error('Не удалось загрузить статью');
        router.push('/articles');
      } finally {
        setLoading(false);
        hydratedRef.current = true;
      }
    };

    void load();
  }, [articleId, router]);

  useEffect(() => {
    const loadBlocks = async () => {
      if (!Number.isFinite(articleId) || !articleId) return;
      setBlocksLoading(true);
      try {
        const data = await articlesApi.listBlocks(articleId);
        setBlocks(data);
      } catch (error) {
        console.error('Failed to load article blocks', error);
      } finally {
        setBlocksLoading(false);
      }
    };
    void loadBlocks();
  }, [articleId]);

  const reloadBlocks = async () => {
    try {
      const data = await articlesApi.listBlocks(articleId);
      setBlocks(data);
    } catch (error) {
      console.error('Failed to reload blocks', error);
    }
  };

  useEffect(() => {
    const loadProducts = async () => {
      setProductsLoading(true);
      try {
        const [productData, typeData] = await Promise.all([clientProductsApi.list(), productTypesApi.list()]);
        setProducts(productData);
        setTypes(typeData);
      } catch (error) {
        console.error('Failed to load products/types', error);
        toast.error('Не удалось загрузить продукты для выбора');
      } finally {
        setProductsLoading(false);
      }
    };

    void loadProducts();
  }, []);

  const scheduleSave = () => {
    if (!article) return;
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = window.setTimeout(async () => {
      setSavingChoices(true);
      try {
        const updated = await articlesApi.saveChoices(articleId, {
          selected_why_now: Array.from(whyNowSelected),
          selected_solution: Array.from(solutionSelected),
          lead_product_id: leadProductId,
          lead_product_name: leadProductName || null,
          tripwire_product_id: tripwireProductId,
          tripwire_product_name: tripwireProductName || null,
        });
        setArticle(updated);
      } catch (error) {
        console.error('Failed to save article choices', error);
        toast.error('Не удалось сохранить выбор');
      } finally {
        setSavingChoices(false);
      }
    }, 500);
  };

  useEffect(() => {
    if (!hydratedRef.current) return;
    scheduleSave();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [whyNowSelected, solutionSelected, leadProductId, tripwireProductId, leadProductName, tripwireProductName]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        window.clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  const onGenerateOutline = async () => {
    if (!article) return;
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    setGeneratingOutline(true);
    try {
      const updated = await articlesApi.generateOutline(articleId, {
        selected_why_now: Array.from(whyNowSelected),
        selected_solution: Array.from(solutionSelected),
        lead_product_id: leadProductId,
        lead_product_name: leadProductName || null,
        tripwire_product_id: tripwireProductId,
        tripwire_product_name: tripwireProductName || null,
      });
      setArticle(updated);
      setOutlineDraft(String(updated.outline_markdown || ''));
      try {
        const blocksData = await articlesApi.listBlocks(articleId);
        setBlocks(blocksData);
      } catch {
        // ignore blocks refresh errors
      }
      setActiveTab('structure');
    } catch (error) {
      console.error('Failed to generate outline', error);
      toast.error('Не удалось сформировать структуру статьи');
    } finally {
      setGeneratingOutline(false);
    }
  };

  const onSaveWordstat = async () => {
    const next = wordstatDraft.trim();
    if (!article || !next) return;
    setSavingWordstat(true);
    try {
      const updated = await articlesApi.updateWordstat(articleId, next);
      setArticle(updated);
      setWordstatDraft(updated.wordstat || next);
      setOutlineDraft(String(updated.outline_markdown || outlineDraft));
      toast.success('Wordstat сохранён');
    } catch (error) {
      console.error('Failed to update wordstat', error);
      toast.error('Не удалось сохранить wordstat');
    } finally {
      setSavingWordstat(false);
    }
  };

  const onSaveAudience = async () => {
    if (!article) return;
    setSavingAudience(true);
    try {
      const updated = await articlesApi.updateAudience(articleId, audienceDraft);
      setArticle(updated);
      setAudienceDraft(String(updated.audience || audienceDraft));
      toast.success('Аудитория сохранена');
    } catch (error) {
      console.error('Failed to update audience', error);
      toast.error('Не удалось сохранить аудиторию');
    } finally {
      setSavingAudience(false);
    }
  };

  const onSaveOutline = async () => {
    if (!article) return;
    setSavingOutline(true);
    try {
      const updated = await articlesApi.updateOutline(articleId, outlineDraft);
      setArticle(updated);
      setOutlineDraft(String(updated.outline_markdown || outlineDraft));
      toast.success('Структура сохранена');
    } catch (error) {
      console.error('Failed to update outline', error);
      toast.error('Не удалось сохранить структуру');
    } finally {
      setSavingOutline(false);
    }
  };

  if (loading) {
    return <div>Загрузка…</div>;
  }

  if (!article) {
    return <div className="text-sm text-muted-foreground">Статья не найдена.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">{article.wordstat}</h1>
          <div className="text-sm text-muted-foreground">{formatDate(article.created_at)}</div>
        </div>
        <div className="flex items-center gap-2">
          {savingChoices ? <span className="text-xs text-muted-foreground">Сохранение…</span> : null}
          <Badge className={`${STATUS_STYLES[article.status] ?? ''} text-xs font-medium`}>
            {STATUS_LABELS[article.status] ?? article.status}
          </Badge>
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as typeof activeTab)}>
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="wordstat">0) wordstat</TabsTrigger>
          <TabsTrigger value="context">1) Контекст</TabsTrigger>
          <TabsTrigger value="structure">2) Структура</TabsTrigger>
          <TabsTrigger value="seo">3) SEO блоки</TabsTrigger>
        </TabsList>

        <TabsContent value="wordstat" className="space-y-3">
          <div className="space-y-2">
            <div className="text-sm font-semibold">Wordstat</div>
            <Input value={wordstatDraft} onChange={(e) => setWordstatDraft(e.target.value)} />
          </div>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => void onSaveWordstat()} disabled={savingWordstat || !wordstatDraft.trim()}>
              {savingWordstat ? 'Сохраняем…' : 'Сохранить'}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="context" className="space-y-4">
          <div className="space-y-2">
            <div className="text-sm font-semibold">Целевая аудитория (для промптов)</div>
            <Textarea
              value={audienceDraft}
              onChange={(e) => setAudienceDraft(e.target.value)}
              className="min-h-20"
              placeholder="Кто читатель? (роль/уровень/контекст)"
            />
            <div className="flex flex-wrap gap-3">
              <Button onClick={() => void onSaveAudience()} disabled={savingAudience}>
                {savingAudience ? 'Сохраняем…' : 'Сохранить аудиторию'}
              </Button>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <ToggleList
              title="Почему пользователь это ищет именно сейчас?"
              items={whyNowOptions}
              selected={whyNowSelected}
              onChange={setWhyNowSelected}
            />
            <ToggleList
              title="К какому решению его можно подвести?"
              items={solutionOptions}
              selected={solutionSelected}
              onChange={setSolutionSelected}
            />
          </div>

          <div className="space-y-3 rounded-md border bg-background p-4">
            <div className="text-sm font-semibold">Какой продукт предложим?</div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">Lead</div>
                <Select
                  value={leadProductId ? String(leadProductId) : 'none'}
                  onValueChange={(value) => setLeadProductId(value === 'none' ? null : Number(value))}
                  disabled={productsLoading || generatingOutline}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={productsLoading ? 'Загрузка…' : 'Выберите lead продукт'} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— не выбирать —</SelectItem>
                    {leadProducts.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">Tripwire</div>
                <Select
                  value={tripwireProductId ? String(tripwireProductId) : 'none'}
                  onValueChange={(value) => setTripwireProductId(value === 'none' ? null : Number(value))}
                  disabled={productsLoading || generatingOutline}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={productsLoading ? 'Загрузка…' : 'Выберите tripwire продукт'} />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— не выбирать —</SelectItem>
                    {tripwireProducts.map((p) => (
                      <SelectItem key={p.id} value={String(p.id)}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => setActiveTab('structure')}>
              Дальше: структура
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="structure" className="space-y-3">
          <div className="space-y-2">
            <div className="text-sm font-semibold">Структура (редактируемая, без контента)</div>
            <Textarea
              value={outlineDraft}
              onChange={(e) => setOutlineDraft(e.target.value)}
              className="min-h-[360px]"
              placeholder="Здесь появится markdown-скелет статьи"
            />
          </div>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => void onSaveOutline()} disabled={savingOutline}>
              {savingOutline ? 'Сохраняем…' : 'Сохранить'}
            </Button>
            <Button onClick={() => void onGenerateOutline()} disabled={generatingOutline}>
              {generatingOutline ? 'Формируем…' : 'Сформировать структуру'}
            </Button>
          </div>
          {!outline ? (
            <div className="text-sm text-muted-foreground">
              Структура пока не сформирована — нажмите «Сформировать структуру».
            </div>
          ) : null}
        </TabsContent>

        <TabsContent value="seo" className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={async () => {
                setGeneratingBlueprint(true);
                try {
                  const updated = await articlesApi.generateSeoBlocks(articleId);
                  setArticle(updated);
                  await reloadBlocks();
                  toast.success('Blueprint обновлён');
                } catch (error) {
                  console.error('Failed to generate blueprint', error);
                  toast.error('Не удалось сгенерировать blueprint');
                } finally {
                  setGeneratingBlueprint(false);
                }
              }}
              disabled={generatingBlueprint}
            >
              {generatingBlueprint ? 'Генерируем blueprint…' : 'Сгенерировать blueprint'}
            </Button>
            {blocksLoading ? <div className="text-sm text-muted-foreground">Загрузка блоков…</div> : null}
          </div>
          <div className="text-sm text-muted-foreground">
            Blueprint — это фаза 1: AI генерирует для каждого блока подзапрос (H2), микро-интент и 1–2 ключа. Текст
            блоков не пишется.
          </div>

          {blocks.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              Пока нет SEO-блоков. Сначала сформируйте структуру во вкладке «2) Структура».
            </div>
          ) : (
            <div className="space-y-4">
              {blocks.map((block) => {
                const keywordsText = (block.keywords || []).join(', ');
                const onUpdateLocal = (next: Partial<ArticleBlock>) => {
                  setBlocks((prev) => prev.map((b) => (b.id === block.id ? { ...b, ...next } : b)));
                };

                const onSave = async () => {
                  setSavingBlockId(block.id);
                  try {
                    const updated = await articlesApi.updateBlock(articleId, {
                      block_id: block.id,
                      subquery_h2: block.subquery_h2,
                      micro_intent: block.micro_intent,
                      keywords: block.keywords,
                      prompt_template: block.prompt_template,
                      content: block.content,
                    });
                    setBlocks((prev) => prev.map((b) => (b.id === block.id ? updated : b)));
                    toast.success('Блок сохранён');
                  } catch (error) {
                    console.error('Failed to save block', error);
                    toast.error('Не удалось сохранить блок');
                  } finally {
                    setSavingBlockId(null);
                  }
                };

                const onGenerate = async () => {
                  setGeneratingBlockId(block.id);
                  try {
                    const updated = await articlesApi.generateBlock(articleId, block.id);
                    setBlocks((prev) => prev.map((b) => (b.id === block.id ? updated : b)));
                    toast.success('Блок сгенерирован');
                  } catch (error) {
                    console.error('Failed to generate block', error);
                    toast.error('Не удалось сгенерировать блок');
                  } finally {
                    setGeneratingBlockId(null);
                  }
                };

                return (
                  <div key={block.id} className="space-y-3 rounded-md border bg-background p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm font-semibold">
                        {block.order}. {block.block_key}
                      </div>
                      <div className="text-xs text-muted-foreground">статус: {block.status}</div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1">
                        <div className="text-sm text-muted-foreground">Подзапрос (H2)</div>
                        <Input
                          value={block.subquery_h2 || ''}
                          onChange={(e) => onUpdateLocal({ subquery_h2: e.target.value })}
                          placeholder="Например: что если продуктовая линейка отсутствует"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-sm text-muted-foreground">Ключи (1–2)</div>
                        <Input
                          value={keywordsText}
                          onChange={(e) => onUpdateLocal({ keywords: parseKeywordsCsv(e.target.value) })}
                          placeholder="ключ 1, ключ 2"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Микро-интент</div>
                      <Input
                        value={block.micro_intent || ''}
                        onChange={(e) => onUpdateLocal({ micro_intent: e.target.value })}
                        placeholder="Что читатель хочет понять/решить в этом блоке"
                      />
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">Текст блока (2–3 абзаца)</div>
                      <Textarea
                        value={block.content || ''}
                        onChange={(e) => onUpdateLocal({ content: e.target.value })}
                        className="min-h-28"
                        placeholder="Появится после генерации или можно написать вручную"
                      />
                    </div>

                    <details className="rounded-md border bg-muted/10 p-3">
                      <summary className="cursor-pointer text-sm font-medium">Корректировка</summary>
                      <div className="mt-3 space-y-2">
                        <div className="text-sm text-muted-foreground">
                          Этот текст добавляется к системному промпту блока (можно использовать {'{{var}}'}).
                        </div>
                        <Textarea
                          value={block.prompt_template || ''}
                          onChange={(e) => onUpdateLocal({ prompt_template: e.target.value })}
                          className="min-h-40"
                        />
                        {block.prompt_used ? (
                          <>
                            <div className="text-sm text-muted-foreground">Последний использованный промпт</div>
                            <pre className="whitespace-pre-wrap rounded-md border bg-background p-3 text-xs leading-5">
                              {block.prompt_used}
                            </pre>
                          </>
                        ) : null}
                      </div>
                    </details>

                    <div className="flex flex-wrap gap-3">
                      <Button onClick={() => void onSave()} disabled={savingBlockId === block.id}>
                        {savingBlockId === block.id ? 'Сохраняем…' : 'Сохранить'}
                      </Button>
                      <Button onClick={() => void onGenerate()} disabled={generatingBlockId === block.id}>
                        {generatingBlockId === block.id ? 'Генерируем…' : 'Сгенерировать блок'}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>
      </Tabs>

      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={() => router.push('/articles')}>
          Назад к списку
        </Button>
      </div>
    </div>
  );
}
