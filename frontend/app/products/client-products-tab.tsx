'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { ClientProduct } from '@/lib/types';
import { ApiError } from '@/lib/api';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { mindMapsApi } from '@/lib/api/mindmaps';
import { productTypesApi } from '@/lib/api/productTypes';
import { Copy, Loader2, Trash2 } from 'lucide-react';
import { useTenantTimezone } from '@/lib/hooks';
import { formatInTenantTimezone } from '@/lib/timezone';

type PendingProduct = {
  id: number;
  name: string;
  product_type_id?: number | null;
  product_type_name?: string | null;
  short_description?: string | null;
  updated_at?: string;
  __pending: true;
  task_id: string;
};

type ProductRow = ClientProduct | PendingProduct;

const formatDate = (iso: string | undefined, timeZone: string) =>
  iso
    ? formatInTenantTimezone(iso, timeZone, { dateStyle: 'medium' }) || '—'
    : '—';

const resolveProductId = (result?: Record<string, unknown>) => {
  if (!result || typeof result !== 'object') return null;
  const raw = (result as { product_id?: unknown }).product_id;
  if (typeof raw === 'number' && Number.isFinite(raw)) return raw;
  if (typeof raw === 'string') {
    const parsed = Number.parseInt(raw, 10);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return null;
};

const isPendingProduct = (product: ProductRow): product is PendingProduct =>
  (product as PendingProduct).__pending === true;

export function ClientProductsTab() {
  const router = useRouter();
  const { timezone: tenantTimezone } = useTenantTimezone();
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [pendingProducts, setPendingProducts] = useState<PendingProduct[]>([]);
  const [types, setTypes] = useState<Array<{ id: number; name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createName, setCreateName] = useState('');
  const [createShortDescription, setCreateShortDescription] = useState('');
  const [filterTypeId, setFilterTypeId] = useState<number | null>(null);
  const [creatingManual, setCreatingManual] = useState(false);
  const [creatingAuto, setCreatingAuto] = useState(false);
  const [creatingAutoTaskId, setCreatingAutoTaskId] = useState<string | null>(null);
  const [creatingProductsMap, setCreatingProductsMap] = useState(false);

  const [duplicatingId, setDuplicatingId] = useState<number | null>(null);
  const [productToDelete, setProductToDelete] = useState<ClientProduct | null>(null);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const coreTypeId = useMemo(() => {
    const core = types.find((t) => t.name.trim().toLowerCase() === 'core');
    return core?.id ?? null;
  }, [types]);

  const coreTypeName = useMemo(() => {
    const core = types.find((t) => t.name.trim().toLowerCase() === 'core');
    return core?.name ?? 'Core';
  }, [types]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [data, typeData] = await Promise.all([clientProductsApi.list(), productTypesApi.list()]);
        setProducts(data);
        setTypes(typeData.map((t) => ({ id: t.id, name: t.name })));
      } catch (err: unknown) {
        console.error('Failed to load client products', err);
        if (err instanceof ApiError && err.status === 404) {
          setProducts([]);
          setError(null);
        } else {
          setError('Не удалось загрузить продукты. Проверьте API /products/list/ и /products/types/.');
        }
      } finally {
        setLoading(false);
      }
    };

    load();
  }, []);

  const openProduct = useCallback(
    (productId: number) => {
      router.push(`/product/${productId}`);
    },
    [router]
  );

  const handleCreateCoreManual = async () => {
    const name = createName.trim();
    const short_description = createShortDescription.trim();
    if (!name || !short_description) return;
    if (creatingManual || creatingAuto) return;
    setCreatingManual(true);
    setError(null);
    try {
      const created = await clientProductsApi.createCore({
        name,
        short_description
      });
      setProducts((prev) => [created, ...prev]);
      setCreateName('');
      setCreateShortDescription('');
      openProduct(created.id);
    } catch (err) {
      console.error('Failed to create core product', err);
      setError('Не удалось создать core-продукт.');
    } finally {
      setCreatingManual(false);
    }
  };

  const handleCreateCoreAuto = async () => {
    const name = createName.trim();
    const short_description = createShortDescription.trim();
    if (!name || !short_description) return;
    if (creatingManual || creatingAuto) return;
    setCreatingAuto(true);
    setError(null);
    let keepLoading = false;
    try {
      const response = await clientProductsApi.createCoreAi({
        name,
        short_description
      });
      const immediateProduct = response.product;
      if (immediateProduct?.id != null) {
        setProducts((prev) => (prev.some((item) => item.id === immediateProduct.id) ? prev : [immediateProduct, ...prev]));
        setCreateName('');
        setCreateShortDescription('');
        setCreatingAuto(false);
        return;
      }

      if (response.task_id) {
        keepLoading = true;
        const pending: PendingProduct = {
          id: -Date.now(),
          name,
          product_type_id: coreTypeId,
          product_type_name: coreTypeName,
          short_description,
          updated_at: new Date().toISOString(),
          __pending: true,
          task_id: response.task_id
        };
        setPendingProducts((prev) => [pending, ...prev]);
        setCreateName('');
        setCreateShortDescription('');
        setCreatingAutoTaskId(response.task_id);
        return;
      }

      setError(response.error ? String(response.error) : 'Не удалось запустить автогенерацию core-продукта.');
    } catch (err) {
      console.error('Failed to auto-create core product', err);
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
      setError('Не удалось создать core-продукт с помощью ИИ.');
    } finally {
      if (!keepLoading) {
        setCreatingAuto(false);
      }
    }
  };

  useEffect(() => {
    if (!creatingAutoTaskId) return;
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      try {
        const status = await clientProductsApi.generationStatus(creatingAutoTaskId);
        if (cancelled) return;

        if (status.status === 'success') {
          let created = status.product ?? null;
          if (!created) {
            const productId = resolveProductId(status.result);
            if (productId != null) {
              try {
                created = await clientProductsApi.detail(productId);
              } catch (err) {
                console.error('Failed to fetch created core product', err);
              }
            }
          }

          if (created?.id != null) {
            setProducts((prev) => (prev.some((item) => item.id === created!.id) ? prev : [created!, ...prev]));
            setPendingProducts((prev) => prev.filter((item) => item.task_id !== creatingAutoTaskId));
          } else {
            setError('Core-продукт создан, но не удалось получить его данные. Обновите список продуктов.');
            setPendingProducts((prev) => prev.filter((item) => item.task_id !== creatingAutoTaskId));
          }

          setCreatingAuto(false);
          setCreatingAutoTaskId(null);
          return;
        }

        if (status.status === 'failure' || status.status === 'revoked') {
          setError(status.error || 'Автогенерация core-продукта завершилась с ошибкой.');
          setPendingProducts((prev) => prev.filter((item) => item.task_id !== creatingAutoTaskId));
          setCreatingAuto(false);
          setCreatingAutoTaskId(null);
        }
      } catch (err) {
        console.error('Failed to fetch core product generation status', err);
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
  }, [creatingAutoTaskId]);

  const handleCreateProductsMap = async () => {
    if (creatingProductsMap) return;
    setCreatingProductsMap(true);
    setError(null);
    try {
      const created = await mindMapsApi.createProductsMap();
      router.push(`/map/${created.id}`);
    } catch (err) {
      console.error('Failed to create products map', err);
      setError('Не удалось создать карту всех продуктов.');
    } finally {
      setCreatingProductsMap(false);
    }
  };

  const handleDuplicate = async (product: ClientProduct) => {
    if (duplicatingId) return;
    if ((product.product_type_name ?? '').trim().toLowerCase() !== 'core') {
      setError('Сопутствующие продукты создаются внутри Core. В списке можно создавать/копировать только Core-продукты.');
      return;
    }
    setDuplicatingId(product.id);
    setError(null);
    try {
      const created = await clientProductsApi.create({
        name: `${product.name} (копия)`,
        product_type_id: product.product_type_id ?? null,
        short_description: product.short_description ?? null,
        packages: Array.isArray(product.packages) ? product.packages : []
      });
      setProducts((prev) => [created, ...prev]);
    } catch (err) {
      console.error('Failed to duplicate product', err);
      setError('Не удалось создать копию продукта.');
    } finally {
      setDuplicatingId(null);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!productToDelete || deletingId) return;
    const productId = productToDelete.id;
    setError(null);
    setDeletingId(productId);
    const prev = products;
    setProducts((items) => items.filter((p) => p.id !== productId));
    try {
      await clientProductsApi.delete(productId);
      setProductToDelete(null);
    } catch (err) {
      console.error('Failed to delete product', err);
      setError('Не удалось удалить продукт.');
      setProducts(prev);
      setProductToDelete(null);
    } finally {
      setDeletingId(null);
    }
  };

  const rows = useMemo(() => {
    const combined: ProductRow[] = [...pendingProducts, ...products];
    if (filterTypeId == null) return combined;
    return combined.filter((product) => product.product_type_id === filterTypeId);
  }, [filterTypeId, pendingProducts, products]);

  const hasAnyProducts = products.length > 0 || pendingProducts.length > 0;
  const coreOnboarding = !loading && !error && !hasAnyProducts;
  const canCreateCore = Boolean(createName.trim() && createShortDescription.trim());
  const isDeleteDialogOpen = productToDelete != null;

  useEffect(() => {
    if (coreTypeId == null) return;
    setPendingProducts((prev) =>
      prev.map((product) =>
        product.product_type_id == null
          ? { ...product, product_type_id: coreTypeId, product_type_name: product.product_type_name ?? coreTypeName }
          : product
      )
    );
  }, [coreTypeId, coreTypeName]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-xl border bg-card/70 p-4 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <Input
            placeholder="Название продукта"
            value={createName}
            onChange={(e) => setCreateName(e.target.value)}
            className="w-full max-w-sm"
          />
          <Input
            placeholder="Описание продукта"
            value={createShortDescription}
            onChange={(e) => setCreateShortDescription(e.target.value)}
            className="w-full max-w-sm"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={() => void handleCreateCoreAuto()}
              disabled={!canCreateCore || creatingAuto || creatingManual}
            >
              {creatingAuto ? (
                <span className="inline-flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Автопилот…
                </span>
              ) : (
                'Автопилот'
              )}
            </Button>
            <Button
              variant="secondary"
              onClick={() => void handleCreateCoreManual()}
              disabled={!canCreateCore || creatingManual || creatingAuto}
            >
              {creatingManual ? 'Создание…' : 'Вручную'}
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {coreOnboarding
            ? 'Создайте основной продукт (Core): заполните название и описание, затем выберите «Вручную» или «Автопилот».'
            : 'В общем списке создаем Core продукты. Внутри Core - всё остальное.'}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" onClick={() => void handleCreateProductsMap()} disabled={creatingProductsMap}>
          {creatingProductsMap ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Создание карты…
            </span>
          ) : (
            'Создать карту всех продуктов'
          )}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading && <div className="text-sm text-muted-foreground">Загрузка продуктов…</div>}
      {!loading && !error && !hasAnyProducts && (
        <div className="rounded-lg border px-4 py-6 text-muted-foreground">
          Пока нет продуктов. Создайте основной продукт (Core) через форму выше.
        </div>
      )}
      {!loading && !error && hasAnyProducts && rows.length === 0 && filterTypeId != null && (
        <div className="rounded-lg border px-4 py-6 text-muted-foreground">
          Нет продуктов выбранного типа.
        </div>
      )}

      {rows.length > 0 && (
        <div className="rounded-xl border bg-card/70 shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Название</TableHead>
                <TableHead className="w-[180px]">
                  <Select
                    value={filterTypeId == null ? 'all' : String(filterTypeId)}
                    onValueChange={(value) => setFilterTypeId(value === 'all' ? null : Number(value))}
                    disabled={loading}
                  >
                    <SelectTrigger className="h-9 w-full">
                      <SelectValue placeholder="Все типы" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">Все типы</SelectItem>
                      {types.map((t) => (
                        <SelectItem key={t.id} value={String(t.id)}>
                          {t.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableHead>
                <TableHead>Краткое описание</TableHead>
                <TableHead>Обновлено</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((product) => {
                const pending = isPendingProduct(product);
                return (
                <TableRow
                  key={product.id}
                  className={pending ? 'opacity-70' : 'cursor-pointer'}
                  onClick={(e) => {
                    if (pending) return;
                    const target = e.target as HTMLElement | null;
                    if (target?.closest('button,a')) return;
                    openProduct(product.id);
                  }}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      <span>{product.name}</span>
                      {pending && (
                        <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">Создается</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{product.product_type_name || '—'}</TableCell>
                  <TableCell className="text-muted-foreground">{product.short_description || '—'}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {formatDate(product.updated_at, tenantTimezone)}
                  </TableCell>
                  <TableCell className="text-right">
                    {pending ? (
                      <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Создается…
                      </div>
                    ) : (
                      <div className="inline-flex items-center gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          disabled={duplicatingId === product.id || (product.product_type_name ?? '').trim().toLowerCase() !== 'core'}
                          onClick={(e) => {
                            e.stopPropagation();
                            void handleDuplicate(product);
                          }}
                          aria-label="Сделать копию"
                          title={
                            (product.product_type_name ?? '').trim().toLowerCase() === 'core'
                              ? 'Сделать копию'
                              : 'Копирование сопутствующих продуктов доступно внутри Core'
                          }
                        >
                          {duplicatingId === product.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                          disabled={duplicatingId === product.id || deletingId === product.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            setProductToDelete(product);
                          }}
                          aria-label="Удалить"
                          title="Удалить"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              );
            })}
            </TableBody>
          </Table>
        </div>
      )}

      <Dialog
        open={isDeleteDialogOpen}
        onOpenChange={(open) => {
          if (!open && !deletingId) {
            setProductToDelete(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Удалить продукт?</DialogTitle>
            <DialogDescription>
              {productToDelete
                ? `Продукт «${productToDelete.name}» будет удален без возможности восстановления.`
                : 'Продукт будет удален без возможности восстановления.'}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setProductToDelete(null)}
              disabled={Boolean(deletingId)}
            >
              Отмена
            </Button>
            <Button type="button" variant="destructive" onClick={() => void handleDeleteConfirm()} disabled={Boolean(deletingId)}>
              {deletingId ? 'Удаление…' : 'Удалить'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
