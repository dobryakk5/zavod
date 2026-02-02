'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { mindMapsApi } from '@/lib/api/mindmaps';
import { ApiError } from '@/lib/api';
import type { MindMap } from '@/lib/types';
import { Copy, Loader2, Trash2 } from 'lucide-react';
import { ClientProductsTab } from './client-products-tab';
import { ProductTypesTab } from './product-types-tab';
import { SalesTab } from './sales-tab';
import { useTenantTimezone } from '@/lib/hooks';
import { formatInTenantTimezone } from '@/lib/timezone';

const formatDate = (iso: string | undefined, timeZone: string) =>
  iso
    ? formatInTenantTimezone(iso, timeZone, { dateStyle: 'medium' }) || '—'
    : '—';

type MapDraft = {
  title: string;
  description: string;
  dirty: boolean;
  saving: boolean;
  error: string | null;
  revision: number;
};

export default function ProductsPage() {
  const router = useRouter();
  const { timezone: tenantTimezone } = useTenantTimezone();
  const [maps, setMaps] = useState<MindMap[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createTitle, setCreateTitle] = useState('');
  const [createDescription, setCreateDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [duplicatingId, setDuplicatingId] = useState<number | null>(null);
  const [mapToDelete, setMapToDelete] = useState<{ id: number; title: string } | null>(null);
  const [deletingMapId, setDeletingMapId] = useState<number | null>(null);

  const [drafts, setDrafts] = useState<Record<number, MapDraft>>({});
  const draftsRef = useRef(drafts);

  useEffect(() => {
    draftsRef.current = drafts;
  }, [drafts]);

  const syncDraftsFromMaps = (items: MindMap[]) => {
    setDrafts((prev) => {
      const next: Record<number, MapDraft> = { ...prev };
      for (const map of items) {
        const existing = next[map.id];
        const freshTitle = map.title ?? '';
        const freshDescription = map.description ?? '';
        if (!existing) {
          next[map.id] = {
            title: freshTitle,
            description: freshDescription,
            dirty: false,
            saving: false,
            error: null,
            revision: 0
          };
          continue;
        }

        if (!existing.dirty && !existing.saving) {
          next[map.id] = {
            ...existing,
            title: freshTitle,
            description: freshDescription,
            error: null
          };
        }
      }
      return next;
    });
  };

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await mindMapsApi.list();
        const productMaps = data.filter((item) => (item.type ?? 'product') !== 'website');
        setMaps(productMaps);
        syncDraftsFromMaps(productMaps);
      } catch (err: unknown) {
        console.error('Failed to load mind maps', err);
        if (err instanceof ApiError && err.status === 404) {
          // Пока нет эндпоинта — показываем пустое состояние без ошибки
          setMaps([]);
          syncDraftsFromMaps([]);
          setError(null);
        } else {
          setError('Не удалось загрузить карты. Проверьте API /map/mind-maps/.');
        }
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const saveDraft = async (mapId: number) => {
    const current = draftsRef.current[mapId];
    if (!current || !current.dirty || current.saving) return;

    const savedRevision = current.revision;
    const title = current.title.trim();
    const description = current.description.trim();

    if (!title) {
      setDrafts((prev) => {
        const existing = prev[mapId];
        if (!existing) return prev;
        return { ...prev, [mapId]: { ...existing, error: 'Название не может быть пустым.' } };
      });
      return;
    }

    setDrafts((prev) => {
      const existing = prev[mapId];
      if (!existing || existing.saving) return prev;
      return { ...prev, [mapId]: { ...existing, saving: true, error: null } };
    });

    try {
      const updated = await mindMapsApi.update(mapId, {
        title,
        description: description ? description : null
      });

      setMaps((prev) => prev.map((m) => (m.id === mapId ? { ...m, ...updated } : m)));

      setDrafts((prev) => {
        const existing = prev[mapId];
        if (!existing) return prev;
        const shouldClearDirty = existing.revision === savedRevision;
        return {
          ...prev,
          [mapId]: {
            ...existing,
            title: shouldClearDirty ? updated.title ?? title : existing.title,
            description: shouldClearDirty ? (updated.description ?? '') : existing.description,
            dirty: shouldClearDirty ? false : existing.dirty,
            saving: false,
            error: null
          }
        };
      });
    } catch (err) {
      console.error('Failed to autosave map', mapId, err);
      setDrafts((prev) => {
        const existing = prev[mapId];
        if (!existing) return prev;
        return { ...prev, [mapId]: { ...existing, saving: false, error: 'Не удалось сохранить. Повторим через 5 сек.' } };
      });
    }
  };

  useEffect(() => {
    const interval = setInterval(() => {
      const snapshot = draftsRef.current;
      for (const [id, draft] of Object.entries(snapshot)) {
        const mapId = Number(id);
        if (Number.isNaN(mapId)) continue;
        if (!draft?.dirty || draft.saving) continue;
        void saveDraft(mapId);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const handleDuplicateMap = async (mapId: number) => {
    if (duplicatingId) return;
    setDuplicatingId(mapId);
    setError(null);
    let createdMapId: number | null = null;

    try {
      const source = await mindMapsApi.detail(mapId);
      const createdMap = await mindMapsApi.create({
        title: `${source.title} (копия)`,
        description: source.description ?? undefined,
        is_public: source.is_public
      });
      createdMapId = Number(createdMap.id);

      const nodeIdMap = new Map<string, string>();

      for (const node of source.nodes ?? []) {
        const createdNode = await mindMapsApi.createNode(Number(createdMap.id), {
          map_id: Number(createdMap.id),
          text: node.text,
          color: node.color ?? null,
          shape: node.shape ?? null,
          meta: node.meta ?? {}
        });
        nodeIdMap.set(String(node.id), String(createdNode.id));

        if (node.position) {
          await mindMapsApi.upsertPosition(String(createdNode.id), {
            layout_name: node.position.layout_name,
            x: node.position.x,
            y: node.position.y
          });
        }

        for (const prop of node.properties ?? []) {
          await mindMapsApi.createProperty({
            node: String(createdNode.id),
            title: prop.title,
            value: prop.value,
            delta: prop.delta ?? undefined,
            order_index: prop.order_index ?? 0,
            meta: prop.meta ?? undefined
          });
        }
      }

      for (const edge of source.edges ?? []) {
        const fromId = nodeIdMap.get(String(edge.from_node_id));
        const toId = nodeIdMap.get(String(edge.to_node_id));
        if (!fromId || !toId) continue;
        await mindMapsApi.createEdge(Number(createdMap.id), {
          map_id: Number(createdMap.id),
          from_node_id: fromId,
          to_node_id: toId,
          type: edge.type ?? 'default',
          label: edge.label ?? null,
          meta: edge.meta ?? {}
        });
      }

      const updated = await mindMapsApi.list();
      setMaps(updated);
      syncDraftsFromMaps(updated);
    } catch (err) {
      console.error('Failed to duplicate map', err);
      if (createdMapId) {
        try {
          await mindMapsApi.delete(createdMapId);
        } catch (cleanupErr) {
          console.warn('Failed to cleanup duplicated map after error', cleanupErr);
        }
      }
      setError('Не удалось создать копию карты.');
    } finally {
      setDuplicatingId(null);
    }
  };

  const handleDeleteMapConfirm = async () => {
    if (!mapToDelete || deletingMapId) return;
    const mapId = mapToDelete.id;
    setError(null);
    setDeletingMapId(mapId);
    const prevMaps = maps;
    const prevDrafts = draftsRef.current;

    setMaps((prev) => prev.filter((m) => m.id !== mapId));
    setDrafts((prev) => {
      const next = { ...prev };
      delete next[mapId];
      return next;
    });

    try {
      await mindMapsApi.delete(mapId);
      setMapToDelete(null);
    } catch (err) {
      console.error('Failed to delete map', err);
      setError('Не удалось удалить карту.');
      setMaps(prevMaps);
      setDrafts(prevDrafts);
      setMapToDelete(null);
    } finally {
      setDeletingMapId(null);
    }
  };

  const handleCreate = async () => {
    if (!createTitle.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const created = await mindMapsApi.create({ title: createTitle.trim(), description: createDescription.trim() || undefined });
      const rootId = crypto.randomUUID();
      await mindMapsApi.createNode(Number(created.id), {
        id: rootId,
        map_id: Number(created.id),
        text: createTitle.trim(),
        meta: { metric_type: 'Root' }
      });
      router.push(`/map/${created.id}`);
    } catch (err) {
      console.error('Failed to create map', err);
      setError('Не удалось создать карту. Проверьте авторизацию и API.');
    } finally {
      setCreating(false);
    }
  };

  const rows = useMemo(
    () =>
      maps.map((map) => {
        const draft = drafts[map.id];
        return {
          map,
          title: draft?.title ?? map.title ?? '',
          description: draft?.description ?? map.description ?? '',
          saving: draft?.saving ?? false,
          error: draft?.error ?? null
        };
      }),
    [drafts, maps]
  );
  const isDeleteDialogOpen = mapToDelete != null;

  return (
    <div className="space-y-8">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground uppercase">Продукты</p>
          <h1 className="text-3xl font-bold">Продукты</h1>
          <p className="text-muted-foreground">
            Управляйте продуктовой картой и списком продуктов клиента.
          </p>
        </div>
      </div>

      <Tabs defaultValue="list" className="space-y-6">
        <TabsList>
          <TabsTrigger value="list">Список продуктов</TabsTrigger>
          <TabsTrigger value="types">Типы продуктов</TabsTrigger>
          <TabsTrigger value="sales">Продажи</TabsTrigger>
          <TabsTrigger value="maps">Продуктовая карта</TabsTrigger>
        </TabsList>

        <TabsContent value="list">
          <ClientProductsTab />
        </TabsContent>

        <TabsContent value="types">
          <ProductTypesTab />
        </TabsContent>

        <TabsContent value="sales">
          <SalesTab />
        </TabsContent>

        <TabsContent value="maps" className="space-y-8">
          <div className="flex flex-col gap-3 rounded-xl border bg-card/70 p-4 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <Input
                placeholder="Название карты"
                value={createTitle}
                onChange={(e) => setCreateTitle(e.target.value)}
                className="w-full max-w-sm"
              />
              <Input
                placeholder="Описание (опционально)"
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
                className="w-full max-w-sm"
              />
              <Button onClick={handleCreate} disabled={creating || !createTitle.trim()}>
                {creating ? 'Создание…' : 'Создать карту'}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Введите название и нажмите «Создать карту»
            </p>
          </div>

          {error && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {error}
            </div>
          )}
          {loading && <div className="text-sm text-muted-foreground">Загрузка mind maps…</div>}
          {!loading && !error && maps.length === 0 && (
            <div className="rounded-lg border px-4 py-6 text-muted-foreground">
              Пока нет карт. 
            </div>
          )}

          {maps.length > 0 && (
            <div className="rounded-xl border bg-card/70 shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Название</TableHead>
                    <TableHead>Описание</TableHead>
                    <TableHead className="w-[180px]">Обновлено</TableHead>
                    <TableHead className="w-[120px] text-right">Действия</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map(({ map, title, description, saving, error: rowError }) => (
                    <TableRow
                      key={map.id}
                      className="cursor-pointer"
                      onClick={(e) => {
                        const target = e.target as HTMLElement | null;
                        if (target?.closest('input,textarea,button,a')) return;
                        router.push(`/map/${map.id}`);
                      }}
                    >
                      <TableCell className="font-medium">
                        <Input
                          value={title}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => {
                            const nextTitle = e.target.value;
                            setDrafts((prev) => {
                              const existing = prev[map.id] ?? {
                                title: map.title ?? '',
                                description: map.description ?? '',
                                dirty: false,
                                saving: false,
                                error: null,
                                revision: 0
                              };
                              return {
                                ...prev,
                                [map.id]: {
                                  ...existing,
                                  title: nextTitle,
                                  dirty: true,
                                  error: null,
                                  revision: existing.revision + 1
                                }
                              };
                            });
                          }}
                          className="h-9"
                          aria-invalid={rowError ? true : undefined}
                        />
                        {rowError ? <div className="mt-1 text-xs text-destructive">{rowError}</div> : null}
                      </TableCell>
                      <TableCell>
                        <Input
                          value={description}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => {
                            const nextDescription = e.target.value;
                            setDrafts((prev) => {
                              const existing = prev[map.id] ?? {
                                title: map.title ?? '',
                                description: map.description ?? '',
                                dirty: false,
                                saving: false,
                                error: null,
                                revision: 0
                              };
                              return {
                                ...prev,
                                [map.id]: {
                                  ...existing,
                                  description: nextDescription,
                                  dirty: true,
                                  error: null,
                                  revision: existing.revision + 1
                                }
                              };
                            });
                          }}
                          className="h-9"
                        />
                        {saving ? <div className="mt-1 text-xs text-muted-foreground">Сохранение…</div> : null}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {formatDate(map.updated_at, tenantTimezone)}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="inline-flex items-center gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            disabled={duplicatingId === map.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              void handleDuplicateMap(map.id);
                            }}
                            aria-label="Сделать копию"
                            title="Сделать копию"
                          >
                            {duplicatingId === map.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                            disabled={duplicatingId === map.id || deletingMapId === map.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              setMapToDelete({ id: map.id, title: title.trim() || 'Без названия' });
                            }}
                            aria-label="Удалить"
                            title="Удалить"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          <Dialog
            open={isDeleteDialogOpen}
            onOpenChange={(open) => {
              if (!open && !deletingMapId) {
                setMapToDelete(null);
              }
            }}
          >
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Удалить карту?</DialogTitle>
                <DialogDescription>
                  {mapToDelete
                    ? `Карта «${mapToDelete.title}» будет удалена без возможности восстановления.`
                    : 'Карта будет удалена без возможности восстановления.'}
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setMapToDelete(null)}
                  disabled={Boolean(deletingMapId)}
                >
                  Отмена
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={() => void handleDeleteMapConfirm()}
                  disabled={Boolean(deletingMapId)}
                >
                  {deletingMapId ? 'Удаление…' : 'Удалить'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>
      </Tabs>
    </div>
  );
}
