'use client';

import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Save, Trash2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { mindMapsApi } from '@/lib/api/mindmaps';
import type { MindMapDetail, MindNodeProperty } from '@/lib/types';

type NodeFormState = {
  title: string;
  typeLabel: string;
  meta: Record<string, unknown>;
};

type PropertyDraft = {
  key: string;
  id?: number;
  title: string;
  value: string;
  delta: string;
  order_index: number;
  deleted?: boolean;
};

function useIsMobile() {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const mql = window.matchMedia('(max-width: 768px)');
    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => setIsMobile(e.matches);
    handleChange(mql);
    mql.addEventListener('change', handleChange as EventListener);
    return () => mql.removeEventListener('change', handleChange as EventListener);
  }, []);

  return isMobile;
}

const INPUT_CLASS = 'border-slate-300 bg-white text-black placeholder:text-slate-400';

const toDrafts = (props: MindNodeProperty[]): PropertyDraft[] =>
  [...props]
    .sort((a, b) => (a.order_index ?? 0) - (b.order_index ?? 0))
    .map((p) => ({
      key: String(p.id),
      id: p.id,
      title: p.title ?? '',
      value: p.value ?? '',
      delta: p.delta ?? '',
      order_index: p.order_index ?? 0
    }));

export default function EditNodePage() {
  const { mapId, nodeId } = useParams<{ mapId: string; nodeId: string }>();
  const router = useRouter();
  const isMobile = useIsMobile();

  const [mapData, setMapData] = useState<MindMapDetail | null>(null);
  const [form, setForm] = useState<NodeFormState>({ title: '', typeLabel: '', meta: {} });
  const [properties, setProperties] = useState<PropertyDraft[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saveTimerRef = useRef<number | null>(null);
  const lastSavedNodeRef = useRef<{ title: string; typeLabel: string } | null>(null);

  const node = useMemo(() => mapData?.nodes.find((n) => String(n.id) === String(nodeId)), [mapData?.nodes, nodeId]);
  const productId = useMemo(() => {
    const meta = node?.meta && typeof node.meta === 'object' ? (node.meta as Record<string, unknown>) : null;
    if (!meta || meta.entity !== 'product') return null;
    const raw = meta.product_id;
    if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
    if (typeof raw === 'string') {
      const parsed = Number.parseInt(raw, 10);
      return Number.isNaN(parsed) ? null : parsed;
    }
    return null;
  }, [node?.meta]);
  const isWebsiteNode = useMemo(() => {
    const entity = node?.meta && typeof node.meta === 'object' ? (node.meta as Record<string, unknown>).entity : undefined;
    return entity === 'website';
  }, [node?.meta]);

  const saveNodeNow = useCallback(
    async (next: { title: string; typeLabel: string }) => {
      if (!mapId || !nodeId) return;
      if (!next.title.trim()) return;
      setSaving(true);
      setError(null);
      try {
        const meta = {
          ...(form.meta ?? {}),
          metric_type: next.typeLabel || undefined,
          ...(isWebsiteNode ? { page_title: next.title } : {}),
        };
        await mindMapsApi.updateNode(Number(mapId), nodeId, { text: next.title, meta });
        lastSavedNodeRef.current = { title: next.title, typeLabel: next.typeLabel };
      } catch (err) {
        console.error('Failed to save node', err);
        setError('Не удалось сохранить изменения');
      } finally {
        setSaving(false);
      }
    },
    [form.meta, isWebsiteNode, mapId, nodeId]
  );

  const load = useCallback(async () => {
    if (!mapId || !nodeId) return;
    setLoading(true);
    setError(null);
    try {
      const detail = await mindMapsApi.detail(mapId);
      setMapData(detail);
      const currentNode = detail.nodes.find((n) => String(n.id) === String(nodeId));
      if (!currentNode) {
        setError('Узел не найден в карте');
        return;
      }

      const meta = (currentNode.meta ?? {}) as Record<string, unknown>;
      const websiteTitleRaw =
        (typeof meta.page_title === 'string' && meta.page_title.trim()) ||
        (typeof meta.title === 'string' && meta.title.trim()) ||
        '';
      const websiteTitle = websiteTitleRaw || currentNode.text;

      const websiteUrlRaw =
        (typeof meta.metric_type === 'string' && meta.metric_type.trim() && meta.metric_type !== 'url' ? meta.metric_type.trim() : '') ||
        (typeof meta.page_url === 'string' && meta.page_url.trim() ? meta.page_url.trim() : '') ||
        (typeof meta.url === 'string' && meta.url.trim() ? meta.url.trim() : '');

      setForm({
        title: typeof meta.entity === 'string' && meta.entity === 'website' ? websiteTitle : currentNode.text,
        typeLabel:
          typeof meta.entity === 'string' && meta.entity === 'website'
            ? websiteUrlRaw
            : (typeof meta.metric_type === 'string' && meta.metric_type) || '',
        meta: (currentNode.meta ?? {}) as Record<string, unknown>
      });
      lastSavedNodeRef.current = {
        title: typeof meta.entity === 'string' && meta.entity === 'website' ? websiteTitle : currentNode.text,
        typeLabel:
          typeof meta.entity === 'string' && meta.entity === 'website'
            ? websiteUrlRaw
            : (typeof meta.metric_type === 'string' && meta.metric_type) || ''
      };
      setProperties(toDrafts(currentNode.properties ?? []));
    } catch (err) {
      console.error('Failed to load node', err);
      setError('Не удалось загрузить данные узла');
    } finally {
      setLoading(false);
    }
  }, [mapId, nodeId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (loading) return;
    if (!mapId || !nodeId) return;
    const lastSaved = lastSavedNodeRef.current;
    if (lastSaved && lastSaved.title === form.title && lastSaved.typeLabel === form.typeLabel) return;

    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      void saveNodeNow({ title: form.title, typeLabel: form.typeLabel });
    }, 500);

    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    };
  }, [form.title, form.typeLabel, loading, mapId, nodeId, saveNodeNow]);

  const updateDraft = (key: string, patch: Partial<PropertyDraft>) => {
    setProperties((prev) => prev.map((p) => (p.key === key ? { ...p, ...patch } : p)));
  };

  const persistDraft = useCallback(
    async (draft: PropertyDraft) => {
      if (!nodeId) return;
      if (draft.deleted) return;

      const title = draft.title.trim();
      const value = draft.value.trim();
      const delta = draft.delta.trim() || undefined;
      const order_index = draft.order_index || 0;

      if (draft.id) {
        setSaving(true);
        setError(null);
        try {
          await mindMapsApi.updateProperty(draft.id, { title, value, delta, order_index });
        } catch (err) {
          console.error('Failed to update property', err);
          setError('Не удалось сохранить свойства');
        } finally {
          setSaving(false);
        }
        return;
      }

      if (!title) return;
      setSaving(true);
      setError(null);
      try {
        const created = (await mindMapsApi.createProperty({ node: nodeId, title, value, delta, order_index })) as unknown as { id?: number };
        if (typeof created?.id === 'number') {
          updateDraft(draft.key, { id: created.id });
        } else {
          await load();
        }
      } catch (err) {
        console.error('Failed to create property', err);
        setError('Не удалось сохранить свойства');
      } finally {
        setSaving(false);
      }
    },
    [load, nodeId]
  );

  const deleteDraft = useCallback(async (draft: PropertyDraft) => {
    if (!draft.id) {
      setProperties((prev) => prev.filter((p) => p.key !== draft.key));
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await mindMapsApi.deleteProperty(draft.id);
      setProperties((prev) => prev.filter((p) => p.key !== draft.key));
    } catch (err) {
      console.error('Failed to delete property', err);
      setError('Не удалось удалить свойство');
    } finally {
      setSaving(false);
    }
  }, []);

  const addPropertyRow = () => {
    setProperties((prev) => {
      const nextOrderIndex = prev.length ? Math.max(...prev.map((p) => p.order_index)) + 1 : 0;
      return [
        ...prev,
        {
          key: crypto.randomUUID(),
          title: '',
          value: '',
          delta: '',
          order_index: nextOrderIndex
        }
      ];
    });
  };

  const saveAll = async () => {
    if (!mapId || !nodeId) return;
    if (!form.title.trim()) {
      setError('Название не может быть пустым');
      return;
    }

    const newDrafts = properties.filter((p) => !p.deleted && !p.id);
    const hasInvalidNew = newDrafts.some((p) => !p.title.trim() && (p.value.trim() || p.delta.trim()));
    if (hasInvalidNew) {
      setError('У новых свойств нужно заполнить название');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const meta = {
        ...(form.meta ?? {}),
        metric_type: form.typeLabel || undefined,
        ...(isWebsiteNode ? { page_title: form.title } : {}),
      };
      await mindMapsApi.updateNode(Number(mapId), nodeId, { text: form.title, meta });

      const originalMap = new Map((node?.properties ?? []).map((p) => [p.id, p]));
      const deletions = properties.filter((p) => p.deleted && p.id).map((p) => p.id!) as number[];
      const creations = properties.filter((p) => !p.deleted && !p.id && p.title.trim());
      const updates = properties.filter((p) => !p.deleted && p.id) as Array<PropertyDraft & { id: number }>;

      await Promise.all([
        ...deletions.map((id) => mindMapsApi.deleteProperty(id)),
        ...creations.map((p) =>
          mindMapsApi.createProperty({
            node: nodeId,
            title: p.title.trim(),
            value: p.value.trim(),
            delta: p.delta.trim() || undefined,
            order_index: p.order_index || 0
          })
        ),
        ...updates
          .map((p) => {
            const original = originalMap.get(p.id);
            if (!original) return null;

            const nextDelta = p.delta.trim() || undefined;
            const originalDelta = original.delta ?? undefined;
            const nextOrder = p.order_index || 0;

            const isSame =
              original.title === p.title &&
              original.value === p.value &&
              originalDelta === nextDelta &&
              (original.order_index ?? 0) === nextOrder;

            if (isSame) return null;

            return mindMapsApi.updateProperty(p.id, {
              title: p.title,
              value: p.value,
              delta: nextDelta,
              order_index: nextOrder
            });
          })
          .filter(Boolean)
      ]);

      await load();
    } catch (err) {
      console.error('Failed to save node', err);
      setError('Не удалось сохранить изменения');
    } finally {
      setSaving(false);
    }
  };

  const content = (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <Button asChild variant="ghost" size="sm" className="text-black hover:bg-slate-100 hover:text-black">
          <Link href={`/map/${mapId}`} className="inline-flex items-center gap-2">
            <ArrowLeft className="h-4 w-4" />
            Назад к карте
          </Link>
        </Button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div>}
      {loading && <div className="text-sm text-black">Загрузка...</div>}

      {node && (
        <Card className="border-slate-200 bg-white text-black shadow-sm">
          <CardHeader>
            <CardTitle className="text-black">Узел</CardTitle>
          </CardHeader>

          <CardContent className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-sm text-black">Название</label>
                <Input
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                  onBlur={() => void saveNodeNow({ title: form.title, typeLabel: form.typeLabel })}
                  className={INPUT_CLASS}
                />
              </div>
              <div className="space-y-1">
                <label className="text-sm text-black">Тип</label>
                <Input
                  value={form.typeLabel}
                  onChange={(e) => !isWebsiteNode && setForm((p) => ({ ...p, typeLabel: e.target.value }))}
                  onBlur={() => void saveNodeNow({ title: form.title, typeLabel: form.typeLabel })}
                  readOnly={isWebsiteNode}
                  className={INPUT_CLASS}
                />
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center">
                <Button
                  type="button"
                  variant="outline"
                  className="border-slate-300 bg-white text-black hover:bg-slate-100 hover:text-black"
                  onClick={addPropertyRow}
                >
                  +Добавить свойство
                </Button>
              </div>

              <div className="grid gap-3">
                {properties
                  .filter((p) => !p.deleted)
                  .map((prop) => (
                    <div key={prop.key} className="rounded-lg border border-slate-200 bg-white p-3">
                      <div className="grid gap-2 sm:grid-cols-12 sm:items-center">
                        <Input
                          value={prop.title}
                          onChange={(e) => updateDraft(prop.key, { title: e.target.value })}
                          placeholder="Название"
                          className={`${INPUT_CLASS} sm:col-span-3`}
                        />
                        <Input
                          value={prop.value}
                          onChange={(e) => updateDraft(prop.key, { value: e.target.value })}
                          placeholder="Значение"
                          className={`${INPUT_CLASS} sm:col-span-4`}
                        />
                        <Input
                          value={prop.delta}
                          onChange={(e) => updateDraft(prop.key, { delta: e.target.value })}
                          placeholder="Δ"
                          className={`${INPUT_CLASS} sm:col-span-3`}
                        />
                        <div className="flex items-center gap-2 sm:col-span-2 sm:justify-end">
                          <Input
                            value={prop.order_index}
                            type="number"
                            onChange={(e) => updateDraft(prop.key, { order_index: Number(e.target.value) || 0 })}
                            className="w-20 border-slate-300 bg-white text-black"
                          />
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="text-slate-700 hover:bg-slate-100 hover:text-black"
                            onClick={() => updateDraft(prop.key, { deleted: true })}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex items-center justify-between">
            {productId ? (
              <Button asChild variant="link" size="sm" className="px-0 text-black">
                <Link href={`/product/${productId}`}>Открыть продукт</Link>
              </Button>
            ) : (
              <span />
            )}
            <Button onClick={saveAll} disabled={saving || loading} className="bg-black text-white hover:bg-black/90">
              <Save className="mr-2 h-4 w-4" />
              {saving ? 'Сохранение...' : 'Сохранить'}
            </Button>
          </CardFooter>
        </Card>
      )}
    </div>
  );

  if (isMobile) return <div className="min-h-screen bg-white p-6 text-black">{content}</div>;

  return (
    <Dialog open onOpenChange={(open) => !open && router.push(`/map/${mapId}`)}>
      <DialogContent className="max-w-4xl bg-white text-black dark:bg-white dark:text-black [&>button]:text-black [&>button]:data-[state=open]:text-black dark:[&>button]:text-black dark:[&>button]:data-[state=open]:text-black">
        <DialogHeader>
          <DialogTitle className="text-black dark:text-black">Редактирование узла</DialogTitle>
          <DialogDescription className="text-black dark:text-black">
            Название, тип и свойства — одним блоком. Esc или клик вне — закрыть.
          </DialogDescription>
        </DialogHeader>
        {content}
      </DialogContent>
    </Dialog>
  );
}
