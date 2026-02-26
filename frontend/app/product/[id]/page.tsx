'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ExternalLink, Plus, Trash2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { CustomTextarea } from '@/components/ui/custom-textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { productTypesApi } from '@/lib/api/productTypes';
import { ApiError } from '@/lib/api';
import { useRole } from '@/lib/hooks';
import type { ClientProduct, ProductStatus, ProductStructure, ProductType } from '@/lib/types';

type ProductRouteParams = { id: string };
type ProductRouteParamsInput = ProductRouteParams | Promise<ProductRouteParams> | undefined;

interface ProductPageProps {
  params?: Promise<ProductRouteParams>;
}

type ProductPackage = { name: string; description?: string | null; price?: number | null };

const normalizePackages = (raw: ClientProduct['packages']): ProductPackage[] => {
  if (!Array.isArray(raw)) return [];
  return raw
    .map((item) => {
      const name = typeof item?.name === 'string' ? item.name : '';
      const description = typeof item?.description === 'string' ? item.description : '';
      const rawPrice = (item as { price?: unknown } | null)?.price;
      const price =
        typeof rawPrice === 'number'
          ? rawPrice
          : typeof rawPrice === 'string'
            ? Number.parseFloat(rawPrice.replace(',', '.'))
            : null;
      return { name, description, price: Number.isFinite(price) ? price : null };
    })
    .filter((pkg) => pkg.name.trim().length > 0);
};

type AudienceRow = { parameter: string; value: string };
type TransformationRow = { was: string; became: string };
type MetricRow = { metric: string; promise: string };
type MethodRow = { component: string; template: string };
type LessonFormatRow = { stage: string; percent: number | null };
type ProgramModuleRow = { module: string; result: string };
type RelatedProductRef = NonNullable<ProductStructure['related_products']>[number];
type ProductPayload = {
  name: string;
  status: ProductStatus;
  product_type_id: number | null;
  short_description: string | null;
  packages: Array<{ name: string; description?: string | null; price?: number | null }>;
  structure: Record<string, unknown>;
};
type StructurePayloadInput = {
  audience: AudienceRow[];
  transformation: TransformationRow[];
  metrics: MetricRow[];
  method: MethodRow[];
  lessonFormat: LessonFormatRow[];
  programModules: ProgramModuleRow[];
  packagingName: string;
  packagingSlogan: string;
  packagingPromise: string;
  relatedProducts: RelatedProductRef[];
};

const toStr = (value: unknown) => (typeof value === 'string' ? value : value == null ? '' : String(value));

const toNumberOrNull = (value: unknown) => {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string') {
    const parsed = Number.parseFloat(value.replace(',', '.'));
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
};

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

const normalizeProductStatus = (value: string | null | undefined): ProductStatus =>
  value === 'active' ? 'active' : 'draft';

const normalizeStructure = (raw: ClientProduct['structure']): ProductStructure => {
  const base = (raw ?? {}) as Record<string, unknown>;
  const audience = Array.isArray(base.audience)
    ? (base.audience as Array<Record<string, unknown>>).map((row) => ({
        parameter: toStr(row?.parameter),
        value: toStr(row?.value)
      }))
    : [];
  const transformation = Array.isArray(base.transformation)
    ? (base.transformation as Array<Record<string, unknown>>).map((row) => ({
        was: toStr(row?.was),
        became: toStr(row?.became)
      }))
    : [];
  const metrics = Array.isArray(base.metrics)
    ? (base.metrics as Array<Record<string, unknown>>).map((row) => ({
        metric: toStr(row?.metric),
        promise: toStr(row?.promise)
      }))
    : [];
  const method = Array.isArray(base.method)
    ? (base.method as Array<Record<string, unknown>>).map((row) => ({
        component: toStr(row?.component),
        template: toStr(row?.template)
      }))
    : [];
  const lesson_format = Array.isArray(base.lesson_format)
    ? (base.lesson_format as Array<Record<string, unknown>>).map((row) => ({
        stage: toStr(row?.stage),
        percent: toNumberOrNull(row?.percent)
      }))
    : [];
  const program_modules = Array.isArray(base.program_modules)
    ? (base.program_modules as Array<Record<string, unknown>>).map((row) => ({
        module: toStr(row?.module),
        result: toStr(row?.result)
      }))
    : [];
  const packaging = (base.packaging ?? {}) as Record<string, unknown>;
  const related_products = Array.isArray(base.related_products)
    ? (base.related_products as unknown[])
        .map((item) => {
          if (item == null) return null;
          if (typeof item === 'number') {
            return { id: item, name: '', product_type_id: null, product_type_name: null, short_description: null } satisfies RelatedProductRef;
          }
          if (typeof item === 'string') {
            const id = toNumberOrNull(item);
            if (id == null) return null;
            return { id, name: '', product_type_id: null, product_type_name: null, short_description: null } satisfies RelatedProductRef;
          }
          if (typeof item !== 'object') return null;
          const row = item as Record<string, unknown>;
          const id = toNumberOrNull(row.id);
          if (id == null) return null;
          const name = toStr(row.name);
          const product_type_id = toNumberOrNull(row.product_type_id);
          const product_type_name = (() => {
            const text = toStr(row.product_type_name).trim();
            return text.length > 0 ? text : null;
          })();
          const short_description = (() => {
            const text = toStr(row.short_description).trim();
            return text.length > 0 ? text : null;
          })();
          return { id, name, product_type_id, product_type_name, short_description } satisfies RelatedProductRef;
        })
        .filter((item): item is Exclude<typeof item, null> => item !== null)
    : [];

  return {
    audience,
    transformation,
    metrics,
    method,
    lesson_format,
    program_modules,
    packaging: {
      name: packaging?.name == null ? '' : toStr(packaging?.name),
      slogan: packaging?.slogan == null ? '' : toStr(packaging?.slogan),
      promise: packaging?.promise == null ? '' : toStr(packaging?.promise)
    },
    related_products,
  };
};

const serializeRelatedProducts = (items: RelatedProductRef[]) =>
  items.map((item) => ({
    id: item.id,
    name: item.name,
    product_type_id: item.product_type_id ?? null,
    product_type_name: item.product_type_name ?? null,
    short_description: item.short_description ?? null
  }));

const buildStructurePayload = (input: StructurePayloadInput): ProductStructure => ({
  audience: input.audience
    .map((row) => ({ parameter: row.parameter.trim(), value: row.value.trim() }))
    .filter((row) => row.parameter.length > 0 || row.value.length > 0),
  transformation: input.transformation
    .map((row) => ({ was: row.was.trim(), became: row.became.trim() }))
    .filter((row) => row.was.length > 0 || row.became.length > 0),
  metrics: input.metrics
    .map((row) => ({ metric: row.metric.trim(), promise: row.promise.trim() }))
    .filter((row) => row.metric.length > 0 || row.promise.length > 0),
  method: input.method
    .map((row) => ({ component: row.component.trim(), template: row.template.trim() }))
    .filter((row) => row.component.length > 0 || row.template.length > 0),
  lesson_format: input.lessonFormat
    .map((row) => ({
      stage: row.stage.trim(),
      percent: typeof row.percent === 'number' && Number.isFinite(row.percent) ? row.percent : null
    }))
    .filter((row) => row.stage.length > 0 || row.percent !== null),
  program_modules: input.programModules
    .map((row) => ({ module: row.module.trim(), result: row.result.trim() }))
    .filter((row) => row.module.length > 0 || row.result.length > 0),
  packaging: {
    name: input.packagingName.trim() ? input.packagingName.trim() : null,
    slogan: input.packagingSlogan.trim() ? input.packagingSlogan.trim() : null,
    promise: input.packagingPromise.trim() ? input.packagingPromise.trim() : null
  },
  related_products: serializeRelatedProducts(input.relatedProducts)
});

const buildPayloadFromProduct = (data: ClientProduct): ProductPayload | null => {
  const nextName = (data.name ?? '').trim();
  if (!nextName) return null;

  const normalizedPackages = normalizePackages(data.packages)
    .map((pkg) => ({
      name: pkg.name.trim(),
      description: (pkg.description ?? '').trim() || null,
      price: typeof pkg.price === 'number' && Number.isFinite(pkg.price) ? pkg.price : null
    }))
    .filter((pkg) => pkg.name.length > 0);

  const structure = normalizeStructure(data.structure);
  const structurePayload = buildStructurePayload({
    audience: structure.audience ?? [],
    transformation: structure.transformation ?? [],
    metrics: structure.metrics ?? [],
    method: structure.method ?? [],
    lessonFormat: structure.lesson_format ?? [],
    programModules: structure.program_modules ?? [],
    packagingName: structure.packaging?.name ?? '',
    packagingSlogan: structure.packaging?.slogan ?? '',
    packagingPromise: structure.packaging?.promise ?? '',
    relatedProducts: structure.related_products ?? []
  });

  return {
    name: nextName,
    status: normalizeProductStatus(data.status),
    product_type_id: data.product_type_id ?? null,
    short_description: (data.short_description ?? '').trim() ? (data.short_description ?? '').trim() : null,
    packages: normalizedPackages,
    structure: structurePayload as unknown as Record<string, unknown>
  };
};

export default function ProductPage({ params }: ProductPageProps) {
  const router = useRouter();
  const { canEdit } = useRole();

  const [productId, setProductId] = useState<number | null>(null);
  const [product, setProduct] = useState<ClientProduct | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const lastSavedHashRef = useRef<string>('');
  const pendingPayloadRef = useRef<ProductPayload | null>(null);
  const dirtyRef = useRef(false);
  const autoSavingRef = useRef(false);
  const lastEditAtRef = useRef(0);

  const [productName, setProductName] = useState('');
  const [productStatus, setProductStatus] = useState<ProductStatus>('draft');
  const [productTypeId, setProductTypeId] = useState<number | null>(null);
  const [shortDescription, setShortDescription] = useState('');
  const [packages, setPackages] = useState<ProductPackage[]>([]);
  const [types, setTypes] = useState<ProductType[]>([]);
  const [audience, setAudience] = useState<AudienceRow[]>([]);
  const [transformation, setTransformation] = useState<TransformationRow[]>([]);
  const [metrics, setMetrics] = useState<MetricRow[]>([]);
  const [method, setMethod] = useState<MethodRow[]>([]);
  const [lessonFormat, setLessonFormat] = useState<LessonFormatRow[]>([]);
  const [programModules, setProgramModules] = useState<ProgramModuleRow[]>([]);
  const [packagingName, setPackagingName] = useState('');
  const [packagingSlogan, setPackagingSlogan] = useState('');
  const [packagingPromise, setPackagingPromise] = useState('');
  const [relatedProducts, setRelatedProducts] = useState<RelatedProductRef[]>([]);

  const [createRelatedName, setCreateRelatedName] = useState('');
  const [createRelatedTypeId, setCreateRelatedTypeId] = useState<number | null>(null);
  const [createRelatedShortDescription, setCreateRelatedShortDescription] = useState('');
  const [creatingRelated, setCreatingRelated] = useState(false);
  const [creatingRelatedTaskId, setCreatingRelatedTaskId] = useState<string | null>(null);
  const [creatingRelatedMap, setCreatingRelatedMap] = useState(false);
  const [creatingDigitalProductPage, setCreatingDigitalProductPage] = useState(false);

  const coreTypeId = useMemo(() => {
    const core = types.find((t) => t.name.trim().toLowerCase() === 'core');
    return core?.id ?? null;
  }, [types]);

  const isCore = useMemo(() => {
    if (coreTypeId != null) return productTypeId === coreTypeId;
    return (product?.product_type_name ?? '').trim().toLowerCase() === 'core';
  }, [coreTypeId, product?.product_type_name, productTypeId]);

  const relatedTypeOptions = useMemo(() => {
    return types.filter((t) => t.name.trim().toLowerCase() !== 'core');
  }, [types]);

  useEffect(() => {
    let isActive = true;
    const paramsInput = params as ProductRouteParamsInput;

    Promise.resolve(paramsInput)
      .then((resolved) => {
        if (!isActive) return;
        if (!resolved) {
          setProductId(null);
          return;
        }
        const parsedId = Number.parseInt(resolved.id, 10);
        setProductId(Number.isNaN(parsedId) ? null : parsedId);
      })
      .catch(() => {
        if (isActive) setProductId(null);
      });

    return () => {
      isActive = false;
    };
  }, [params]);

  const loadProduct = async () => {
    if (productId === null) return;
    setLoading(true);
    try {
      const [data, typeData] = await Promise.all([clientProductsApi.detail(productId), productTypesApi.list()]);
      setProduct(data);
      setProductName(data.name ?? '');
      setProductStatus(normalizeProductStatus(data.status));
      setProductTypeId(data.product_type_id ?? null);
      setShortDescription(data.short_description ?? '');
      setPackages(normalizePackages(data.packages));
      setTypes(typeData);
      const structure = normalizeStructure(data.structure);
      setAudience(structure.audience ?? []);
      setTransformation(structure.transformation ?? []);
      setMetrics(structure.metrics ?? []);
      setMethod(structure.method ?? []);
      setLessonFormat(structure.lesson_format ?? []);
      setProgramModules(structure.program_modules ?? []);
      setPackagingName(structure.packaging?.name ?? '');
      setPackagingSlogan(structure.packaging?.slogan ?? '');
      setPackagingPromise(structure.packaging?.promise ?? '');
      setRelatedProducts(structure.related_products ?? []);
      const payload = buildPayloadFromProduct(data);
      pendingPayloadRef.current = payload;
      lastSavedHashRef.current = payload ? JSON.stringify(payload) : '';
      dirtyRef.current = false;
    } catch (err) {
      console.error('Failed to load product', err);
      toast.error('Не удалось загрузить продукт');
      setProduct(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (productId !== null) {
      void loadProduct();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId]);

  const packagesCount = useMemo(() => packages.length, [packages]);
  const canCreateRelated = Boolean(createRelatedName.trim() && createRelatedTypeId != null);

  const handleAddAudienceRow = () => setAudience((prev) => [...prev, { parameter: '', value: '' }]);
  const handleAddTransformationRow = () => setTransformation((prev) => [...prev, { was: '', became: '' }]);
  const handleAddMetricRow = () => setMetrics((prev) => [...prev, { metric: '', promise: '' }]);
  const handleAddMethodRow = () => setMethod((prev) => [...prev, { component: '', template: '' }]);
  const handleAddLessonFormatRow = () => setLessonFormat((prev) => [...prev, { stage: '', percent: null }]);
  const handleAddProgramModuleRow = () => setProgramModules((prev) => [...prev, { module: '', result: '' }]);

  const handleAddPackage = () => {
    setPackages((prev) => [...prev, { name: '', description: '', price: null }]);
  };

  const handleDeletePackage = (index: number) => {
    setPackages((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCreateRelatedProduct = async () => {
    if (!canEdit || saving || creatingRelated) return;
    if (!isCore) {
      toast.error('Сопутствующие продукты можно создавать только внутри Core-продукта.');
      return;
    }

    const name = createRelatedName.trim();
    const short_description = createRelatedShortDescription.trim();
    if (!name || createRelatedTypeId == null) return;
    if (productId == null) return;

    setCreatingRelated(true);
    let keepLoading = false;
    try {
      const response = await clientProductsApi.createRelatedAi(productId, {
        name,
        product_type_id: createRelatedTypeId,
        short_description: short_description ? short_description : undefined,
        language: 'ru'
      });

      const immediateProduct = response.product;
      if (immediateProduct?.id != null) {
        const ref: RelatedProductRef = {
          id: immediateProduct.id,
          name: immediateProduct.name ?? name,
          product_type_id: immediateProduct.product_type_id ?? createRelatedTypeId,
          product_type_name: immediateProduct.product_type_name ?? null,
          short_description: immediateProduct.short_description ?? (short_description ? short_description : null)
        };

        setRelatedProducts((prev) => {
          if (prev.some((item) => item.id === ref.id)) return prev;
          return [ref, ...prev];
        });

        setCreateRelatedName('');
        setCreateRelatedTypeId(null);
        setCreateRelatedShortDescription('');
        toast.success('Сопутствующий продукт создан и добавлен в список. Привязка к Core сохранится автоматически после завершения создания.');
        setCreatingRelated(false);
        return;
      }

      if (response.task_id) {
        keepLoading = true;
        setCreatingRelatedTaskId(response.task_id);
        toast.success(response.message || 'Генерация сопутствующего продукта запущена.');
        return;
      }

      toast.error(response.error || 'Не удалось запустить генерацию сопутствующего продукта');
    } catch (err) {
      console.error('Failed to create related product', err);
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
      toast.error('Не удалось создать сопутствующий продукт');
    } finally {
      if (!keepLoading) {
        setCreatingRelated(false);
      }
    }
  };

  const handleCreateDigitalProductPage = async () => {
    if (!canEdit || saving || creatingDigitalProductPage || productId == null) return;
    setCreatingDigitalProductPage(true);
    try {
      const response = await clientProductsApi.createDigitalProductPage(productId);
      setProduct(response.product);
      toast.success(response.created ? 'Страница цифрового продукта создана в Базе знаний' : 'Страница цифрового продукта уже привязана');
      if (response.kb_url) {
        router.push(response.kb_url);
      }
    } catch (err) {
      console.error('Failed to create digital product page', err);
      toast.error('Не удалось создать страницу цифрового продукта');
    } finally {
      setCreatingDigitalProductPage(false);
    }
  };

  useEffect(() => {
    if (!creatingRelatedTaskId) return;
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      try {
        const status = await clientProductsApi.generationStatus(creatingRelatedTaskId);
        if (cancelled) return;

        if (status.status === 'success') {
          let created = status.product ?? null;
          if (!created) {
            const productId = resolveProductId(status.result);
            if (productId != null) {
              try {
                created = await clientProductsApi.detail(productId);
              } catch (err) {
                console.error('Failed to fetch created related product', err);
              }
            }
          }

          if (created?.id != null) {
            const ref: RelatedProductRef = {
              id: created.id,
              name: created.name ?? '',
              product_type_id: created.product_type_id ?? null,
              product_type_name: created.product_type_name ?? null,
              short_description: created.short_description ?? null
            };

            setRelatedProducts((prev) => {
              if (prev.some((item) => item.id === ref.id)) return prev;
              return [ref, ...prev];
            });

            setCreateRelatedName('');
            setCreateRelatedTypeId(null);
            setCreateRelatedShortDescription('');
            toast.success('Сопутствующий продукт создан и добавлен в список.');
          } else {
            toast.error('Сопутствующий продукт создан, но не удалось получить его данные.');
          }

          setCreatingRelated(false);
          setCreatingRelatedTaskId(null);
          return;
        }

        if (status.status === 'failure' || status.status === 'revoked') {
          toast.error(status.error || 'Генерация сопутствующего продукта завершилась с ошибкой.');
          setCreatingRelated(false);
          setCreatingRelatedTaskId(null);
        }
      } catch (err) {
        console.error('Failed to fetch related product generation status', err);
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
  }, [creatingRelatedTaskId]);

  const handleCreateRelatedMap = async () => {
    if (!canEdit || creatingRelatedMap || productId == null) return;
    setCreatingRelatedMap(true);
    try {
      const created = await clientProductsApi.createRelatedMap(productId);
      router.push(`/map/${created.id}`);
    } catch (err) {
      console.error('Failed to create related products map', err);
      toast.error('Не удалось создать карту сопутствующих продуктов');
    } finally {
      setCreatingRelatedMap(false);
    }
  };

  const buildProductPayload = useCallback(
    (override?: { relatedProducts?: RelatedProductRef[] }): ProductPayload | null => {
      const nextName = productName.trim();
      if (!nextName) return null;

      const normalizedPackages = packages
        .map((pkg) => ({
          name: pkg.name.trim(),
          description: (pkg.description ?? '').trim() || null,
          price: typeof pkg.price === 'number' && Number.isFinite(pkg.price) ? pkg.price : null
        }))
        .filter((pkg) => pkg.name.length > 0);

      const structure = buildStructurePayload({
        audience,
        transformation,
        metrics,
        method,
        lessonFormat,
        programModules,
        packagingName,
        packagingSlogan,
        packagingPromise,
        relatedProducts: override?.relatedProducts ?? relatedProducts
      });

      return {
        name: nextName,
        status: productStatus,
        product_type_id: productTypeId,
        short_description: shortDescription.trim() ? shortDescription.trim() : null,
        packages: normalizedPackages,
        structure: structure as unknown as Record<string, unknown>
      };
    },
    [
      productName,
      productStatus,
      productTypeId,
      shortDescription,
      packages,
      audience,
      transformation,
      metrics,
      method,
      lessonFormat,
      programModules,
      packagingName,
      packagingSlogan,
      packagingPromise,
      relatedProducts
    ]
  );

  useEffect(() => {
    if (productId === null) return;
    const payload = buildProductPayload();
    pendingPayloadRef.current = payload;
    if (!payload) {
      dirtyRef.current = false;
      return;
    }
    const hash = JSON.stringify(payload);
    dirtyRef.current = hash !== lastSavedHashRef.current;
    lastEditAtRef.current = Date.now();
  }, [buildProductPayload, productId]);

  useEffect(() => {
    if (productId === null || !canEdit) return;
    const intervalId = window.setInterval(async () => {
      if (saving || loading) return;
      if (autoSavingRef.current) return;
      if (!dirtyRef.current) return;
      if (Date.now() - lastEditAtRef.current < 2000) return;
      const payload = pendingPayloadRef.current;
      if (!payload) return;
      autoSavingRef.current = true;
      try {
        const updated = await clientProductsApi.update(productId, payload);
        lastSavedHashRef.current = JSON.stringify(payload);
        dirtyRef.current = false;
        setProduct((prev) => (prev ? { ...prev, ...updated } : updated));
        setProductStatus(normalizeProductStatus(updated.status));
      } catch (err) {
        console.error('Failed to auto-save product', err);
      } finally {
        autoSavingRef.current = false;
      }
    }, 5000);
    return () => window.clearInterval(intervalId);
  }, [productId, canEdit, saving, loading]);

  const handleRemoveRelatedProduct = async (id: number) => {
    if (!canEdit || saving || productId === null) return;
    if (!confirm('Убрать продукт из сопутствующих?')) return;

    const prevRelated = relatedProducts;
    const nextRelated = relatedProducts.filter((p) => p.id !== id);
    setRelatedProducts(nextRelated);
    setSaving(true);
    try {
      const payload = buildProductPayload({ relatedProducts: nextRelated });
      if (!payload) {
        throw new Error('Product payload is empty');
      }
      const updated = await clientProductsApi.update(productId, payload);
      setProduct((prev) => (prev ? { ...prev, structure: updated.structure } : prev));
      const updatedStructure = normalizeStructure(updated.structure);
      setRelatedProducts(updatedStructure.related_products ?? nextRelated);
      lastSavedHashRef.current = JSON.stringify(payload);
      dirtyRef.current = false;
    } catch (err) {
      console.error('Failed to remove related product', err);
      toast.error('Не удалось удалить сопутствующий продукт');
      setRelatedProducts(prevRelated);
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    if (!canEdit || productId === null) return;
    const payload = buildProductPayload();
    if (!payload) return;

    setSaving(true);
    try {
      const updated = await clientProductsApi.update(productId, {
        name: payload.name,
        status: payload.status,
        product_type_id: payload.product_type_id,
        short_description: payload.short_description,
        packages: payload.packages,
        structure: payload.structure
      });
      setProduct(updated);
      setProductStatus(normalizeProductStatus(updated.status));
      setPackages(normalizePackages(updated.packages));
      const updatedStructure = normalizeStructure(updated.structure);
      setAudience(updatedStructure.audience ?? []);
      setTransformation(updatedStructure.transformation ?? []);
      setMetrics(updatedStructure.metrics ?? []);
      setMethod(updatedStructure.method ?? []);
      setLessonFormat(updatedStructure.lesson_format ?? []);
      setProgramModules(updatedStructure.program_modules ?? []);
      setPackagingName(updatedStructure.packaging?.name ?? '');
      setPackagingSlogan(updatedStructure.packaging?.slogan ?? '');
      setPackagingPromise(updatedStructure.packaging?.promise ?? '');
      setRelatedProducts(updatedStructure.related_products ?? []);
      lastSavedHashRef.current = JSON.stringify(payload);
      pendingPayloadRef.current = payload;
      dirtyRef.current = false;
      toast.success('Продукт сохранён');
    } catch (err) {
      console.error('Failed to update product', err);
      toast.error('Не удалось сохранить продукт');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!canEdit || productId === null) return;
    if (!confirm('Удалить продукт? Это действие нельзя отменить.')) return;
    try {
      await clientProductsApi.delete(productId);
      toast.success('Продукт удалён');
      router.push('/products');
    } catch (err) {
      console.error('Failed to delete product', err);
      toast.error('Не удалось удалить продукт');
    }
  };

  if (loading && !product) {
    return <div className="text-muted-foreground">Загрузка…</div>;
  }

  if (!product) {
    return (
      <div className="space-y-4">
        <Link href="/products">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад к продуктам
          </Button>
        </Link>
        <div className="rounded-lg border px-4 py-6 text-muted-foreground">
          Продукт не найден или недоступен.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <Link href="/products">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="h-4 w-4 mr-2" />
            Назад к продуктам
          </Button>
        </Link>

        {canEdit && (
          <Button variant="destructive" size="sm" onClick={handleDelete}>
            <Trash2 className="h-4 w-4 mr-2" />
            Удалить
          </Button>
        )}
      </div>

      <div className="space-y-1">
        <h1 className="text-3xl font-bold">Продукт</h1>
        <p className="text-gray-500">
          Структура продукта и пакеты ({packagesCount}).
        </p>
      </div>

      <div className="rounded-xl border bg-card/70 p-4 shadow-sm space-y-4">
        <div className="space-y-2">
          <div className="text-sm font-medium">Название продукта</div>
          <Input value={productName} onChange={(e) => setProductName(e.target.value)} disabled={!canEdit || saving} />
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium">Тип продукта</div>
          <Select
            value={productTypeId == null ? 'none' : String(productTypeId)}
            onValueChange={(value) => setProductTypeId(value === 'none' ? null : Number(value))}
            disabled={!canEdit || saving}
          >
            <SelectTrigger>
              <SelectValue placeholder="Выберите тип продукта" />
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
          <div className="text-xs text-muted-foreground">
            Типы редактируются во вкладке «Типы продуктов».
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium">Статус продукта</div>
          <Select
            value={productStatus}
            onValueChange={(value) => setProductStatus(value === 'active' ? 'active' : 'draft')}
            disabled={!canEdit || saving}
          >
            <SelectTrigger>
              <SelectValue placeholder="Выберите статус" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="draft">Черновик</SelectItem>
              <SelectItem value="active">Активный</SelectItem>
            </SelectContent>
          </Select>
          <div className="text-xs text-muted-foreground">
            На странице клиента показываются только активные продукты.
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium">Краткое описание</div>
          <CustomTextarea
            value={shortDescription}
            onChange={(e) => setShortDescription(e.target.value)}
            className="min-h-[110px]"
            disabled={!canEdit || saving}
          />
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium">Цифровой продукт (База знаний)</div>
          {product?.digital_product_document_id ? (
            <div className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2">
              <div className="text-sm">
                {product.digital_product_document_title?.trim() || `Документ #${product.digital_product_document_id}`}
              </div>
              <Link href={`/kb/${product.digital_product_document_id}`} className="inline-flex">
                <Button type="button" variant="outline" size="sm">
                  Открыть страницу
                  <ExternalLink className="ml-2 h-4 w-4" />
                </Button>
              </Link>
            </div>
          ) : (
            <div className="text-xs text-muted-foreground">
              Страница цифрового продукта не создана. После покупки без этой страницы клиент увидит сообщение для связи с владельцем.
            </div>
          )}

          {canEdit && (
            <Button
              type="button"
              variant="outline"
              onClick={() => void handleCreateDigitalProductPage()}
              disabled={saving || creatingDigitalProductPage}
            >
              {creatingDigitalProductPage ? 'Создание…' : 'Добавить цифровой продукт'}
            </Button>
          )}
        </div>
      </div>

      {isCore ? (
        <div className="rounded-xl border bg-card/70 p-4 shadow-sm space-y-4">
          <div className="space-y-1">
            <div className="text-sm font-medium">Сопутствующие продукты</div>
            <div className="text-xs text-muted-foreground">
              Создавайте продукты других типов из Core. Привязка к Core сохраняется автоматически после создания.
            </div>
          </div>

          {canEdit ? (
            <div className="flex flex-wrap items-center gap-3">
              <Input
                placeholder="Название сопутствующего продукта"
                value={createRelatedName}
                onChange={(e) => setCreateRelatedName(e.target.value)}
                disabled={saving || creatingRelated}
                className="w-full max-w-sm"
              />
              <Input
                placeholder="Краткое описание (опционально)"
                value={createRelatedShortDescription}
                onChange={(e) => setCreateRelatedShortDescription(e.target.value)}
                disabled={saving || creatingRelated}
                className="w-full max-w-sm"
              />
              <div className="w-full max-w-sm">
                <Select
                  value={createRelatedTypeId == null ? 'none' : String(createRelatedTypeId)}
                  onValueChange={(value) => setCreateRelatedTypeId(value === 'none' ? null : Number(value))}
                  disabled={saving || creatingRelated}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Тип продукта" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">— Выберите тип —</SelectItem>
                    {relatedTypeOptions.map((t) => (
                      <SelectItem key={t.id} value={String(t.id)}>
                        {t.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button onClick={() => void handleCreateRelatedProduct()} disabled={!canCreateRelated || saving || creatingRelated}>
                {creatingRelated ? 'Создание…' : 'Добавить'}
              </Button>
            </div>
          ) : null}

          {relatedProducts.length === 0 ? (
            <div className="rounded-lg border px-4 py-6 text-muted-foreground">
              Пока нет сопутствующих продуктов.
            </div>
          ) : (
            <div className="rounded-xl border bg-background/30 shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Название</TableHead>
                    <TableHead>Тип</TableHead>
                    <TableHead>Описание</TableHead>
                    <TableHead className="text-right">Действия</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {relatedProducts.map((item) => {
                    const typeName =
                      item.product_type_name ??
                      (item.product_type_id != null ? types.find((t) => t.id === item.product_type_id)?.name : null) ??
                      '—';
                    return (
                      <TableRow
                        key={item.id}
                        className="cursor-pointer"
                        onClick={(e) => {
                          const target = e.target as HTMLElement | null;
                          if (target?.closest('button,a')) return;
                          router.push(`/product/${item.id}`);
                        }}
                      >
                        <TableCell className="font-medium">{item.name || `#${item.id}`}</TableCell>
                        <TableCell className="text-muted-foreground">{typeName}</TableCell>
                        <TableCell className="text-muted-foreground">{item.short_description || '—'}</TableCell>
                        <TableCell className="text-right">
                          <div className="inline-flex items-center gap-1">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={(e) => {
                                e.stopPropagation();
                                router.push(`/product/${item.id}`);
                              }}
                            >
                              Открыть
                            </Button>
                            {canEdit ? (
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  void handleRemoveRelatedProduct(item.id);
                                }}
                                disabled={saving}
                                aria-label="Убрать из сопутствующих"
                                title="Убрать из сопутствующих"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            ) : null}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
          {canEdit && (
            <div className="flex justify-start">
              <Button
                onClick={() => void handleCreateRelatedMap()}
                disabled={creatingRelatedMap}
                className="bg-black text-white hover:bg-black/90"
              >
                {creatingRelatedMap ? 'Создание карты…' : 'Создать карту сопутствующих'}
              </Button>
            </div>
          )}
        </div>
      ) : null}

      <div className="rounded-xl border bg-card/70 p-4 shadow-sm space-y-6">
        <div className="space-y-1">
          <div className="text-sm font-medium">Структура продукта</div>
          <div className="text-xs text-muted-foreground">Заполните блоки по шаблону (ЦА → трансформация → метрики → метод → формат → программа → упаковка).</div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium">1. ЦА (кому)</div>
            {canEdit && (
              <Button type="button" variant="secondary" size="sm" onClick={handleAddAudienceRow} disabled={saving}>
                <Plus className="h-4 w-4 mr-2" />
                Добавить параметр
              </Button>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Параметр</TableHead>
                <TableHead>Пример / значение</TableHead>
                <TableHead className="w-[56px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {audience.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-muted-foreground">
                    Добавьте строки (Возраст, Уровень, Боль, Страх, Цель…)
                  </TableCell>
                </TableRow>
              ) : (
                audience.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Input
                        value={row.parameter}
                        onChange={(e) => {
                          const next = e.target.value;
                          setAudience((prev) => prev.map((r, i) => (i === index ? { ...r, parameter: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.value}
                        onChange={(e) => {
                          const next = e.target.value;
                          setAudience((prev) => prev.map((r, i) => (i === index ? { ...r, value: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      {canEdit ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={() => setAudience((prev) => prev.filter((_, i) => i !== index))}
                          disabled={saving}
                          aria-label="Удалить строку"
                          title="Удалить строку"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium">2. Трансформация (из → в)</div>
            {canEdit && (
              <Button type="button" variant="secondary" size="sm" onClick={handleAddTransformationRow} disabled={saving}>
                <Plus className="h-4 w-4 mr-2" />
                Добавить пару
              </Button>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Было</TableHead>
                <TableHead>Стало</TableHead>
                <TableHead className="w-[56px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {transformation.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-muted-foreground">
                    Добавьте пары «было → стало»
                  </TableCell>
                </TableRow>
              ) : (
                transformation.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Input
                        value={row.was}
                        onChange={(e) => {
                          const next = e.target.value;
                          setTransformation((prev) => prev.map((r, i) => (i === index ? { ...r, was: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.became}
                        onChange={(e) => {
                          const next = e.target.value;
                          setTransformation((prev) => prev.map((r, i) => (i === index ? { ...r, became: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      {canEdit ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={() => setTransformation((prev) => prev.filter((_, i) => i !== index))}
                          disabled={saving}
                          aria-label="Удалить строку"
                          title="Удалить строку"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium">3. Результат в цифрах</div>
            {canEdit && (
              <Button type="button" variant="secondary" size="sm" onClick={handleAddMetricRow} disabled={saving}>
                <Plus className="h-4 w-4 mr-2" />
                Добавить метрику
              </Button>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Метрика</TableHead>
                <TableHead>Что обещаем</TableHead>
                <TableHead className="w-[56px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {metrics.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-muted-foreground">
                    Добавьте метрики и обещания (Listening, Speaking…)
                  </TableCell>
                </TableRow>
              ) : (
                metrics.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Input
                        value={row.metric}
                        onChange={(e) => {
                          const next = e.target.value;
                          setMetrics((prev) => prev.map((r, i) => (i === index ? { ...r, metric: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.promise}
                        onChange={(e) => {
                          const next = e.target.value;
                          setMetrics((prev) => prev.map((r, i) => (i === index ? { ...r, promise: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      {canEdit ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={() => setMetrics((prev) => prev.filter((_, i) => i !== index))}
                          disabled={saving}
                          aria-label="Удалить строку"
                          title="Удалить строку"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium">4. Метод (как именно)</div>
            {canEdit && (
              <Button type="button" variant="secondary" size="sm" onClick={handleAddMethodRow} disabled={saving}>
                <Plus className="h-4 w-4 mr-2" />
                Добавить компонент
              </Button>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Компонент</TableHead>
                <TableHead>Универсальный шаблон</TableHead>
                <TableHead className="w-[56px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {method.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-muted-foreground">
                    Добавьте элементы метода (Контент, Анализ, Практика…)
                  </TableCell>
                </TableRow>
              ) : (
                method.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Input
                        value={row.component}
                        onChange={(e) => {
                          const next = e.target.value;
                          setMethod((prev) => prev.map((r, i) => (i === index ? { ...r, component: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.template}
                        onChange={(e) => {
                          const next = e.target.value;
                          setMethod((prev) => prev.map((r, i) => (i === index ? { ...r, template: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      {canEdit ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={() => setMethod((prev) => prev.filter((_, i) => i !== index))}
                          disabled={saving}
                          aria-label="Удалить строку"
                          title="Удалить строку"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium">5. Формат взаимодействия с клиентом</div>
            {canEdit && (
              <Button type="button" variant="secondary" size="sm" onClick={handleAddLessonFormatRow} disabled={saving}>
                <Plus className="h-4 w-4 mr-2" />
                Добавить этап
              </Button>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Этап</TableHead>
                <TableHead className="w-[160px]">% времени</TableHead>
                <TableHead className="w-[56px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {lessonFormat.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-muted-foreground">
                    Добавьте этапы и проценты (Онбординг, Диагностика, Сопровождение…)
                  </TableCell>
                </TableRow>
              ) : (
                lessonFormat.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Input
                        value={row.stage}
                        onChange={(e) => {
                          const next = e.target.value;
                          setLessonFormat((prev) => prev.map((r, i) => (i === index ? { ...r, stage: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="number"
                        min="0"
                        step="1"
                        inputMode="numeric"
                        value={row.percent == null ? '' : String(row.percent)}
                        onChange={(e) => {
                          const raw = e.target.value;
                          const parsed = raw.trim() ? Number.parseFloat(raw) : NaN;
                          setLessonFormat((prev) =>
                            prev.map((r, i) => (i === index ? { ...r, percent: Number.isFinite(parsed) ? parsed : null } : r))
                          );
                        }}
                        disabled={!canEdit || saving}
                        className="text-right"
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      {canEdit ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={() => setLessonFormat((prev) => prev.filter((_, i) => i !== index))}
                          disabled={saving}
                          aria-label="Удалить строку"
                          title="Удалить строку"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium">6. Программа (модули)</div>
            {canEdit && (
              <Button type="button" variant="secondary" size="sm" onClick={handleAddProgramModuleRow} disabled={saving}>
                <Plus className="h-4 w-4 mr-2" />
                Добавить модуль
              </Button>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Модуль</TableHead>
                <TableHead>Результат</TableHead>
                <TableHead className="w-[56px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {programModules.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={3} className="text-muted-foreground">
                    Добавьте модули и результаты (Foundation, Expansion…)
                  </TableCell>
                </TableRow>
              ) : (
                programModules.map((row, index) => (
                  <TableRow key={index}>
                    <TableCell>
                      <Input
                        value={row.module}
                        onChange={(e) => {
                          const next = e.target.value;
                          setProgramModules((prev) => prev.map((r, i) => (i === index ? { ...r, module: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        value={row.result}
                        onChange={(e) => {
                          const next = e.target.value;
                          setProgramModules((prev) => prev.map((r, i) => (i === index ? { ...r, result: next } : r)));
                        }}
                        disabled={!canEdit || saving}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      {canEdit ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={() => setProgramModules((prev) => prev.filter((_, i) => i !== index))}
                          disabled={saving}
                          aria-label="Удалить строку"
                          title="Удалить строку"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>

        <div className="space-y-3">
          <div className="text-sm font-medium">7. Упаковка</div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">Название</div>
              <Input value={packagingName} onChange={(e) => setPackagingName(e.target.value)} disabled={!canEdit || saving} />
            </div>
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">Слоган</div>
              <Input value={packagingSlogan} onChange={(e) => setPackagingSlogan(e.target.value)} disabled={!canEdit || saving} />
            </div>
            <div className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">Обещание</div>
              <Input value={packagingPromise} onChange={(e) => setPackagingPromise(e.target.value)} disabled={!canEdit || saving} />
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border bg-card/70 p-4 shadow-sm space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-1">
            <div className="text-sm font-medium">Пакеты</div>
            <div className="text-xs text-muted-foreground">Добавьте пакеты (например, Basic/Pro) и их описания.</div>
          </div>
          {canEdit && (
            <Button type="button" variant="secondary" size="sm" onClick={handleAddPackage} disabled={saving}>
              <Plus className="h-4 w-4 mr-2" />
              Добавить пакет
            </Button>
          )}
        </div>

        {packages.length === 0 ? (
          <div className="text-sm text-muted-foreground">Пакетов пока нет.</div>
        ) : (
          <div className="space-y-3">
            {packages.map((pkg, index) => (
              <div key={index} className="rounded-lg border bg-background p-3 space-y-2">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium">Пакет #{index + 1}</div>
                  {canEdit && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-600 hover:bg-red-50 hover:text-red-700"
                      onClick={() => handleDeletePackage(index)}
                      disabled={saving}
                      aria-label="Удалить пакет"
                      title="Удалить пакет"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  )}
                </div>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="space-y-1 sm:col-span-2">
                    <div className="text-xs font-medium text-muted-foreground">Название</div>
                    <Input
                      value={pkg.name}
                      onChange={(e) => {
                        const next = e.target.value;
                        setPackages((prev) => prev.map((p, i) => (i === index ? { ...p, name: next } : p)));
                      }}
                      disabled={!canEdit || saving}
                    />
                  </div>
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-muted-foreground sm:text-right">Цена</div>
                    <Input
                      type="number"
                      inputMode="decimal"
                      step="0.01"
                      min="0"
                      value={typeof pkg.price === 'number' && Number.isFinite(pkg.price) ? String(pkg.price) : ''}
                      onChange={(e) => {
                        const raw = e.target.value;
                        const parsed = raw.trim() ? Number.parseFloat(raw) : NaN;
                        setPackages((prev) =>
                          prev.map((p, i) => (i === index ? { ...p, price: Number.isFinite(parsed) ? parsed : null } : p))
                        );
                      }}
                      disabled={!canEdit || saving}
                      className="sm:text-right"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="text-xs font-medium text-muted-foreground">Наполнение</div>
                  <CustomTextarea
                    value={pkg.description ?? ''}
                    onChange={(e) => {
                      const next = e.target.value;
                      setPackages((prev) => prev.map((p, i) => (i === index ? { ...p, description: next } : p)));
                    }}
                    disabled={!canEdit || saving}
                    className="min-h-[80px]"
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center justify-end gap-2">
        <Button variant="secondary" onClick={() => void loadProduct()} disabled={saving || loading}>
          Обновить
        </Button>
        <Button onClick={handleSave} disabled={!canEdit || saving || !productName.trim()}>
          {saving ? 'Сохранение…' : 'Сохранить'}
        </Button>
      </div>
    </div>
  );
}
