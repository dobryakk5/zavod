'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import type { Article, ArticleBlock, ArticleStatus, ClientProduct, ProductType } from '@/lib/types';
import { ApiError } from '@/lib/api';
import { articlesApi } from '@/lib/api/articles';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { RichTextEditor } from '@/components/ui/rich-text-editor';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { productTypesApi } from '@/lib/api/productTypes';
import { sanitizeRichText } from '@/lib/sanitize-html';
import { highlightPhrasesInHtml } from '@/lib/highlight-html';

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

function parsePhrases(raw: string): string[] {
  return (raw || '')
    .replace(/\r/g, '\n')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
}

const escapeHtml = (value: string) =>
  value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const extractPlainText = (html: string) => {
  if (!html) return '';
  if (typeof DOMParser === 'undefined') return html;
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');
  return doc.body.textContent || '';
};

const countPhraseMatches = (text: string, phrase: string) => {
  if (!text || !phrase) return 0;
  const regex = new RegExp(escapeRegExp(phrase), 'gi');
  return text.match(regex)?.length ?? 0;
};

const looksLikeHtml = (value: string) => /<\/?[a-z][\s\S]*>/i.test(value);

const applyInlineMarkdown = (value: string) => {
  let escaped = escapeHtml(value);
  escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  escaped = escaped.replace(/__(.+?)__/g, '<strong>$1</strong>');
  escaped = escaped.replace(/\*(.+?)\*/g, '<em>$1</em>');
  escaped = escaped.replace(/_(.+?)_/g, '<em>$1</em>');
  return escaped;
};

const renderMarkdownBlocks = (raw: string) => {
  const lines = (raw || '').replace(/\r/g, '').split('\n');
  const parts: string[] = [];
  let paragraph: string[] = [];
  let listType: 'ul' | 'ol' | null = null;
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (!paragraph.length) return;
    const html = paragraph.map((line) => applyInlineMarkdown(line.trim())).join('<br />');
    parts.push(`<p>${html}</p>`);
    paragraph = [];
  };

  const flushList = () => {
    if (!listType || !listItems.length) {
      listType = null;
      listItems = [];
      return;
    }
    const itemsHtml = listItems.map((item) => `<li>${applyInlineMarkdown(item)}</li>`).join('');
    parts.push(`<${listType}>${itemsHtml}</${listType}>`);
    listType = null;
    listItems = [];
  };

  const pushHeading = (level: number, text: string) => {
    if (parts.length) {
      parts.push('<br />');
    }
    const headingText = applyInlineMarkdown(text.toUpperCase());
    parts.push(`<h${level}><strong>${headingText}</strong></h${level}>`);
  };

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      pushHeading(headingMatch[1].length, headingMatch[2]);
      continue;
    }

    const orderedMatch = trimmed.match(/^\d+\.\s+(.*)$/);
    if (orderedMatch) {
      flushParagraph();
      if (listType !== 'ol') {
        flushList();
        listType = 'ol';
      }
      listItems.push(orderedMatch[1]);
      continue;
    }

    const unorderedMatch = trimmed.match(/^[-*•]\s+(.*)$/);
    if (unorderedMatch) {
      flushParagraph();
      if (listType !== 'ul') {
        flushList();
        listType = 'ul';
      }
      listItems.push(unorderedMatch[1]);
      continue;
    }

    flushList();
    paragraph.push(trimmed);
  }

  flushParagraph();
  flushList();
  return parts.join('');
};

const normalizeMarkdownToHtml = (raw: string) => {
  if (!raw) return '';
  if (looksLikeHtml(raw)) return raw;
  return renderMarkdownBlocks(raw);
};

const buildResultHtml = (items: ArticleBlock[]) => {
  const parts: string[] = [];
  for (const block of items) {
    const title = (block.h2_title || block.block_key || '').trim();
    const content = (block.content || '').trim();
    if (!title && !content) continue;
    if (title) {
      if (parts.length) {
        parts.push('<br />');
      }
      const headingText = applyInlineMarkdown(title.toUpperCase());
      parts.push(`<h2><strong>${headingText}</strong></h2>`);
    }
    if (content) {
      parts.push(renderMarkdownBlocks(content));
    }
  }
  return parts.join('');
};

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

  const [activeTab, setActiveTab] = useState<'wordstat' | 'context' | 'seo' | 'result'>('context');
  const initialTabSetRef = useRef(false);

  const [wordstatDraft, setWordstatDraft] = useState('');
  const [savingWordstat, setSavingWordstat] = useState(false);
  const [generatingContext, setGeneratingContext] = useState(false);
  const [resultDraft, setResultDraft] = useState('');
  const [savingResult, setSavingResult] = useState(false);
  const [resultTouched, setResultTouched] = useState(false);
  const [resultMode, setResultMode] = useState<'edit' | 'preview'>('edit');

  const [blocksLoading, setBlocksLoading] = useState(false);
  const [blocks, setBlocks] = useState<ArticleBlock[]>([]);
  const [savingBlockId, setSavingBlockId] = useState<number | null>(null);
  const [generatingBlockId, setGeneratingBlockId] = useState<number | null>(null);
  const [generatingBlueprint, setGeneratingBlueprint] = useState(false);
  const [generatingPhase2, setGeneratingPhase2] = useState(false);
  const [blueprintTaskId, setBlueprintTaskId] = useState<string | null>(null);
  const [phase2TaskId, setPhase2TaskId] = useState<string | null>(null);
  const [blockTaskId, setBlockTaskId] = useState<string | null>(null);

  const [productsLoading, setProductsLoading] = useState(false);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [types, setTypes] = useState<ProductType[]>([]);
  const [savingChoices, setSavingChoices] = useState(false);

  const [whyNowSelected, setWhyNowSelected] = useState<Set<string>>(new Set());
  const [solutionSelected, setSolutionSelected] = useState<Set<string>>(new Set());
  const [leadProductId, setLeadProductId] = useState<number | null>(null);
  const [tripwireProductId, setTripwireProductId] = useState<number | null>(null);

  const saveTimerRef = useRef<number | null>(null);
  const hydratedRef = useRef(false);
  const resultAutoRef = useRef<string | null>(null);
  const resultTabRef = useRef<HTMLDivElement | null>(null);

  const whyNowOptions = useMemo(() => ensureArray(article?.options_why_now), [article?.options_why_now]);
  const solutionOptions = useMemo(() => ensureArray(article?.options_solution), [article?.options_solution]);
  const orderedBlocks = useMemo(() => [...blocks].sort((a, b) => a.order - b.order), [blocks]);
  const wordstatPhrases = useMemo(() => {
    const phrases = new Set<string>();
    for (const phrase of article?.wordstat_phrases || []) {
      if (phrase && phrase.trim()) {
        phrases.add(phrase.trim());
      }
    }
    if (article?.wordstat) {
      phrases.add(article.wordstat);
    }
    for (const block of orderedBlocks) {
      for (const keyword of block.keywords || []) {
        if (keyword && keyword.trim()) {
          phrases.add(keyword.trim());
        }
      }
    }
    return Array.from(phrases);
  }, [article?.wordstat, article?.wordstat_phrases, orderedBlocks]);
  const normalizedResult = useMemo(() => normalizeMarkdownToHtml(resultDraft || ''), [resultDraft]);
  const sanitizedResult = useMemo(() => sanitizeRichText(normalizedResult), [normalizedResult]);
  const resultPreviewHtml = useMemo(
    () => highlightPhrasesInHtml(sanitizedResult, wordstatPhrases),
    [sanitizedResult, wordstatPhrases]
  );
  const wordstatClusterPhrases = useMemo(() => {
    const source = article?.wordstat_phrases?.length
      ? article.wordstat_phrases
      : parsePhrases(wordstatDraft);
    const seen = new Set<string>();
    return source
      .map((phrase) => phrase.trim())
      .filter((phrase) => {
        if (!phrase) return false;
        const key = phrase.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  }, [article?.wordstat_phrases, wordstatDraft]);
  const resultSeoStats = useMemo(() => {
    const plainText = extractPlainText(sanitizedResult);
    return wordstatPhrases
      .map((phrase) => ({
        phrase,
        count: countPhraseMatches(plainText, phrase),
      }))
      .sort((a, b) => b.count - a.count || a.phrase.localeCompare(b.phrase, 'ru'));
  }, [sanitizedResult, wordstatPhrases]);
  const blockTaskActive = blockTaskId !== null;
  const phaseBusy = generatingBlueprint || generatingPhase2 || blockTaskActive;
  const phase2ActiveBlockId = useMemo(() => {
    if (!generatingPhase2) return null;
    const next = orderedBlocks.find((block) => !block.content?.trim() && block.status !== 'failed');
    return next?.id ?? null;
  }, [generatingPhase2, orderedBlocks]);

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
        setResultDraft(normalizeMarkdownToHtml(data.result_html || ''));
        setResultTouched(false);
        setResultMode('edit');
        resultAutoRef.current = null;
        setWhyNowSelected(new Set(ensureArray(data.selected_why_now)));
        setSolutionSelected(new Set(ensureArray(data.selected_solution)));
        setLeadProductId(typeof data.lead_product_id === 'number' ? data.lead_product_id : null);
        setTripwireProductId(typeof data.tripwire_product_id === 'number' ? data.tripwire_product_id : null);
        if (!initialTabSetRef.current) {
          const hasSeoBlocks = Boolean(data.seo_blocks && Object.keys(data.seo_blocks).length > 0);
          const hasResult = Boolean(data.result_html && data.result_html.trim());
          const hasContextOptions = Boolean(
            (data.options_why_now && data.options_why_now.length > 0) ||
              (data.options_solution && data.options_solution.length > 0)
          );
          setActiveTab(
            hasResult ? 'result' : hasSeoBlocks ? 'seo' : data.status === 'wordstat' && !hasContextOptions ? 'wordstat' : 'context'
          );
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

  useEffect(() => {
    if (resultTouched) return;
    const hasContent = orderedBlocks.some((block) => block.content?.trim());
    if (!hasContent) return;
    const nextAuto = buildResultHtml(orderedBlocks);
    if (!nextAuto.trim()) return;
    if (!resultDraft.trim() || resultDraft === resultAutoRef.current) {
      setResultDraft(nextAuto);
      resultAutoRef.current = nextAuto;
    }
  }, [orderedBlocks, resultDraft, resultTouched]);

  const reloadBlocks = async () => {
    try {
      const data = await articlesApi.listBlocks(articleId);
      setBlocks(data);
    } catch (error) {
      console.error('Failed to reload blocks', error);
    }
  };

  useEffect(() => {
    if (!blueprintTaskId) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        const status = await articlesApi.generationStatus(blueprintTaskId);
        if (cancelled) return;
        if (status.status === 'success' || status.status === 'failure' || status.status === 'revoked') {
          setBlueprintTaskId(null);
          setGeneratingBlueprint(false);
          await reloadBlocks();
          const updated = await articlesApi.get(articleId);
          setArticle(updated);
          if (status.status !== 'success') {
            toast.error(status.error || 'Создание структуры завершилось с ошибкой');
          }
        }
      } catch (error) {
        console.error('Failed to fetch blueprint status', error);
      }
    };
    const intervalId = window.setInterval(() => {
      void poll();
    }, 2000);
    void poll();
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [articleId, blueprintTaskId]);

  useEffect(() => {
    if (!phase2TaskId) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        await reloadBlocks();
        const status = await articlesApi.generationStatus(phase2TaskId);
        if (cancelled) return;
        if (status.status === 'success' || status.status === 'failure' || status.status === 'revoked') {
          setPhase2TaskId(null);
          setGeneratingPhase2(false);
          await reloadBlocks();
          if (status.status === 'success') {
            const updated = await articlesApi.get(articleId);
            setArticle(updated);
          }
          if (status.status === 'success') {
            scrollToResult();
          }
          if (status.status !== 'success') {
            toast.error(status.error || 'Генерация блоков завершилась с ошибкой');
          }
        }
      } catch (error) {
        console.error('Failed to fetch phase 2 status', error);
      }
    };
    const intervalId = window.setInterval(() => {
      void poll();
    }, 2000);
    void poll();
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [articleId, phase2TaskId]);

  useEffect(() => {
    if (!blockTaskId) return;
    let cancelled = false;
    const poll = async () => {
      if (cancelled) return;
      try {
        await reloadBlocks();
        const status = await articlesApi.generationStatus(blockTaskId);
        if (cancelled) return;
        if (status.status === 'success' || status.status === 'failure' || status.status === 'revoked') {
          setBlockTaskId(null);
          setGeneratingBlockId(null);
          await reloadBlocks();
          if (status.status !== 'success') {
            toast.error(status.error || 'Генерация блока завершилась с ошибкой');
          }
        }
      } catch (error) {
        console.error('Failed to fetch block status', error);
      }
    };
    const intervalId = window.setInterval(() => {
      void poll();
    }, 2000);
    void poll();
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [articleId, blockTaskId]);

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

  const saveChoicesNow = async () => {
    if (!article) return;
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
  };

  const scheduleSave = () => {
    if (!article) return;
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
    }
    saveTimerRef.current = window.setTimeout(() => {
      void saveChoicesNow();
    }, 500);
  };

  const scrollToResult = () => {
    setActiveTab('result');
    window.requestAnimationFrame(() => {
      resultTabRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
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

  const onGenerateBlueprint = async () => {
    if (!article) return;
    if (phaseBusy) return;
    setGeneratingBlueprint(true);
    try {
      const response = await articlesApi.generateSeoBlocks(articleId);
      if (!response.task_id) {
        setGeneratingBlueprint(false);
        toast.error(response.error || 'Не удалось запустить создание структуры');
        return;
      }
      setBlueprintTaskId(response.task_id);
      toast.success('Создание структуры');
    } catch (error) {
      console.error('Failed to generate blueprint', error);
      setGeneratingBlueprint(false);
      toast.error('Не удалось создать структуру');
    }
  };

  const onGenerateAllBlocks = async () => {
    if (!article) return;
    if (phaseBusy) return;
    if (orderedBlocks.length === 0) {
      toast.error('Нет блоков для генерации');
      return;
    }
    setGeneratingPhase2(true);
    setGeneratingBlockId(null);
    setBlockTaskId(null);
    try {
      const response = await articlesApi.generateBlocks(articleId);
      if (!response.task_id) {
        setGeneratingPhase2(false);
        toast.error(response.error || 'Не удалось запустить фазу 2');
        return;
      }
      setPhase2TaskId(response.task_id);
      toast.success(response.message || 'Фаза 2 запущена');
    } catch (error) {
      console.error('Failed to generate all blocks', error);
      setGeneratingPhase2(false);
      toast.error('Не удалось запустить фазу 2');
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
      toast.success('Wordstat сохранён');
    } catch (error) {
      console.error('Failed to update wordstat', error);
      toast.error('Не удалось сохранить wordstat');
    } finally {
      setSavingWordstat(false);
    }
  };

  const onCreateContext = async () => {
    if (!article) return;
    const nextWordstat = wordstatDraft.trim();
    if (!nextWordstat) return;
    setGeneratingContext(true);
    try {
      if (nextWordstat !== (article.wordstat || '').trim()) {
        const updatedWordstat = await articlesApi.updateWordstat(articleId, nextWordstat);
        setArticle(updatedWordstat);
        setWordstatDraft(updatedWordstat.wordstat || nextWordstat);
      }
      const updated = await articlesApi.generateContext(articleId);
      setArticle(updated);
      toast.success('Контекст создан');
      setActiveTab('context');
    } catch (error) {
      console.error('Failed to generate context', error);
      toast.error('Не удалось создать контекст');
    } finally {
      setGeneratingContext(false);
    }
  };

  const onSaveResult = async () => {
    if (!article) return;
    setSavingResult(true);
    try {
      const normalized = sanitizeRichText(normalizeMarkdownToHtml(resultDraft || ''));
      const updated = await articlesApi.updateResult(articleId, normalized);
      setArticle(updated);
      setResultDraft(updated.result_html || normalized);
      setResultTouched(false);
      resultAutoRef.current = null;
      setResultMode('edit');
      toast.success('Результат сохранён');
    } catch (error) {
      console.error('Failed to update result', error);
      toast.error('Не удалось сохранить результат');
    } finally {
      setSavingResult(false);
    }
  };

  const onCompleteContext = async () => {
    if (!article) return;
    if (saveTimerRef.current) {
      window.clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    setActiveTab('seo');
    await saveChoicesNow();
    await onGenerateBlueprint();
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

      <Tabs
        value={activeTab}
        onValueChange={(v) => {
          const next = v as typeof activeTab;
          setActiveTab(next);
          if (next === 'result') {
            setResultMode('edit');
          }
        }}
      >
        <TabsList className="flex flex-wrap">
          <TabsTrigger value="wordstat">1) wordstat</TabsTrigger>
          <TabsTrigger value="context">2) Контекст</TabsTrigger>
          <TabsTrigger value="seo">3) SEO блоки</TabsTrigger>
          <TabsTrigger value="result">4) Результат</TabsTrigger>
        </TabsList>

        <TabsContent value="wordstat" className="space-y-3">
          <div className="space-y-2">
            <div className="text-sm font-semibold">Wordstat</div>
            <Input value={wordstatDraft} onChange={(e) => setWordstatDraft(e.target.value)} />
          </div>
          <div className="space-y-2 rounded-md border bg-background p-4">
            <div className="text-sm font-semibold">Найденный кластер</div>
            {wordstatClusterPhrases.length > 1 ? (
              <div className="flex flex-wrap gap-2">
                {wordstatClusterPhrases.map((phrase) => (
                  <Badge key={phrase} className="bg-slate-100 text-slate-700">
                    {phrase}
                  </Badge>
                ))}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">
                Кластер не найден — используем основной запрос.
              </div>
            )}
          </div>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => void onSaveWordstat()} disabled={savingWordstat || !wordstatDraft.trim()}>
              {savingWordstat ? 'Сохраняем…' : 'Сохранить'}
            </Button>
            <Button
              variant="outline"
              onClick={() => void onCreateContext()}
              disabled={generatingContext || savingWordstat || !wordstatDraft.trim()}
            >
              {generatingContext ? 'Создаём контекст…' : 'Создать контекст'}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="context" className="space-y-4">
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
                  disabled={productsLoading}
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
                  disabled={productsLoading}
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
            <Button
              variant="outline"
              onClick={() => void onCompleteContext()}
              disabled={savingChoices || generatingBlueprint}
            >
              {generatingBlueprint ? 'Создаём структуру…' : 'Дальше: Создать структуру'}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="seo" className="space-y-4">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => void onGenerateBlueprint()} disabled={phaseBusy}>
                Фаза 1: структура
              </Button>
              <div className="text-sm text-muted-foreground">
                AI генерирует для каждого блока подзапрос (H2), микро-интент и ключевые фразы. Текст блоков не пишется.
              </div>
              {blocksLoading ? <div className="text-sm text-muted-foreground">Загрузка блоков…</div> : null}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={() => void onGenerateAllBlocks()} disabled={phaseBusy}>
                Фаза 2
              </Button>
              <div className="text-sm text-muted-foreground">Сгенерировать текст для всех блоков.</div>
            </div>
          </div>

          {blocks.length === 0 ? (
            <div className="text-sm text-muted-foreground">
              Пока нет SEO-блоков. Заполните контекст и нажмите «Дальше: Создать структуру».
            </div>
          ) : (
            <div className="space-y-4">
              {orderedBlocks.map((block) => {
                const keywordsText = (block.keywords || []).join(', ');
                const onUpdateLocal = (next: Partial<ArticleBlock>) => {
                  setBlocks((prev) => prev.map((b) => (b.id === block.id ? { ...b, ...next } : b)));
                };

                const onSave = async () => {
                  setSavingBlockId(block.id);
                  try {
                    const updated = await articlesApi.updateBlock(articleId, {
                      block_id: block.id,
                      h2_title: block.h2_title,
                      subquery: block.subquery,
                      micro_intent: block.micro_intent,
                      keywords: block.keywords,
                      key_points: block.key_points,
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
                  if (generatingPhase2) return;
                  setGeneratingBlockId(block.id);
                  try {
                    const response = await articlesApi.generateBlock(articleId, block.id);
                    if (!response.task_id) {
                      setGeneratingBlockId(null);
                      toast.error(response.error || 'Не удалось запустить генерацию блока');
                      return;
                    }
                    setBlockTaskId(response.task_id);
                    toast.success(response.message || 'Генерация блока запущена');
                  } catch (error) {
                    console.error('Failed to generate block', error);
                    setGeneratingBlockId(null);
                    toast.error('Не удалось сгенерировать блок');
                  }
                };

                return (
                  <div key={block.id} className="space-y-3 rounded-md border bg-background p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm font-semibold flex items-center gap-2">
                        <span>
                          {block.order}. {block.block_key}
                        </span>
                        {generatingBlockId === block.id || phase2ActiveBlockId === block.id ? (
                          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                        ) : null}
                      </div>
                      <div className="text-xs text-muted-foreground">статус: {block.status}</div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="space-y-1">
                        <div className="text-sm text-muted-foreground">Подзаголовок — для человека и SEO</div>
                        <Input
                          value={block.h2_title || ''}
                          onChange={(e) => onUpdateLocal({ h2_title: e.target.value })}
                          placeholder="Например: как понять, что система не работает"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-sm text-muted-foreground">
                          Подзапрос — конкретный пользовательский вопрос, который раскрывает блок
                        </div>
                        <Input
                          value={block.subquery || ''}
                          onChange={(e) => onUpdateLocal({ subquery: e.target.value })}
                          placeholder="Например: почему у меня нет стабильного потока лидов"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-sm text-muted-foreground">
                          Интент — когнитивная задача блока (логика)
                        </div>
                        <Input
                          value={block.micro_intent || ''}
                          onChange={(e) => onUpdateLocal({ micro_intent: e.target.value })}
                          placeholder="Что читатель хочет понять/решить в этом блоке"
                        />
                      </div>
                      <div className="space-y-1">
                        <div className="text-sm text-muted-foreground">
                          Wordstat-кластер - 1 основная фраза (и еще парочка)
                        </div>
                        <Input
                          value={keywordsText}
                          onChange={(e) => onUpdateLocal({ keywords: parseKeywordsCsv(e.target.value) })}
                          placeholder="ключ 1, ключ 2"
                        />
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="text-sm text-muted-foreground">
                        Важные моменты — 3–6 ключевых смыслов, которые должны быть раскрыты
                      </div>
                      <Textarea
                        value={block.key_points || ''}
                        onChange={(e) => onUpdateLocal({ key_points: e.target.value })}
                        className="min-h-24"
                        placeholder="3–6 ключевых смыслов, по одному в строке"
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
                      <Button
                        onClick={() => void onGenerate()}
                        disabled={generatingBlockId === block.id || generatingPhase2 || blockTaskActive}
                      >
                        {generatingBlockId === block.id ? 'Генерируем…' : 'Сгенерировать блок'}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </TabsContent>

        <TabsContent value="result" className="space-y-4" ref={resultTabRef}>
          {resultMode === 'edit' ? (
            <>
              <div className="space-y-2">
                <div className="text-sm font-semibold">Редактирование</div>
                <RichTextEditor
                  value={resultDraft}
                  onChange={(value) => {
                    setResultDraft(value);
                    setResultTouched(true);
                    resultAutoRef.current = null;
                  }}
                  placeholder="Соберите результат статьи и выделяйте важное"
                />
              </div>

              <div className="flex flex-wrap gap-3">
                <Button onClick={() => void onSaveResult()} disabled={savingResult}>
                  {savingResult ? 'Сохраняем…' : 'Сохранить результат'}
                </Button>
                <Button variant="outline" onClick={() => setResultMode('preview')}>
                  Просмотр SEO
                </Button>
              </div>
            </>
          ) : (
            <>
              <div className="space-y-2">
                <div className="text-sm font-semibold">Просмотр SEO</div>
                {resultPreviewHtml ? (
                  <div
                    className="prose max-w-none whitespace-pre-wrap break-words rounded-md border bg-background p-4 text-gray-900"
                    dangerouslySetInnerHTML={{ __html: resultPreviewHtml }}
                  />
                ) : (
                  <div className="text-sm text-muted-foreground">
                    Пока нет текста. Сгенерируйте блоки или заполните результат вручную.
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="text-sm font-semibold">Статистика SEO</div>
                {resultSeoStats.length ? (
                  <div className="space-y-2">
                    {resultSeoStats.map((item) => (
                      <div key={item.phrase} className="flex items-center justify-between rounded-md border px-3 py-2">
                        <div className="text-sm">{item.phrase}</div>
                        <div className="text-sm font-semibold">{item.count}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-sm text-muted-foreground">Нет фраз для подсчёта.</div>
                )}
              </div>

              <div className="flex flex-wrap gap-3">
                <Button variant="outline" onClick={() => setResultMode('edit')}>
                  Вернуться к редактированию
                </Button>
              </div>
            </>
          )}
        </TabsContent>
      </Tabs>

      <div className="flex flex-wrap gap-3">
        <Button onClick={scrollToResult}>К результату</Button>
        <Button variant="outline" onClick={() => router.push('/articles')}>
          Назад к списку
        </Button>
      </div>
    </div>
  );
}
