'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Copy, ExternalLink } from 'lucide-react';
import { clientApi } from '@/lib/api/client';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { type ClientProduct } from '@/lib/types';
import {
  DEFAULT_TENANT_TIMEZONE,
  formatInTenantTimezone,
  localDateTimeStringToUtcISOString,
  normalizeTenantTimezone,
  toTenantDate,
} from '@/lib/timezone';

const copyTextToClipboard = async (value: string): Promise<void> => {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  if (typeof document === 'undefined') {
    throw new Error('Clipboard is unavailable');
  }

  const textarea = document.createElement('textarea');
  textarea.value = value;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.top = '-9999px';
  document.body.appendChild(textarea);
  textarea.select();

  const copied = document.execCommand('copy');
  document.body.removeChild(textarea);

  if (!copied) {
    throw new Error('Copy failed');
  }
};

const EVENT_PRODUCT_TYPE_KEYS = new Set(['мероприятие', 'event']);

type ParsedProductEventDate = {
  date: Date;
  hasTime: boolean;
};

type EventProductRow = {
  id: number;
  productName: string;
  eventTitle: string;
  dateLabel: string;
  locationLabel: string;
  durationLabel: string;
  priceLabel: string;
  startTimestamp: number;
};

const isEventProductType = (product: ClientProduct): boolean => {
  const typeName = (product.product_type_name ?? product.product_type?.name ?? '').trim().toLowerCase();
  return EVENT_PRODUCT_TYPE_KEYS.has(typeName);
};

const parseProductEventDate = (rawValue: unknown, timezone: string): ParsedProductEventDate | null => {
  const raw = String(rawValue ?? '').trim();
  if (!raw) {
    return null;
  }

  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})$/i.test(raw)) {
    const tenantDate = toTenantDate(raw, timezone);
    if (Number.isNaN(tenantDate.getTime())) {
      return null;
    }
    return { date: tenantDate, hasTime: true };
  }

  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(raw)) {
    const utcValue = localDateTimeStringToUtcISOString(raw, timezone);
    if (!utcValue) {
      return null;
    }
    const tenantDate = toTenantDate(utcValue, timezone);
    if (Number.isNaN(tenantDate.getTime())) {
      return null;
    }
    return { date: tenantDate, hasTime: true };
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) {
    const utcValue = localDateTimeStringToUtcISOString(`${raw}T12:00`, timezone);
    if (!utcValue) {
      return null;
    }
    const tenantDate = toTenantDate(utcValue, timezone);
    if (Number.isNaN(tenantDate.getTime())) {
      return null;
    }
    return { date: tenantDate, hasTime: false };
  }

  return null;
};

const formatParsedProductEventDate = (parsed: ParsedProductEventDate, timezone: string): string => {
  const options: Intl.DateTimeFormatOptions = parsed.hasTime
    ? {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }
    : {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      };
  return formatInTenantTimezone(parsed.date, timezone, options);
};

const resolveMinPackagePrice = (product: ClientProduct): number | null => {
  if (!Array.isArray(product.packages)) {
    return null;
  }

  const prices = product.packages
    .map((pkg) => {
      const raw = (pkg as { price?: unknown })?.price;
      if (typeof raw === 'number' && Number.isFinite(raw)) {
        return raw;
      }
      if (typeof raw === 'string') {
        const parsed = Number.parseFloat(raw.replace(',', '.'));
        return Number.isFinite(parsed) ? parsed : null;
      }
      return null;
    })
    .filter((value): value is number => value !== null && value > 0);

  if (!prices.length) {
    return null;
  }

  return Math.min(...prices);
};

export function SiteTab() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [clientId, setClientId] = useState<number | null>(null);
  const [timezone, setTimezone] = useState(DEFAULT_TENANT_TIMEZONE);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingError, setLoadingError] = useState<string | null>(null);

  const activeSitePage = searchParams.get('sitePage') ?? '';
  const isEventsPage = activeSitePage === 'events';

  const buildSiteUrl = useCallback(
    (sitePage: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set('tab', 'site');
      if (sitePage) {
        params.set('sitePage', sitePage);
      } else {
        params.delete('sitePage');
      }
      return `/settings?${params.toString()}`;
    },
    [searchParams]
  );

  useEffect(() => {
    const loadClientInfo = async () => {
      try {
        setLoading(true);
        setLoadingError(null);
        const [info, settings, productsData] = await Promise.all([
          clientApi.info(),
          clientApi.getSettings(),
          clientProductsApi.list(),
        ]);
        setClientId(info.client.id);
        setTimezone(normalizeTenantTimezone(settings.timezone));
        setProducts(productsData);
      } catch {
        setClientId(null);
        setLoadingError('Не удалось загрузить список мероприятий.');
      } finally {
        setLoading(false);
      }
    };
    void loadClientInfo();
  }, []);

  const publicPagePath = useMemo(() => (clientId ? `/c/${clientId}` : ''), [clientId]);
  const publicPageEditorPath = useMemo(() => (publicPagePath ? `${publicPagePath}/edit` : ''), [publicPagePath]);
  const quizEditorPath = useMemo(() => (publicPagePath ? `${publicPagePath}/quiz/edit` : ''), [publicPagePath]);
  const publicEventsPath = useMemo(() => (publicPagePath ? `${publicPagePath}/events` : ''), [publicPagePath]);
  const publicPageShareUrl = useMemo(() => {
    if (!publicPagePath) {
      return '';
    }
    if (typeof window === 'undefined') {
      return publicPagePath;
    }
    return `${window.location.origin}${publicPagePath}`;
  }, [publicPagePath]);
  const publicEventsShareUrl = useMemo(() => {
    if (!publicEventsPath) {
      return '';
    }
    if (typeof window === 'undefined') {
      return publicEventsPath;
    }
    return `${window.location.origin}${publicEventsPath}`;
  }, [publicEventsPath]);

  const handleCopyPublicPageLink = useCallback(async () => {
    if (!publicPageShareUrl) {
      toast.error('Ссылка пока недоступна');
      return;
    }
    try {
      await copyTextToClipboard(publicPageShareUrl);
      toast.success('Ссылка скопирована');
    } catch {
      toast.error('Не удалось скопировать ссылку');
    }
  }, [publicPageShareUrl]);

  const handleCopyEventsLink = useCallback(async () => {
    if (!publicEventsShareUrl) {
      toast.error('Ссылка пока недоступна');
      return;
    }
    try {
      await copyTextToClipboard(publicEventsShareUrl);
      toast.success('Ссылка скопирована');
    } catch {
      toast.error('Не удалось скопировать ссылку');
    }
  }, [publicEventsShareUrl]);

  const rubFormatter = useMemo(
    () =>
      new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 2,
      }),
    []
  );

  const eventProducts = useMemo<EventProductRow[]>(() => {
    return products
      .filter((product) => isEventProductType(product))
      .map((product) => {
        const eventData = product.structure?.event;
        const parsedDate = parseProductEventDate(eventData?.date, timezone);
        const dateLabel = parsedDate
          ? formatParsedProductEventDate(parsedDate, timezone)
          : String(eventData?.date ?? '').trim() || 'Дата не указана';
        const durationRaw = eventData?.duration_minutes;
        const durationLabel =
          typeof durationRaw === 'number' && Number.isFinite(durationRaw) && durationRaw > 0
            ? `${Math.round(durationRaw)} мин`
            : '';
        const minPackagePrice = resolveMinPackagePrice(product);
        const priceLabel = minPackagePrice !== null ? `от ${rubFormatter.format(minPackagePrice)}` : '';

        return {
          id: product.id,
          productName: (product.name || '').trim() || `Продукт #${product.id}`,
          eventTitle: (eventData?.title || '').trim() || (product.name || '').trim() || `Продукт #${product.id}`,
          dateLabel,
          locationLabel: String(eventData?.location ?? '').trim() || 'Не указано',
          durationLabel,
          priceLabel,
          startTimestamp: parsedDate ? parsedDate.date.getTime() : Number.POSITIVE_INFINITY,
        };
      })
      .sort((a, b) => a.startTimestamp - b.startTimestamp);
  }, [products, rubFormatter, timezone]);

  if (isEventsPage) {
    return (
      <div className="space-y-3 rounded-lg border bg-background p-5">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold">Мероприятия</h2>
            <p className="text-sm text-muted-foreground">
              Список берётся из продуктов типа «Мероприятие».
            </p>
          </div>
          <div className="flex items-center gap-1">
            {publicEventsPath && (
              <a
                href={publicEventsPath}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-input bg-background text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                aria-label="Открыть публичную страницу мероприятий"
                title="Открыть публичную страницу мероприятий"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            )}
            <Button type="button" variant="outline" onClick={() => router.replace(buildSiteUrl(null))}>
              Назад
            </Button>
          </div>
        </div>

        {loading && <p className="text-sm text-muted-foreground">Загрузка мероприятий...</p>}
        {!loading && loadingError && <p className="text-sm text-red-500">{loadingError}</p>}
        {!loading && !loadingError && eventProducts.length === 0 && (
          <p className="text-sm text-muted-foreground">Пока нет продуктов типа «Мероприятие».</p>
        )}

        {!loading && !loadingError && eventProducts.length > 0 && (
          <div className="space-y-2">
            {eventProducts.map((item) => (
              <div key={item.id} className="rounded-md border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.eventTitle}</p>
                    <Link href={`/product/${item.id}`} className="text-xs text-blue-600 hover:underline">
                      {item.productName}
                    </Link>
                  </div>
                  {(item.durationLabel || item.priceLabel) && (
                    <div className="shrink-0 text-right text-xs text-muted-foreground">
                      {item.durationLabel && <p>{item.durationLabel}</p>}
                      {item.priceLabel && <p>{item.priceLabel}</p>}
                    </div>
                  )}
                </div>
                <div className="mt-2 grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
                  <p>Дата: {item.dateLabel}</p>
                  <p>Локация: {item.locationLabel}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3 rounded-lg border bg-background p-5">
      <div>
        <h2 className="text-base font-semibold">Мои страницы</h2>
        <p className="text-sm text-muted-foreground">
          Управление публичной страницей клиента и квизом.
        </p>
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">1.</span>
          {publicPageEditorPath ? (
            <Link href={publicPageEditorPath} className="text-blue-600 hover:underline">
              Одностраничный сайт
            </Link>
          ) : (
            <span className="text-muted-foreground">Одностраничный сайт</span>
          )}
          {publicPagePath ? (
            <>
              <span className="text-muted-foreground">·</span>
              <a
                href={publicPagePath}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline"
              >
                {publicPagePath}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => void handleCopyPublicPageLink()}
                aria-label="Скопировать ссылку на мою страницу"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </>
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">2.</span>
          {quizEditorPath ? (
            <Link href={quizEditorPath} className="text-blue-600 hover:underline">
              Квиз (опросник)
            </Link>
          ) : (
            <span className="text-muted-foreground">Квиз (опросник)</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">3.</span>
          <Link href={buildSiteUrl('events')} className="text-blue-600 hover:underline">
            Мероприятия
          </Link>
          {publicEventsPath && (
            <>
              <span className="text-muted-foreground">·</span>
              <a
                href={publicEventsPath}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline"
              >
                {publicEventsPath}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => void handleCopyEventsLink()}
                aria-label="Скопировать ссылку на страницу мероприятий"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
          {!loading && !loadingError && (
            <span className="text-xs text-muted-foreground">({eventProducts.length})</span>
          )}
        </div>
      </div>
    </div>
  );
}
