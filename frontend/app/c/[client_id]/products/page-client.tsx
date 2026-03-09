'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { ApiError, apiFetch } from '@/lib/api';
import type { ClientProduct } from '@/lib/types';
import ProductsContent from './content';
import { buildPublicProductRows } from './product-items';

type PublicClientPageResponse = {
  client?: {
    id?: number;
    name?: string;
  };
  settings?: {
    brand_name?: string;
    timezone?: string;
  } | null;
  products?: ClientProduct[];
};

type PublicProductsPageClientProps = {
  resolvedClientId?: number;
  useCustomDomainPaths?: boolean;
};

export default function PublicProductsPage({
  resolvedClientId,
  useCustomDomainPaths = false,
}: PublicProductsPageClientProps = {}) {
  const { client_id: rawClientId } = useParams<{ client_id?: string }>();
  const pageClientId = resolvedClientId ?? Number(rawClientId);
  const publicRootPath = useCustomDomainPaths ? '/' : `/c/${pageClientId}`;
  const pathPrefix = useCustomDomainPaths ? '' : `/c/${pageClientId}`;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clientName, setClientName] = useState('');
  const [brandName, setBrandName] = useState('');
  const [products, setProducts] = useState<ClientProduct[]>([]);

  useEffect(() => {
    const loadPublicProductsPage = async () => {
      if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
        setError('Некорректный идентификатор клиента.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<PublicClientPageResponse>(`/public/client-page/${pageClientId}/`);
        setClientName(String(data?.client?.name ?? '').trim());
        setBrandName(String(data?.settings?.brand_name ?? '').trim());
        setProducts(Array.isArray(data?.products) ? data.products : []);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setError('Страница продуктов не найдена.');
        } else {
          setError('Не удалось загрузить продукты.');
        }
      } finally {
        setLoading(false);
      }
    };

    void loadPublicProductsPage();
  }, [pageClientId]);

  const rubFormatter = useMemo(
    () =>
      new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 2,
      }),
    []
  );

  const productRows = useMemo(
    () => buildPublicProductRows(products, rubFormatter),
    [products, rubFormatter]
  );

  const displayName = brandName || clientName || `Клиент #${pageClientId}`;

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-2xl border p-6 text-sm text-muted-foreground">Загрузка продуктов...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-6 space-y-4">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">{error}</div>
        <Link href={publicRootPath} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent">
          На страницу клиента
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <ProductsContent
        clientId={pageClientId}
        displayName={displayName}
        products={productRows}
        pathPrefix={pathPrefix}
        backHref={publicRootPath}
      />
    </div>
  );
}
