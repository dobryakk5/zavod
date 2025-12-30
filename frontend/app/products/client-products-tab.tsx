'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { ClientProduct } from '@/lib/types';
import { ApiError } from '@/lib/api';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { productTypesApi } from '@/lib/api/productTypes';
import { Copy, Loader2, Trash2 } from 'lucide-react';

const formatDate = (iso?: string) =>
  iso ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium' }).format(new Date(iso)) : '—';

export function ClientProductsTab() {
  const router = useRouter();
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [types, setTypes] = useState<Array<{ id: number; name: string }>>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [createName, setCreateName] = useState('');
  const [createTypeId, setCreateTypeId] = useState<number | null>(null);
  const [createShortDescription, setCreateShortDescription] = useState('');
  const [creatingManual, setCreatingManual] = useState(false);
  const [creatingAuto, setCreatingAuto] = useState(false);

  const [duplicatingId, setDuplicatingId] = useState<number | null>(null);

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

  const openProduct = (productId: number) => {
    router.push(`/product/${productId}`);
  };

  const handleCreateRegular = async () => {
    const name = createName.trim();
    const short_description = createShortDescription.trim();
    if (!name) return;
    setCreatingManual(true);
    setError(null);
    try {
      const created = await clientProductsApi.create({
        name,
        product_type_id: createTypeId,
        short_description: short_description ? short_description : null,
        packages: []
      });
      setProducts((prev) => [created, ...prev]);
      setCreateName('');
      setCreateTypeId(null);
      setCreateShortDescription('');
      openProduct(created.id);
    } catch (err) {
      console.error('Failed to create product', err);
      setError('Не удалось создать продукт.');
    } finally {
      setCreatingManual(false);
    }
  };

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
      setCreateTypeId(null);
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
    try {
      const created = await clientProductsApi.createCoreAi({
        name,
        short_description
      });
      setProducts((prev) => [created, ...prev]);
      setCreateName('');
      setCreateTypeId(null);
      setCreateShortDescription('');
      openProduct(created.id);
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
      setCreatingAuto(false);
    }
  };

  const handleDuplicate = async (product: ClientProduct) => {
    if (duplicatingId) return;
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

  const handleDelete = async (productId: number) => {
    const ok = window.confirm('Удалить продукт? Это действие нельзя отменить.');
    if (!ok) return;

    setError(null);
    const prev = products;
    setProducts((items) => items.filter((p) => p.id !== productId));
    try {
      await clientProductsApi.delete(productId);
    } catch (err) {
      console.error('Failed to delete product', err);
      setError('Не удалось удалить продукт.');
      setProducts(prev);
    }
  };

  const rows = useMemo(() => {
    if (createTypeId == null) return products;
    return products.filter((product) => product.product_type_id === createTypeId);
  }, [createTypeId, products]);

  const coreOnboarding = !loading && !error && products.length === 0;
  const canCreateCore = Boolean(createName.trim() && createShortDescription.trim());

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
            placeholder={coreOnboarding ? 'Описание продукта' : 'Краткое описание (опционально)'}
            value={createShortDescription}
            onChange={(e) => setCreateShortDescription(e.target.value)}
            className="w-full max-w-sm"
          />
          {coreOnboarding ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => void handleCreateCoreManual()} disabled={!canCreateCore || creatingManual || creatingAuto}>
                {creatingManual ? 'Создание…' : 'Вручную'}
              </Button>
              <Button
                variant="secondary"
                onClick={() => void handleCreateCoreAuto()}
                disabled={!canCreateCore || creatingAuto || creatingManual}
              >
                {creatingAuto ? (
                  <span className="inline-flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Автомат…
                  </span>
                ) : (
                  'Автомат'
                )}
              </Button>
              <div className="text-xs text-muted-foreground">Тип: Core</div>
            </div>
          ) : (
            <>
              <div className="w-full max-w-sm">
                <Select
                  value={createTypeId == null ? 'none' : String(createTypeId)}
                  onValueChange={(value) => setCreateTypeId(value === 'none' ? null : Number(value))}
                  disabled={creatingManual}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Тип продукта (опционально)" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— Без типа —</SelectItem>
                    {types.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={() => void handleCreateRegular()} disabled={creatingManual || !createName.trim()}>
                {creatingManual ? 'Создание…' : 'Добавить продукт'}
              </Button>
            </>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {coreOnboarding
            ? 'Создайте основной продукт (Core): заполните название и описание, затем выберите «Вручную» или «Автомат».'
            : 'Введите название и нажмите «Добавить продукт»'}
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}
      {loading && <div className="text-sm text-muted-foreground">Загрузка продуктов…</div>}
      {!loading && !error && products.length === 0 && (
        <div className="rounded-lg border px-4 py-6 text-muted-foreground">
          Пока нет продуктов. Создайте основной продукт (Core) через форму выше.
        </div>
      )}
      {!loading && !error && products.length > 0 && rows.length === 0 && createTypeId != null && (
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
                <TableHead>Тип</TableHead>
                <TableHead>Краткое описание</TableHead>
                <TableHead>Обновлено</TableHead>
                <TableHead className="text-right">Действия</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((product) => (
                <TableRow
                  key={product.id}
                  className="cursor-pointer"
                  onClick={(e) => {
                    const target = e.target as HTMLElement | null;
                    if (target?.closest('button,a')) return;
                    openProduct(product.id);
                  }}
                >
                  <TableCell className="font-medium">{product.name}</TableCell>
                  <TableCell className="text-muted-foreground">{product.product_type_name || '—'}</TableCell>
                  <TableCell className="text-muted-foreground">{product.short_description || '—'}</TableCell>
                  <TableCell className="text-muted-foreground">{formatDate(product.updated_at)}</TableCell>
                  <TableCell className="text-right">
                    <div className="inline-flex items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        disabled={duplicatingId === product.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDuplicate(product);
                        }}
                        aria-label="Сделать копию"
                        title="Сделать копию"
                      >
                        {duplicatingId === product.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Copy className="h-4 w-4" />}
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                        disabled={duplicatingId === product.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          void handleDelete(product.id);
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
