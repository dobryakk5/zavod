'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { toast } from 'sonner';
import type { Article } from '@/lib/types';
import { ApiError } from '@/lib/api';
import { articlesApi } from '@/lib/api/articles';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { productTypesApi } from '@/lib/api/productTypes';
import type { ClientProduct, ProductType } from '@/lib/types';

function ensureArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item)).map((s) => s.trim()).filter(Boolean);
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

export default function ArticleNewPageClient() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const articleId = Number(params.id);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [article, setArticle] = useState<Article | null>(null);
  const [whyNowSelected, setWhyNowSelected] = useState<Set<string>>(new Set());
  const [solutionSelected, setSolutionSelected] = useState<Set<string>>(new Set());
  const [productsLoading, setProductsLoading] = useState(false);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [types, setTypes] = useState<ProductType[]>([]);
  const [leadProductId, setLeadProductId] = useState<number | null>(null);
  const [tripwireProductId, setTripwireProductId] = useState<number | null>(null);

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
        setWhyNowSelected(new Set(ensureArray(data.selected_why_now)));
        setSolutionSelected(new Set(ensureArray(data.selected_solution)));
        setLeadProductId(typeof data.lead_product_id === 'number' ? data.lead_product_id : null);
        setTripwireProductId(typeof data.tripwire_product_id === 'number' ? data.tripwire_product_id : null);
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
      }
    };

    void load();
  }, [articleId, router]);

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

  const onGenerateOutline = async () => {
    if (!article) return;
    setSubmitting(true);
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
      router.push(`/articles/${articleId}`);
    } catch (error) {
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
      console.error('Failed to generate outline', error);
      toast.error('Не удалось сформировать структуру статьи');
    } finally {
      setSubmitting(false);
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
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Создание статьи</h1>
        <div className="text-sm text-muted-foreground">Wordstat: {article.wordstat}</div>
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
              disabled={productsLoading || submitting}
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
              disabled={productsLoading || submitting}
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
        {!productsLoading && leadProducts.length === 0 && tripwireProducts.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            Не нашли продукты типов <span className="font-medium">lead</span> / <span className="font-medium">tripwire</span>. Проверьте значения
            в <span className="font-medium">Продукты → Типы продуктов</span>.
          </div>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-3">
        <Button onClick={onGenerateOutline} disabled={submitting}>
          {submitting ? 'Формируем структуру…' : 'Сформировать структуру'}
        </Button>
        <Button variant="outline" onClick={() => router.push('/articles')} disabled={submitting}>
          Назад к списку
        </Button>
      </div>
    </div>
  );
}
