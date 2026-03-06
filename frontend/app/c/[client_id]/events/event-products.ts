import type { ClientProduct } from '@/lib/types';
import {
  formatInTenantTimezone,
  localDateTimeStringToUtcISOString,
  toTenantDate,
} from '@/lib/timezone';

const EVENT_PRODUCT_TYPE_KEYS = new Set(['мероприятие', 'event']);

export type ParsedProductEventDate = {
  date: Date;
  hasTime: boolean;
};

export type EventProductRow = {
  id: number;
  eventTitle: string;
  dateLabel: string;
  locationLabel: string;
  durationLabel: string;
  priceLabel: string;
  shortDescription: string;
  startTimestamp: number;
};

export const isProductActive = (product: ClientProduct): boolean => {
  if (!product.status) {
    return true;
  }
  return product.status === 'active';
};

export const isEventProductType = (product: ClientProduct): boolean => {
  const typeName = (product.product_type_name ?? product.product_type?.name ?? '').trim().toLowerCase();
  if (EVENT_PRODUCT_TYPE_KEYS.has(typeName)) {
    return true;
  }
  return Boolean(product.structure?.event);
};

export const parseProductEventDate = (rawValue: unknown, timezone: string): ParsedProductEventDate | null => {
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

export const formatParsedProductEventDate = (parsed: ParsedProductEventDate, timezone: string): string => {
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

export const resolveMinPackagePrice = (product: ClientProduct): number | null => {
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

export const buildEventProductRows = (
  products: ClientProduct[],
  timezone: string,
  rubFormatter: Intl.NumberFormat,
): EventProductRow[] => {
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
};
