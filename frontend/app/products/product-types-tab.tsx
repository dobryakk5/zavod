'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { ProductType } from '@/lib/types';
import { ApiError } from '@/lib/api';
import { productTypesApi } from '@/lib/api/productTypes';
import { Copy, Loader2, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

type TypeDraft = {
  name: string;
  value: string;
  goal: string;
  dirty: boolean;
  saving: boolean;
  error: string | null;
  revision: number;
};

export function ProductTypesTab() {
  const router = useRouter();
  const [types, setTypes] = useState<ProductType[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createName, setCreateName] = useState('');
  const [createValue, setCreateValue] = useState('');
  const [createGoal, setCreateGoal] = useState('');
  const [creating, setCreating] = useState(false);
  const [duplicatingId, setDuplicatingId] = useState<number | null>(null);
  const [generatingId, setGeneratingId] = useState<number | null>(null);

  const [drafts, setDrafts] = useState<Record<number, TypeDraft>>({});
  const draftsRef = useRef(drafts);

  useEffect(() => {
    draftsRef.current = drafts;
  }, [drafts]);

  const syncDraftsFromTypes = (items: ProductType[]) => {
    setDrafts((prev) => {
      const next: Record<number, TypeDraft> = { ...prev };
      for (const type of items) {
        const existing = next[type.id];
        const freshName = type.name ?? '';
        const freshValue = type.value ?? '';
        const freshGoal = type.goal ?? '';
        if (!existing) {
          next[type.id] = {
            name: freshName,
            value: freshValue,
            goal: freshGoal,
            dirty: false,
            saving: false,
            error: null,
            revision: 0
          };
          continue;
        }

        if (!existing.dirty && !existing.saving) {
          next[type.id] = {
            ...existing,
            name: freshName,
            value: freshValue,
            goal: freshGoal,
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
        const data = await productTypesApi.list();
        setTypes(data);
        syncDraftsFromTypes(data);
      } catch (err: unknown) {
        console.error('Failed to load product types', err);
        if (err instanceof ApiError && err.status === 404) {
          setTypes([]);
          syncDraftsFromTypes([]);
          setError(null);
        } else {
          setError('Не удалось загрузить типы продуктов. Проверьте API /products/types/.');
        }
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const saveDraft = async (typeId: number) => {
    const current = draftsRef.current[typeId];
    if (!current || !current.dirty || current.saving) return;

    const savedRevision = current.revision;
    const name = current.name.trim();
    const value = current.value.trim();
    const goal = current.goal.trim();

    if (!name) {
      setDrafts((prev) => {
        const existing = prev[typeId];
        if (!existing) return prev;
        return { ...prev, [typeId]: { ...existing, error: 'Название не может быть пустым.' } };
      });
      return;
    }

    setDrafts((prev) => {
      const existing = prev[typeId];
      if (!existing || existing.saving) return prev;
      return { ...prev, [typeId]: { ...existing, saving: true, error: null } };
    });

    try {
      const updated = await productTypesApi.update(typeId, {
        name,
        value: value ? value : null,
        goal: goal ? goal : null
      });
      setTypes((prev) => prev.map((t) => (t.id === typeId ? { ...t, ...updated } : t)));
      setDrafts((prev) => {
        const existing = prev[typeId];
        if (!existing) return prev;
        const shouldClearDirty = existing.revision === savedRevision;
        return {
          ...prev,
          [typeId]: {
            ...existing,
            name: shouldClearDirty ? updated.name ?? name : existing.name,
            value: shouldClearDirty ? (updated.value ?? '') : existing.value,
            goal: shouldClearDirty ? (updated.goal ?? '') : existing.goal,
            dirty: shouldClearDirty ? false : existing.dirty,
            saving: false,
            error: null
          }
        };
      });
    } catch (err) {
      console.error('Failed to autosave product type', typeId, err);
      setDrafts((prev) => {
        const existing = prev[typeId];
        if (!existing) return prev;
        return { ...prev, [typeId]: { ...existing, saving: false, error: 'Не удалось сохранить. Повторим через 5 сек.' } };
      });
    }
  };

  useEffect(() => {
    const interval = setInterval(() => {
      const snapshot = draftsRef.current;
      for (const [id, draft] of Object.entries(snapshot)) {
        const typeId = Number(id);
        if (Number.isNaN(typeId)) continue;
        if (!draft?.dirty || draft.saving) continue;
        void saveDraft(typeId);
      }
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const handleCreate = async () => {
    const name = createName.trim();
    const value = createValue.trim();
    const goal = createGoal.trim();
    if (!name) return;
    setCreating(true);
    setError(null);
    try {
      const created = await productTypesApi.create({
        name,
        value: value ? value : null,
        goal: goal ? goal : null
      });
      const next = [created, ...types];
      setTypes(next);
      syncDraftsFromTypes(next);
      setCreateName('');
      setCreateValue('');
      setCreateGoal('');
    } catch (err) {
      console.error('Failed to create product type', err);
      setError('Не удалось создать тип продукта.');
    } finally {
      setCreating(false);
    }
  };

  const handleDuplicate = async (type: ProductType) => {
    if (duplicatingId) return;
    setDuplicatingId(type.id);
    setError(null);
    try {
      const created = await productTypesApi.create({
        name: `${type.name} (копия)`,
        value: type.value ?? null,
        goal: type.goal ?? null
      });
      const next = [created, ...types];
      setTypes(next);
      syncDraftsFromTypes(next);
    } catch (err) {
      console.error('Failed to duplicate product type', err);
      setError('Не удалось создать копию типа продукта.');
    } finally {
      setDuplicatingId(null);
    }
  };

  const handleDelete = async (typeId: number) => {
    const ok = window.confirm('Удалить тип продукта? Это действие нельзя отменить.');
    if (!ok) return;

    setError(null);
    const prev = types;
    setTypes((items) => items.filter((t) => t.id !== typeId));
    setDrafts((prevDrafts) => {
      const next = { ...prevDrafts };
      delete next[typeId];
      return next;
    });
    try {
      await productTypesApi.delete(typeId);
    } catch (err) {
      console.error('Failed to delete product type', err);
      setError('Не удалось удалить тип продукта.');
      setTypes(prev);
      syncDraftsFromTypes(prev);
    }
  };

  const handleGenerateProduct = async (type: ProductType) => {
    if (generatingId) return;
    setGeneratingId(type.id);
    setError(null);
    try {
      const created = await productTypesApi.generateProduct(type.id);
      toast.success('Продукт создан');
      router.push(`/product/${created.id}`);
    } catch (err) {
      console.error('Failed to generate product for type', type.id, err);
      if (err instanceof ApiError) {
        try {
          const payload = err.body ? JSON.parse(err.body) : null;
          const message = payload?.error || payload?.detail;
          if (message) {
            setError(String(message));
            return;
          }
        } catch {}
      }
      setError('Не удалось сгенерировать продукт.');
    } finally {
      setGeneratingId(null);
    }
  };

  const rows = useMemo(
    () =>
      types.map((type) => {
        const draft = drafts[type.id];
        return {
          type,
          name: draft?.name ?? type.name ?? '',
          value: draft?.value ?? type.value ?? '',
          goal: draft?.goal ?? type.goal ?? '',
          saving: draft?.saving ?? false,
          error: draft?.error ?? null
        };
      }),
    [drafts, types]
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-xl border bg-card/70 p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="Название типа продукта"
            value={createName}
            onChange={(e) => setCreateName(e.target.value)}
            className="w-full max-w-sm"
          />
          <Input
            placeholder="Ценность (опционально)"
            value={createValue}
            onChange={(e) => setCreateValue(e.target.value)}
            className="w-full max-w-sm"
          />
          <Input
            placeholder="Цель (опционально)"
            value={createGoal}
            onChange={(e) => setCreateGoal(e.target.value)}
            className="w-full max-w-sm"
          />
          <Button onClick={handleCreate} disabled={creating || !createName.trim()}>
            {creating ? 'Создание…' : 'Добавить тип'}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Введите название и нажмите «Добавить тип»
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading && <div className="text-sm text-muted-foreground">Загрузка типов…</div>}
      {!loading && !error && types.length === 0 && (
        <div className="rounded-lg border px-4 py-6 text-muted-foreground">
          Пока нет типов продуктов.
        </div>
      )}

      {rows.length > 0 && (
        <div className="rounded-xl border bg-card/70 shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Название</TableHead>
                <TableHead>Ценность</TableHead>
                <TableHead>Цель</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map(({ type, name, value, goal, saving, error: rowError }) => (
                <TableRow
                  key={type.id}
                >
                  <TableCell className="font-medium">
                    <Input
                      value={name}
                      onChange={(e) => {
                        const nextName = e.target.value;
                        setDrafts((prev) => {
                          const existing = prev[type.id] ?? {
                            name: type.name ?? '',
                            value: type.value ?? '',
                            goal: type.goal ?? '',
                            dirty: false,
                            saving: false,
                            error: null,
                            revision: 0
                          };
                          return {
                            ...prev,
                            [type.id]: {
                              ...existing,
                              name: nextName,
                              dirty: true,
                              error: null,
                              revision: existing.revision + 1
                            }
                          };
                        });
                      }}
                      onBlur={() => void saveDraft(type.id)}
                      className="h-9"
                      aria-invalid={rowError ? true : undefined}
                    />
                    {rowError ? <div className="mt-1 text-xs text-destructive">{rowError}</div> : null}
                  </TableCell>
                  <TableCell>
                    <Input
                      value={value}
                      onChange={(e) => {
                        const nextValue = e.target.value;
                        setDrafts((prev) => {
                          const existing = prev[type.id] ?? {
                            name: type.name ?? '',
                            value: type.value ?? '',
                            goal: type.goal ?? '',
                            dirty: false,
                            saving: false,
                            error: null,
                            revision: 0
                          };
                          return {
                            ...prev,
                            [type.id]: {
                              ...existing,
                              value: nextValue,
                              dirty: true,
                              error: null,
                              revision: existing.revision + 1
                            }
                          };
                        });
                      }}
                      onBlur={() => void saveDraft(type.id)}
                      className="h-9"
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      value={goal}
                      onChange={(e) => {
                        const nextGoal = e.target.value;
                        setDrafts((prev) => {
                          const existing = prev[type.id] ?? {
                            name: type.name ?? '',
                            value: type.value ?? '',
                            goal: type.goal ?? '',
                            dirty: false,
                            saving: false,
                            error: null,
                            revision: 0
                          };
                          return {
                            ...prev,
                            [type.id]: {
                              ...existing,
                              goal: nextGoal,
                              dirty: true,
                              error: null,
                              revision: existing.revision + 1
                            }
                          };
                        });
                      }}
                      onBlur={() => void saveDraft(type.id)}
                      className="h-9"
                    />
                    {saving ? <div className="mt-1 text-xs text-muted-foreground">Сохранение…</div> : null}
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        disabled={generatingId === type.id || duplicatingId === type.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleGenerateProduct(type);
                        }}
                        aria-label="Создать продукт"
                        title="Создать продукт"
                      >
                        {generatingId === type.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        disabled={duplicatingId === type.id || generatingId === type.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDuplicate(type);
                        }}
                        aria-label="Сделать копию"
                        title="Сделать копию"
                      >
                        {duplicatingId === type.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                        disabled={duplicatingId === type.id || generatingId === type.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDelete(type.id);
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
    </div>
  );
}
