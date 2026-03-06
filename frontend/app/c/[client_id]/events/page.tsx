'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';
import { ApiError, apiFetch } from '@/lib/api';
import type { ClientProduct } from '@/lib/types';
import {
  DEFAULT_TENANT_TIMEZONE,
  formatInTenantTimezone,
  localDateTimeStringToUtcISOString,
  normalizeTenantTimezone,
  toTenantDate,
} from '@/lib/timezone';

const EVENT_PRODUCT_TYPE_KEYS = new Set(['мероприятие', 'event']);

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

type ParsedProductEventDate = {
  date: Date;
  hasTime: boolean;
};

type EventProductRow = {
  id: number;
  eventTitle: string;
  dateLabel: string;
  locationLabel: string;
  durationLabel: string;
  priceLabel: string;
  shortDescription: string;
  startTimestamp: number;
};

const isProductActive = (product: ClientProduct): boolean => {
  if (!product.status) {
    return true;
  }
  return product.status === 'active';
};

const isEventProductType = (product: ClientProduct): boolean => {
  const typeName = (product.product_type_name ?? product.product_type?.name ?? '').trim().toLowerCase();
  if (EVENT_PRODUCT_TYPE_KEYS.has(typeName)) {
    return true;
  }
  return Boolean(product.structure?.event);
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

export default function PublicEventsPage() {
  const { client_id: rawClientId } = useParams<{ client_id: string }>();
  const pageClientId = Number(rawClientId);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clientName, setClientName] = useState('');
  const [brandName, setBrandName] = useState('');
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [timezone, setTimezone] = useState(DEFAULT_TENANT_TIMEZONE);

  useEffect(() => {
    const loadPublicEventsPage = async () => {
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
        setTimezone(normalizeTenantTimezone(data?.settings?.timezone));
        setProducts(Array.isArray(data?.products) ? data.products : []);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          setError('Страница мероприятий не найдена.');
        } else {
          setError('Не удалось загрузить мероприятия.');
        }
      } finally {
        setLoading(false);
      }
    };

    void loadPublicEventsPage();
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

  const eventProducts = useMemo<EventProductRow[]>(() => {
    return products
      .filter((product) => isProductActive(product))
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
          eventTitle: (eventData?.title || '').trim() || (product.name || '').trim() || `Продукт #${product.id}`,
          dateLabel,
          locationLabel: String(eventData?.location ?? '').trim() || 'Не указано',
          durationLabel,
          priceLabel,
          shortDescription: (product.short_description || '').trim(),
          startTimestamp: parsedDate ? parsedDate.date.getTime() : Number.POSITIVE_INFINITY,
        };
      })
      .sort((a, b) => {
        if (a.startTimestamp !== b.startTimestamp) {
          return a.startTimestamp - b.startTimestamp;
        }
        return a.id - b.id;
      });
  }, [products, rubFormatter, timezone]);

  const displayName = brandName || clientName || `Клиент #${pageClientId}`;

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-2xl border p-6 text-sm text-muted-foreground">Загрузка мероприятий...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-6 space-y-4">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">{error}</div>
        <Link href={`/c/${pageClientId}`} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent">
          На страницу клиента
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-6 space-y-4">
      <div className="rounded-2xl border p-6 shadow-sm space-y-2">
        <h1 className="text-2xl font-semibold">Мероприятия</h1>
        <p className="text-sm text-muted-foreground">{displayName}</p>
        <Link href={`/c/${pageClientId}`} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent">
          На страницу клиента
        </Link>
      </div>

      {eventProducts.length === 0 ? (
        <div className="rounded-2xl border p-6 text-sm text-muted-foreground">
          Сейчас нет опубликованных мероприятий.
        </div>
      ) : (
        <div className="space-y-3">
          {eventProducts.map((item) => (
            <Link
              key={item.id}
              href={`/c/${pageClientId}/events/${item.id}`}
              className="block rounded-2xl border p-5 shadow-sm transition-colors hover:border-primary/50 hover:bg-accent/20"
            >
              <article>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <h2 className="text-lg font-semibold">{item.eventTitle}</h2>
                  {(item.durationLabel || item.priceLabel) && (
                    <div className="text-right">
                      {item.durationLabel && <div className="text-sm text-muted-foreground">{item.durationLabel}</div>}
                      {item.priceLabel && <div className="text-base font-semibold">{item.priceLabel}</div>}
                    </div>
                  )}
                </div>
                <div className="mt-3 grid gap-1 text-sm text-muted-foreground sm:grid-cols-2">
                  <p>Дата: {item.dateLabel}</p>
                  <p>Локация: {item.locationLabel}</p>
                </div>
                {item.shortDescription && <p className="mt-3 text-sm text-foreground/90">{item.shortDescription}</p>}
              </article>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
