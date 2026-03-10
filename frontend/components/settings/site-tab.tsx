'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Copy, ExternalLink } from 'lucide-react';
import { clientApi } from '@/lib/api/client';
import { clientProductsApi } from '@/lib/api/clientProducts';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
const CUSTOM_DOMAIN_CNAME_TARGET = 'fibonatty.ru';

const normalizeCustomDomainInput = (value: string): string => {
  const raw = value.trim().toLowerCase();
  if (!raw) {
    return '';
  }
  try {
    const parsed = new URL(raw.includes('://') ? raw : `https://${raw}`);
    return parsed.hostname.trim().toLowerCase().replace(/\.$/, '');
  } catch {
    return raw.replace(/^https?:\/\//, '').split('/')[0]?.split(':')[0]?.trim().replace(/\.$/, '') ?? '';
  }
};

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

type PublicProductRow = {
  id: number;
  productName: string;
  typeLabel: string;
  shortDescription: string;
  priceLabel: string;
  publicPath: string;
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
  const [customDomainInput, setCustomDomainInput] = useState('');
  const [customDomainValue, setCustomDomainValue] = useState('');
  const [domainVerified, setDomainVerified] = useState(false);
  const [domainStatusMessage, setDomainStatusMessage] = useState<string | null>(null);
  const [savingDomain, setSavingDomain] = useState(false);
  const [verifyingDomain, setVerifyingDomain] = useState(false);
  const [browserOrigin, setBrowserOrigin] = useState('');

  const activeSitePage = searchParams.get('sitePage') ?? '';
  const isEventsPage = activeSitePage === 'events';
  const isProductsPage = activeSitePage === 'products';
  const isTasksPage = activeSitePage === 'tasks';

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
        const normalizedDomain = normalizeCustomDomainInput(String(settings.custom_domain ?? ''));
        setCustomDomainInput(normalizedDomain);
        setCustomDomainValue(normalizedDomain);
        setDomainVerified(Boolean(settings.domain_verified) && Boolean(normalizedDomain));
        setDomainStatusMessage(null);
      } catch {
        setClientId(null);
        setLoadingError('Не удалось загрузить данные страницы.');
      } finally {
        setLoading(false);
      }
    };
    void loadClientInfo();
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setBrowserOrigin(window.location.origin);
    }
  }, []);

  const publicPagePath = useMemo(() => (clientId ? `/c/${clientId}` : ''), [clientId]);
  const customDomainEnabled = Boolean(customDomainValue) && domainVerified;
  const publicRouteBasePath = useMemo(() => {
    if (customDomainEnabled) {
      return '';
    }
    return publicPagePath;
  }, [customDomainEnabled, publicPagePath]);
  const publicPageEditorPath = useMemo(() => (publicPagePath ? `${publicPagePath}/edit` : ''), [publicPagePath]);
  const quizEditorPath = useMemo(() => (publicPagePath ? `${publicPagePath}/quiz/edit` : ''), [publicPagePath]);
  const publicEventsPath = useMemo(
    () => (publicRouteBasePath ? `${publicRouteBasePath}/events` : '/events'),
    [publicRouteBasePath]
  );
  const publicProductsPath = useMemo(
    () => (publicRouteBasePath ? `${publicRouteBasePath}/products` : '/products'),
    [publicRouteBasePath]
  );
  const publicTasksPath = useMemo(
    () => (publicRouteBasePath ? `${publicRouteBasePath}/tasks` : '/tasks'),
    [publicRouteBasePath]
  );
  const publicPageShareUrl = useMemo(() => {
    if (customDomainEnabled && customDomainValue) {
      return `https://${customDomainValue}`;
    }
    if (!publicRouteBasePath) {
      return '';
    }
    return browserOrigin ? `${browserOrigin}${publicRouteBasePath}` : publicRouteBasePath;
  }, [browserOrigin, customDomainEnabled, customDomainValue, publicRouteBasePath]);
  const publicEventsShareUrl = useMemo(() => {
    if (customDomainEnabled && customDomainValue) {
      return `https://${customDomainValue}/events`;
    }
    if (!publicEventsPath) {
      return '';
    }
    return browserOrigin ? `${browserOrigin}${publicEventsPath}` : publicEventsPath;
  }, [browserOrigin, customDomainEnabled, customDomainValue, publicEventsPath]);
  const publicProductsShareUrl = useMemo(() => {
    if (customDomainEnabled && customDomainValue) {
      return `https://${customDomainValue}/products`;
    }
    if (!publicProductsPath) {
      return '';
    }
    return browserOrigin ? `${browserOrigin}${publicProductsPath}` : publicProductsPath;
  }, [browserOrigin, customDomainEnabled, customDomainValue, publicProductsPath]);
  const publicTasksShareUrl = useMemo(() => {
    if (customDomainEnabled && customDomainValue) {
      return `https://${customDomainValue}/tasks`;
    }
    if (!publicTasksPath) {
      return '';
    }
    return browserOrigin ? `${browserOrigin}${publicTasksPath}` : publicTasksPath;
  }, [browserOrigin, customDomainEnabled, customDomainValue, publicTasksPath]);

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

  const handleCopyProductsLink = useCallback(async () => {
    if (!publicProductsShareUrl) {
      toast.error('Ссылка пока недоступна');
      return;
    }
    try {
      await copyTextToClipboard(publicProductsShareUrl);
      toast.success('Ссылка скопирована');
    } catch {
      toast.error('Не удалось скопировать ссылку');
    }
  }, [publicProductsShareUrl]);

  const handleCopyTasksLink = useCallback(async () => {
    if (!publicTasksShareUrl) {
      toast.error('Ссылка пока недоступна');
      return;
    }
    try {
      await copyTextToClipboard(publicTasksShareUrl);
      toast.success('Ссылка скопирована');
    } catch {
      toast.error('Не удалось скопировать ссылку');
    }
  }, [publicTasksShareUrl]);

  const handleSaveCustomDomain = useCallback(async () => {
    const normalizedDomain = normalizeCustomDomainInput(customDomainInput);
    setSavingDomain(true);
    setDomainStatusMessage(null);
    try {
      const payload = await clientApi.updateSettings({
        custom_domain: normalizedDomain || null,
      });
      const savedDomain = normalizeCustomDomainInput(String(payload.custom_domain ?? ''));
      setCustomDomainInput(savedDomain);
      setCustomDomainValue(savedDomain);
      setDomainVerified(Boolean(payload.domain_verified) && Boolean(savedDomain));
      setDomainStatusMessage(
        savedDomain
          ? 'Домен сохранен. Нажмите «Проверить подключение» после настройки DNS.'
          : 'Свой домен очищен.'
      );
      toast.success(savedDomain ? 'Домен сохранен' : 'Свой домен очищен');
    } catch {
      toast.error('Не удалось сохранить свой домен');
    } finally {
      setSavingDomain(false);
    }
  }, [customDomainInput]);

  const handleVerifyCustomDomain = useCallback(async () => {
    const normalizedDomain = normalizeCustomDomainInput(customDomainInput || customDomainValue);
    if (!normalizedDomain) {
      toast.error('Укажите домен для проверки');
      return;
    }

    setVerifyingDomain(true);
    setDomainStatusMessage(null);
    try {
      const result = await clientApi.verifyCustomDomain(normalizedDomain);
      setCustomDomainInput(result.domain);
      setCustomDomainValue(result.domain);
      setDomainVerified(Boolean(result.verified));
      if (result.verified) {
        const viaMethod = result.method === 'cname' ? 'CNAME' : 'A/AAAA';
        const message = `Домен подтвержден (${viaMethod}).`;
        setDomainStatusMessage(message);
        toast.success(message);
      } else {
        const message = result.error || 'Домен пока не подтвержден. Проверьте DNS и повторите проверку.';
        setDomainStatusMessage(message);
        toast.error('Домен не подтвержден');
      }
    } catch {
      toast.error('Не удалось проверить домен');
    } finally {
      setVerifyingDomain(false);
    }
  }, [customDomainInput, customDomainValue]);

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

  const publicProducts = useMemo<PublicProductRow[]>(() => {
    return products
      .filter((product) => product.status === 'active' || !product.status)
      .filter((product) => !isEventProductType(product))
      .map((product) => {
        const minPackagePrice = resolveMinPackagePrice(product);
        const publicPath = customDomainEnabled && customDomainValue
          ? `https://${customDomainValue}/products/${product.id}`
          : clientId
            ? `/c/${clientId}/products/${product.id}`
            : '';
        return {
          id: product.id,
          productName: (product.name || '').trim() || `Продукт #${product.id}`,
          typeLabel: (product.product_type_name || product.product_type?.name || '').trim() || 'Без типа',
          shortDescription: (product.short_description || '').trim(),
          priceLabel: minPackagePrice !== null ? `от ${rubFormatter.format(minPackagePrice)}` : '',
          publicPath,
        };
      })
      .sort((a, b) => a.productName.localeCompare(b.productName, 'ru'));
  }, [clientId, customDomainEnabled, customDomainValue, products, rubFormatter]);

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
            {publicEventsShareUrl && (
              <a
                href={publicEventsShareUrl}
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
              <Link
                key={item.id}
                href={`/product/${item.id}`}
                className="block rounded-md border p-3 transition-colors hover:bg-accent/30"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.eventTitle}</p>
                    <p className="text-xs text-blue-600">{item.productName}</p>
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
              </Link>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (isProductsPage) {
    return (
      <div className="space-y-3 rounded-lg border bg-background p-5">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold">Продукты</h2>
            <p className="text-sm text-muted-foreground">
              Список берётся из активных продуктов (кроме типа «Мероприятие»).
            </p>
          </div>
          <div className="flex items-center gap-1">
            {publicProductsShareUrl && (
              <a
                href={publicProductsShareUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-input bg-background text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                aria-label="Открыть публичную страницу продуктов"
                title="Открыть публичную страницу продуктов"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            )}
            <Button type="button" variant="outline" onClick={() => router.replace(buildSiteUrl(null))}>
              Назад
            </Button>
          </div>
        </div>

        {loading && <p className="text-sm text-muted-foreground">Загрузка продуктов...</p>}
        {!loading && loadingError && <p className="text-sm text-red-500">{loadingError}</p>}
        {!loading && !loadingError && publicProducts.length === 0 && (
          <p className="text-sm text-muted-foreground">Пока нет активных продуктов.</p>
        )}

        {!loading && !loadingError && publicProducts.length > 0 && (
          <div className="space-y-2">
            {publicProducts.map((item) => (
              <div key={item.id} className="rounded-md border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.productName}</p>
                    {item.publicPath ? (
                      <a
                        href={item.publicPath}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline"
                      >
                        {item.typeLabel}
                        <ExternalLink className="h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <span className="text-xs text-muted-foreground">{item.typeLabel}</span>
                    )}
                  </div>
                  {item.priceLabel && <div className="shrink-0 text-right text-xs text-muted-foreground">{item.priceLabel}</div>}
                </div>
                {item.shortDescription && <p className="mt-2 text-xs text-muted-foreground">{item.shortDescription}</p>}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (isTasksPage) {
    return (
      <div className="space-y-3 rounded-lg border bg-background p-5">
        <div className="flex items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold">Задания</h2>
            <p className="text-sm text-muted-foreground">
              Контакт видит только свои задания после входа через Telegram/VK.
            </p>
          </div>
          <div className="flex items-center gap-1">
            {publicTasksShareUrl && (
              <a
                href={publicTasksShareUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-input bg-background text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                aria-label="Открыть публичную страницу заданий"
                title="Открыть публичную страницу заданий"
              >
                <ExternalLink className="h-4 w-4" />
              </a>
            )}
            <Button type="button" variant="outline" onClick={() => router.replace(buildSiteUrl(null))}>
              Назад
            </Button>
          </div>
        </div>

        <p className="text-sm text-muted-foreground">
          На странице отображаются задания, привязанные к контакту в CRM.
        </p>
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
      <div className="space-y-3 rounded-md border p-3">
        <div>
          <h3 className="text-sm font-semibold">Свой домен</h3>
          <p className="text-xs text-muted-foreground">
            Укажите домен и добавьте DNS запись CNAME: <span className="font-mono">www</span>{' -> '}
            <span className="font-mono">{CUSTOM_DOMAIN_CNAME_TARGET}</span>
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input
            value={customDomainInput}
            onChange={(event) => setCustomDomainInput(event.target.value)}
            placeholder="example.com или www.example.com"
            autoCapitalize="none"
            autoCorrect="off"
            spellCheck={false}
          />
          <Button type="button" variant="outline" onClick={() => void handleSaveCustomDomain()} disabled={savingDomain}>
            {savingDomain ? 'Сохраняем...' : 'Сохранить'}
          </Button>
          <Button type="button" onClick={() => void handleVerifyCustomDomain()} disabled={verifyingDomain}>
            {verifyingDomain ? 'Проверяем...' : 'Проверить подключение'}
          </Button>
        </div>
        <div className="text-xs text-muted-foreground">
          {!customDomainValue
            ? 'Домен не задан.'
            : domainVerified
              ? `Домен подтвержден: ${customDomainValue}`
              : `Домен ожидает верификацию: ${customDomainValue}`}
        </div>
        {domainStatusMessage && (
          <div className={`text-xs ${domainVerified ? 'text-green-700' : 'text-amber-700'}`}>
            {domainStatusMessage}
          </div>
        )}
      </div>
      <div className="space-y-2 text-sm">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">1.</span>
          {publicPageEditorPath ? (
            <Link href={publicPageEditorPath} className="text-blue-600 hover:underline">
              Страницы сайта
            </Link>
          ) : (
            <span className="text-muted-foreground">Страницы сайта</span>
          )}
          {publicPageShareUrl ? (
            <>
              <span className="text-muted-foreground">·</span>
              <a
                href={publicPageShareUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline"
              >
                {publicPageShareUrl}
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
          {publicEventsShareUrl && (
            <>
              <span className="text-muted-foreground">·</span>
              <a
                href={publicEventsShareUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline"
              >
                {publicEventsShareUrl}
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
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">4.</span>
          <Link href={buildSiteUrl('products')} className="text-blue-600 hover:underline">
            Продукты
          </Link>
          {publicProductsShareUrl && (
            <>
              <span className="text-muted-foreground">·</span>
              <a
                href={publicProductsShareUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline"
              >
                {publicProductsShareUrl}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => void handleCopyProductsLink()}
                aria-label="Скопировать ссылку на страницу продуктов"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
          {!loading && !loadingError && (
            <span className="text-xs text-muted-foreground">({publicProducts.length})</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-muted-foreground">5.</span>
          <Link href={buildSiteUrl('tasks')} className="text-blue-600 hover:underline">
            Задания
          </Link>
          {publicTasksShareUrl && (
            <>
              <span className="text-muted-foreground">·</span>
              <a
                href={publicTasksShareUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-blue-600 hover:underline"
              >
                {publicTasksShareUrl}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => void handleCopyTasksLink()}
                aria-label="Скопировать ссылку на страницу заданий"
              >
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
