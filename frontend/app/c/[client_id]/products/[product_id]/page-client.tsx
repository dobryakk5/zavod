'use client';

import Link from 'next/link';
import { useParams, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { generateHTML } from '@tiptap/html';
import { createKbExtensions } from '@/components/kb/tiptapExtensions';
import { normalizeTiptapDoc } from '@/components/products/event-description-editor';
import { ApiError, API_BASE_URL, apiFetch } from '@/lib/api';
import type { ClientProduct } from '@/lib/types';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  parseResponseDetail,
  PAYMENT_PROVIDER_LABELS,
  type PaymentProvider,
  type PublicBuyProductResponse,
  type PublicProductPaymentStatusResponse,
  resolvePackagePrice,
} from '../../shared/public-product-payment';
import {
  isEventProductType,
  isProductActive,
} from '../../events/event-products';

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

type ProductPackage = {
  index: number;
  name: string;
  description: string;
  price: number | null;
};

const getPendingProductPurchaseStorageKey = (clientId: number, productId: number) =>
  `client-page:pending-product-purchase:${clientId}:${productId}`;

type PublicProductPageClientProps = {
  resolvedClientId?: number;
  useCustomDomainPaths?: boolean;
};

export default function PublicProductPage({
  resolvedClientId,
  useCustomDomainPaths = false,
}: PublicProductPageClientProps = {}) {
  const { client_id: rawClientId, product_id: rawProductId } = useParams<{ client_id?: string; product_id: string }>();
  const searchParams = useSearchParams();
  const pageClientId = resolvedClientId ?? Number(rawClientId);
  const pageProductId = Number(rawProductId);
  const productsPath = useCustomDomainPaths ? '/products' : `/c/${pageClientId}/products`;
  const productPath = useCustomDomainPaths ? `/products/${pageProductId}` : `/c/${pageClientId}/products/${pageProductId}`;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clientName, setClientName] = useState('');
  const [brandName, setBrandName] = useState('');
  const [product, setProduct] = useState<ClientProduct | null>(null);
  const [providerDialogOpen, setProviderDialogOpen] = useState(false);
  const [pendingPackage, setPendingPackage] = useState<ProductPackage | null>(null);
  const [buyingPackageIndex, setBuyingPackageIndex] = useState<number | null>(null);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [purchaseStatusLoading, setPurchaseStatusLoading] = useState(false);
  const [purchaseStatusError, setPurchaseStatusError] = useState<string | null>(null);
  const [checkedPaymentId, setCheckedPaymentId] = useState<string | null>(null);
  const [purchaseSuccessModalOpen, setPurchaseSuccessModalOpen] = useState(false);
  const [purchaseSuccessModalMessage, setPurchaseSuccessModalMessage] = useState<string | null>(null);
  const [purchaseDeliveryLink, setPurchaseDeliveryLink] = useState<string | null>(null);
  const [purchaseDeliveryTitle, setPurchaseDeliveryTitle] = useState<string | null>(null);

  useEffect(() => {
    const loadProduct = async () => {
      if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
        setError('Некорректный идентификатор клиента.');
        setLoading(false);
        return;
      }
      if (!Number.isFinite(pageProductId) || pageProductId <= 0) {
        setError('Некорректный идентификатор продукта.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<PublicClientPageResponse>(`/public/client-page/${pageClientId}/`);
        setClientName(String(data?.client?.name ?? '').trim());
        setBrandName(String(data?.settings?.brand_name ?? '').trim());

        const list = Array.isArray(data?.products) ? data.products : [];
        const selected = list.find((item) => item.id === pageProductId) ?? null;
        if (!selected || !isProductActive(selected) || isEventProductType(selected)) {
          setProduct(null);
          setError('Продукт не найден или недоступен.');
          return;
        }
        setProduct(selected);
      } catch {
        setError('Не удалось загрузить продукт.');
      } finally {
        setLoading(false);
      }
    };

    void loadProduct();
  }, [pageClientId, pageProductId]);

  useEffect(() => {
    if (loading || !Number.isFinite(pageClientId) || pageClientId <= 0 || !Number.isFinite(pageProductId) || pageProductId <= 0) {
      return;
    }

    const queryPaymentId = (
      searchParams.get('payment_id')
      || searchParams.get('paymentId')
      || searchParams.get('PaymentId')
      || ''
    ).trim();
    let pendingPaymentId = queryPaymentId;

    if (!pendingPaymentId && typeof window !== 'undefined') {
      try {
        const raw = window.localStorage.getItem(getPendingProductPurchaseStorageKey(pageClientId, pageProductId));
        if (raw) {
          const parsed = JSON.parse(raw) as { paymentId?: unknown; createdAt?: unknown };
          const localPaymentId = typeof parsed?.paymentId === 'string' ? parsed.paymentId.trim() : '';
          const createdAt = typeof parsed?.createdAt === 'number' ? parsed.createdAt : 0;
          const isFresh = createdAt > 0 && Date.now() - createdAt < 1000 * 60 * 60 * 24;
          if (localPaymentId && isFresh) {
            pendingPaymentId = localPaymentId;
          }
        }
      } catch {
        // ignore invalid localStorage payload
      }
    }

    if (!pendingPaymentId || checkedPaymentId === pendingPaymentId) {
      return;
    }

    const checkPurchaseStatus = async (paymentId: string) => {
      setPurchaseStatusLoading(true);
      setPurchaseStatusError(null);
      try {
        const statusResponse = await apiFetch<PublicProductPaymentStatusResponse>(
          `/public/client-page/${pageClientId}/payment-status/?payment_id=${encodeURIComponent(paymentId)}`
        );
        const paymentStatus = (statusResponse?.status || '').trim();
        const delivery = statusResponse?.delivery || null;
        if (paymentStatus === 'succeeded' && statusResponse?.paid) {
          const successMessage = delivery?.ready && delivery.url
            ? 'Оплата прошла успешно. Доступ к курсу активирован.'
            : (delivery?.message || 'Оплата прошла успешно. Доступ к курсу активирован.');
          setPurchaseSuccessModalMessage(successMessage);
          setPurchaseSuccessModalOpen(true);
          if (delivery?.ready && delivery.url) {
            setPurchaseDeliveryLink(delivery.url);
            setPurchaseDeliveryTitle((delivery.course_title || delivery.document_title || '').trim() || 'Открыть курс');
          } else {
            setPurchaseDeliveryLink(null);
            setPurchaseDeliveryTitle(null);
          }
          if (typeof window !== 'undefined') {
            window.localStorage.removeItem(getPendingProductPurchaseStorageKey(pageClientId, pageProductId));
          }
          return;
        }

        if (paymentStatus) {
          setPurchaseStatusError(`Статус оплаты: ${paymentStatus}. Если вы уже оплатили, обновите страницу через несколько секунд.`);
          return;
        }
        setPurchaseStatusError('Статус оплаты пока не получен.');
      } catch (statusError) {
        if (statusError instanceof ApiError && statusError.status === 401) {
          setPurchaseStatusError('Для подтверждения оплаты войдите как контакт через Telegram или VK.');
          return;
        }
        setPurchaseStatusError('Не удалось проверить статус оплаты.');
      } finally {
        setPurchaseStatusLoading(false);
      }
    };

    setCheckedPaymentId(pendingPaymentId);
    void checkPurchaseStatus(pendingPaymentId);
  }, [checkedPaymentId, loading, pageClientId, pageProductId, searchParams]);

  const rubFormatter = useMemo(
    () =>
      new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 2,
      }),
    []
  );

  const productName = (product?.name || '').trim() || `Продукт #${pageProductId}`;
  const shortDescription = (product?.short_description || '').trim();
  const descriptionHtml = useMemo(() => {
    const description = product?.structure?.rich_description as unknown;
    if (
      description == null
      || (typeof description === 'string' && !description.trim())
      || (typeof description === 'object' && !Array.isArray(description) && !Object.keys(description).length)
    ) {
      return '';
    }
    try {
      const normalized = normalizeTiptapDoc(description);
      return generateHTML(normalized, createKbExtensions());
    } catch {
      return '';
    }
  }, [product?.structure?.rich_description]);

  const packages = useMemo<ProductPackage[]>(() => {
    if (!Array.isArray(product?.packages)) {
      return [];
    }
    return product.packages.map((item, index) => {
      const fallbackName = `Пакет ${index + 1}`;
      return {
        index,
        name: (String(item?.name ?? '').trim() || fallbackName),
        description: String(item?.description ?? '').trim(),
        price: resolvePackagePrice((item as { price?: unknown })?.price),
      };
    });
  }, [product?.packages]);

  const displayClient = brandName || clientName || `Клиент #${pageClientId}`;

  const handleBuyPackage = async (pkg: ProductPackage, provider: PaymentProvider) => {
    if (!product || pkg.price === null || buyingPackageIndex !== null) {
      return;
    }
    if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
      return;
    }

    setProviderDialogOpen(false);
    setBuyingPackageIndex(pkg.index);
    setPurchaseError(null);
    setPurchaseStatusError(null);
    setPurchaseSuccessModalOpen(false);
    setPurchaseSuccessModalMessage(null);
    setPurchaseDeliveryLink(null);
    setPurchaseDeliveryTitle(null);
    try {
      const authRedirectPath = typeof window !== 'undefined'
        ? `${window.location.pathname}${window.location.search}`
        : productPath;
      const returnUrl = typeof window !== 'undefined'
        ? `${window.location.origin}${window.location.pathname}`
        : productPath;
      const response = await fetch(`${API_BASE_URL}/public/client-page/${pageClientId}/buy/`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          product_id: product.id,
          package_index: pkg.index,
          provider,
          return_url: returnUrl,
        }),
      });

      const rawText = await response.text();
      let payload: PublicBuyProductResponse = {};
      if (rawText.trim()) {
        try {
          payload = JSON.parse(rawText) as PublicBuyProductResponse;
        } catch {
          payload = {};
        }
      }

      if (!response.ok) {
        if (response.status === 401 && typeof window !== 'undefined') {
          window.location.href = `/login?next=${encodeURIComponent(authRedirectPath)}&tenant_id=${pageClientId}`;
          return;
        }
        const detail = parseResponseDetail(rawText);
        setPurchaseError(detail || 'Не удалось создать оплату.');
        return;
      }

      const paymentId = String(payload?.id ?? '').trim();
      const paymentUrl = String(payload?.payment_url ?? payload?.confirmation_url ?? '').trim();
      if (!paymentId || !paymentUrl) {
        setPurchaseError('Не удалось создать оплату.');
        return;
      }

      if (typeof window !== 'undefined') {
        window.localStorage.setItem(
          getPendingProductPurchaseStorageKey(pageClientId, product.id),
          JSON.stringify({
            paymentId,
            productId: product.id,
            packageIndex: pkg.index,
            createdAt: Date.now(),
          })
        );
        window.location.href = paymentUrl;
      }
    } catch {
      setPurchaseError('Не удалось создать оплату.');
    } finally {
      setBuyingPackageIndex(null);
    }
  };

  const handleRequestProvider = (pkg: ProductPackage) => {
    if (pkg.price === null || buyingPackageIndex !== null) {
      return;
    }
    setPurchaseError(null);
    setPendingPackage(pkg);
    setProviderDialogOpen(true);
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-2xl border p-6 text-sm text-muted-foreground">Загрузка продукта...</div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="mx-auto max-w-3xl p-6 space-y-4">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">
          {error || 'Продукт не найден.'}
        </div>
        <Link href={productsPath} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent">
          К списку продуктов
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-6 space-y-4">
      <div className="rounded-2xl border p-6 shadow-sm space-y-2">
        <div className="text-sm text-muted-foreground">{displayClient}</div>
        <h1 className="text-2xl font-semibold">{productName}</h1>
        <Link href={productsPath} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent">
          К списку продуктов
        </Link>
      </div>

      <div className="rounded-2xl border p-6 shadow-sm space-y-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Название</div>
          <div className="mt-1 text-sm font-medium">{productName}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Краткое описание</div>
          <div className="mt-1 text-sm">{shortDescription || 'Не указано'}</div>
        </div>
        <div>
          <div className="text-xs uppercase tracking-wide text-muted-foreground">Описание</div>
          {descriptionHtml ? (
            <div className="tiptap prose prose-slate mt-2 max-w-none" dangerouslySetInnerHTML={{ __html: descriptionHtml }} />
          ) : (
            <div className="mt-1 text-sm text-muted-foreground">Не указано</div>
          )}
        </div>
      </div>

      <div className="rounded-2xl border p-6 shadow-sm space-y-3">
        <h2 className="text-xl font-semibold">Пакеты</h2>

        {packages.length === 0 ? (
          <div className="text-sm text-muted-foreground">Пакеты пока не добавлены.</div>
        ) : (
          <div className="space-y-2">
            {packages.map((pkg) => (
              <div key={pkg.index} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-medium">{pkg.name}</div>
                    {pkg.description && <div className="mt-1 text-sm text-muted-foreground">{pkg.description}</div>}
                  </div>
                  <div className="text-right">
                    <div className="text-base font-semibold">
                      {pkg.price === null ? 'Цена не указана' : rubFormatter.format(pkg.price)}
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRequestProvider(pkg)}
                      disabled={pkg.price === null || buyingPackageIndex !== null}
                      className="mt-2 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-accent disabled:opacity-60"
                    >
                      {buyingPackageIndex === pkg.index ? 'Переход к оплате...' : 'Купить'}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="text-xs text-muted-foreground">
          Для покупки войдите как контакт через Telegram или VK на странице клиента.
        </div>
        {purchaseStatusLoading && (
          <div className="text-sm text-muted-foreground">Проверяем оплату...</div>
        )}
        {purchaseStatusError && <div className="text-sm text-amber-700">{purchaseStatusError}</div>}
        {purchaseError && <div className="text-sm text-red-600">{purchaseError}</div>}
      </div>

      <Dialog
        open={providerDialogOpen}
        onOpenChange={(open) => {
          if (!open && buyingPackageIndex !== null) return;
          setProviderDialogOpen(open);
          if (!open) {
            setPendingPackage(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Выберите способ оплаты</DialogTitle>
            <DialogDescription>
              {pendingPackage ? `Пакет: ${pendingPackage.name}` : 'Выберите провайдера для оплаты.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            {(['yookassa', 'tbank'] as PaymentProvider[]).map((provider) => (
              <button
                key={provider}
                type="button"
                onClick={() => {
                  if (!pendingPackage) return;
                  void handleBuyPackage(pendingPackage, provider);
                }}
                disabled={!pendingPackage || buyingPackageIndex !== null}
                className="w-full rounded-lg border px-3 py-2 text-sm font-medium text-left hover:bg-accent disabled:opacity-60"
              >
                {buyingPackageIndex !== null ? 'Переход к оплате...' : `Купить через ${PAYMENT_PROVIDER_LABELS[provider]}`}
              </button>
            ))}
            <button
              type="button"
              onClick={() => {
                if (buyingPackageIndex !== null) return;
                setProviderDialogOpen(false);
                setPendingPackage(null);
              }}
              disabled={buyingPackageIndex !== null}
              className="w-full rounded-lg border px-3 py-2 text-sm hover:bg-accent disabled:opacity-60"
            >
              Отмена
            </button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={purchaseSuccessModalOpen} onOpenChange={setPurchaseSuccessModalOpen}>
        <DialogContent className="sm:max-w-md bg-white text-gray-900 dark:bg-white dark:text-gray-900 dark:border-gray-200">
          <DialogHeader>
            <DialogTitle>Покупка успешно оформлена</DialogTitle>
            <DialogDescription className="text-gray-600 dark:text-gray-600">
              {purchaseSuccessModalMessage || 'Оплата прошла успешно.'}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="text-sm text-gray-600">
              Подтверждение отправлено в ваш основной мессенджер (Telegram или VK).
            </div>
          {purchaseDeliveryLink && (
            <a
              href={purchaseDeliveryLink}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent"
            >
              {purchaseDeliveryTitle || 'Открыть курс'}
            </a>
          )}
            <div>
              <button
                type="button"
                onClick={() => setPurchaseSuccessModalOpen(false)}
                className="rounded-lg border px-3 py-2 text-sm hover:bg-accent"
              >
                Понятно
              </button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
