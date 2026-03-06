'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Image from 'next/image';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { generateHTML } from '@tiptap/html';
import {
  ApiError,
  API_BASE_URL,
  BACKEND_BASE_URL,
  apiFetch,
} from '@/lib/api';
import { clientApi } from '@/lib/api/client';
import { clientProductsApi } from '@/lib/api/clientProducts';
import {
  crmAvailabilityEventsApi,
  crmContactsApi,
  crmEventsApi,
  type AvailabilityEvent,
  type Contact,
  type Event,
} from '@/lib/api/crm';
import type { ClientProduct, ClientSettings } from '@/lib/types';
import { createKbExtensions } from '@/components/kb/tiptapExtensions';
import {
  DEFAULT_TENANT_TIMEZONE,
  formatInTenantTimezone,
  normalizeTenantTimezone,
  tenantDateToUtcISOString,
  toTenantDate,
} from '@/lib/timezone';
import {
  CLIENT_PAGE_BLOCK_DEFAULT_ORDER,
  normalizeClientPageTemplateConfig,
  resolveClientPageVideoSource,
  type ClientPageBlockKey,
} from '@/lib/client-page-template';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import EventsContent from './events/content';
import {
  buildEventProductRows,
  isEventProductType,
  parseProductEventDate,
} from './events/event-products';

type ReferralStatsResponse = {
  has_code?: boolean;
  referral_code?: string;
  referral_url?: string;
  total_referrals?: number;
  invitations?: ReferralInvitation[];
};

type ApplyReferralCodeResponse = {
  ok?: boolean;
  already_applied?: boolean;
  message?: string;
};

type ReferralInvitation = {
  id: number;
  code?: string;
  code_type?: 'client' | 'contact' | string;
  status?: 'pending' | 'registered' | 'rewarded' | 'expired' | string;
  invited_telegram_username?: string;
  created_at?: string;
  registered_at?: string | null;
  rewarded_at?: string | null;
};

type ReferralInvitationsResponse = {
  items?: ReferralInvitation[];
};

type TelegramAuthResponse = {
  user?: {
    telegramId?: string;
    firstName?: string;
    lastName?: string;
    username?: string;
    photoUrl?: string | null;
    authDate?: string;
    isDev?: boolean;
    contactId?: number | null;
    tenantId?: number | null;
  };
};

type VkAuthResponse = {
  user?: {
    vkId?: string;
    firstName?: string;
    lastName?: string;
    username?: string;
    photoUrl?: string | null;
    authDate?: string;
    contactId?: number | null;
    tenantId?: number | null;
  };
};

type PublicClientPageResponse = {
  client?: {
    id?: number;
    name?: string;
  };
  settings?: Partial<ClientSettings> | null;
  products?: ClientProduct[];
  availability_events?: AvailabilityEvent[];
  events?: Event[];
};

type PaymentProvider = 'yookassa' | 'tbank';

type PublicBuyProductResponse = {
  id?: string;
  status?: string;
  provider?: PaymentProvider | string;
  payment_url?: string;
  confirmation_url?: string;
  product_id?: number;
};

type PublicProductPaymentStatusResponse = {
  payment_id?: string;
  provider?: PaymentProvider | string;
  status?: string;
  paid?: boolean;
  delivery?: {
    ready?: boolean;
    url?: string;
    document_id?: number;
    document_title?: string;
    message?: string;
    missing_product_page?: boolean;
  } | null;
};

type ContactPurchaseListItem = {
  id?: number;
  product_id?: number;
  product_name?: string;
  paid_at?: string | null;
  amount?: string | null;
  currency?: string | null;
  payment_id?: string | null;
  package?: {
    index?: number;
    name?: string | null;
    description?: string | null;
    price?: string | number | null;
  } | null;
  delivery?: {
    ready?: boolean;
    url?: string;
    document_id?: number;
    document_title?: string;
    message?: string;
    missing_product_page?: boolean;
  } | null;
  service_package?: {
    enabled?: boolean;
    mode?: 'count' | 'minutes';
    package_name?: string | null;
    total_units?: number;
    used_units?: number;
    remaining_units?: number;
    is_exhausted?: boolean;
    total_label?: string;
    used_label?: string;
    remaining_label?: string;
  } | null;
};

type ContactPurchasesResponse = {
  contact_id?: number;
  items?: ContactPurchaseListItem[];
};

type Slot = {
  id: string;
  startAt: string;
  endAt: string;
};

type BuildSlotsOptions = {
  excludeEventIds?: Set<number>;
  requiredDurationMinutes?: number;
};

type PlannedMeeting = {
  id: number;
  title: string;
  startAt: string;
  endAt: string;
  startMs: number;
  endMs: number;
  durationMinutes: number;
};

const SLOT_LOOKAHEAD_DAYS = 60;
const REFERRAL_STATUS_LABELS: Record<string, string> = {
  pending: 'Ожидает',
  registered: 'Зарегистрирован',
  rewarded: 'Засчитан',
  expired: 'Истек',
};
const PAYMENT_PROVIDER_LABELS: Record<PaymentProvider, string> = {
  yookassa: 'YooKassa',
  tbank: 'T-Bank',
};

const normalizeTiptapJson = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
};

const replaceTemplateTokens = (input: string, values: Record<string, string>) => {
  return input.replace(/\{\{([a-zA-Z0-9_]+)\}\}/g, (_, key: string) => values[key] ?? `{{${key}}}`);
};

const replaceTemplateTokensInTiptapNode = (node: unknown, values: Record<string, string>): unknown => {
  if (typeof node === 'string') {
    return replaceTemplateTokens(node, values);
  }
  if (Array.isArray(node)) {
    return node.map((item) => replaceTemplateTokensInTiptapNode(item, values));
  }
  if (!node || typeof node !== 'object') {
    return node;
  }

  const source = node as Record<string, unknown>;
  const next: Record<string, unknown> = {};
  Object.entries(source).forEach(([key, value]) => {
    if (key === 'text' && typeof value === 'string') {
      next[key] = replaceTemplateTokens(value, values);
      return;
    }
    next[key] = replaceTemplateTokensInTiptapNode(value, values);
  });
  return next;
};

const buildCompactReferralUrl = (stats: ReferralStatsResponse): string => {
  const referralCode = (stats.referral_code || '').trim();
  const botUsername = (process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME || '').trim().replace(/^@/, '');
  if (referralCode && botUsername) {
    return `https://t.me/${botUsername}?start=${referralCode}`;
  }

  const rawUrl = (stats.referral_url || '').trim();
  if (!rawUrl) {
    return '';
  }

  try {
    const parsed = new URL(rawUrl);
    const start = parsed.searchParams.get('start');
    const username = parsed.pathname.replace(/^\/+/, '');
    const host = parsed.hostname.toLowerCase();
    if (start && username && (host === 't.me' || host === 'telegram.me')) {
      return `https://t.me/${username}?start=${start}`;
    }
  } catch {
    return rawUrl;
  }

  return rawUrl;
};

const normalizeReferralCodeInput = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) {
    return '';
  }

  let parsed = trimmed;
  try {
    const url = new URL(trimmed);
    const startParam = url.searchParams.get('start');
    if (startParam) {
      parsed = startParam.trim();
    }
  } catch {
    parsed = trimmed;
  }

  const startMatch = parsed.match(/start=([^&\s]+)/i);
  if (startMatch?.[1]) {
    parsed = startMatch[1];
  }

  const lower = parsed.toLowerCase();
  if (lower.startsWith('ref_c')) {
    return `ref_c${parsed.slice(5).toUpperCase()}`;
  }
  if (lower.startsWith('ref_')) {
    return `ref_${parsed.slice(4).toUpperCase()}`;
  }
  return parsed;
};

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

const fetchTelegramAuthOptional = async (): Promise<TelegramAuthResponse | null> => {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/telegram`, {
      method: 'GET',
      credentials: 'include',
    });
    if (response.status === 401) {
      return null;
    }
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as TelegramAuthResponse;
  } catch {
    return null;
  }
};

const fetchVkAuthOptional = async (): Promise<VkAuthResponse | null> => {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/vk`, {
      method: 'GET',
      credentials: 'include',
    });
    if (response.status === 401) {
      return null;
    }
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as VkAuthResponse;
  } catch {
    return null;
  }
};

const overlaps = (startA: number, endA: number, startB: number, endB: number) =>
  startA < endB && endA > startB;

const normalizeDay = (value: Date) => {
  const out = new Date(value);
  out.setHours(0, 0, 0, 0);
  return out;
};

const addDays = (value: Date, days: number) => {
  const out = new Date(value);
  out.setDate(out.getDate() + days);
  return out;
};

const startOfWeek = (value: Date) => {
  const out = new Date(value);
  const day = out.getDay();
  const diff = (day + 6) % 7;
  out.setDate(out.getDate() - diff);
  out.setHours(0, 0, 0, 0);
  return out;
};

const formatKey = (value: Date) => {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const generateWeekDates = (referenceDate: Date) => {
  const start = startOfWeek(referenceDate);
  return Array.from({ length: 7 }).map((_, index) => {
    const day = new Date(start);
    day.setDate(start.getDate() + index);
    return day;
  });
};

const formatTenantLocalDate = (
  value: Date,
  timeZone: string,
  options: Intl.DateTimeFormatOptions
) => {
  const utcValue = tenantDateToUtcISOString(value, timeZone);
  if (!utcValue) {
    return '';
  }
  return formatInTenantTimezone(utcValue, timeZone, options);
};

const formatMeetingRange = (startAt: string, endAt: string, timeZone: string) => {
  const dateLabel = formatInTenantTimezone(startAt, timeZone, {
    weekday: 'short',
    day: '2-digit',
    month: 'short',
  });
  const startLabel = formatInTenantTimezone(startAt, timeZone, {
    hour: '2-digit',
    minute: '2-digit',
  });
  const endLabel = formatInTenantTimezone(endAt, timeZone, {
    hour: '2-digit',
    minute: '2-digit',
  });
  return `${dateLabel}, ${startLabel} - ${endLabel}`;
};

const getPendingProductPurchaseStorageKey = (clientId: number) => `client-page:pending-product-purchase:${clientId}`;

const availabilityMatchesDate = (baseStart: Date, checkDate: Date, repeatType: AvailabilityEvent['repeat_type']) => {
  const baseDate = normalizeDay(baseStart);
  const targetDate = normalizeDay(checkDate);

  if (targetDate < baseDate) {
    return false;
  }

  if (repeatType === 1) {
    return true;
  }

  if (repeatType === 2) {
    return targetDate.getDay() === baseDate.getDay();
  }

  if (repeatType === 3) {
    return targetDate.getDate() === baseDate.getDate();
  }

  return targetDate.getTime() === baseDate.getTime();
};

const parseProductEventStart = (rawValue: unknown, timezone: string): Date | null => {
  const parsed = parseProductEventDate(rawValue, timezone);
  if (!parsed) {
    return null;
  }
  return parsed.date;
};

const buildProductBusyIntervals = (
  products: ClientProduct[],
  timezone: string
): Array<{ startMs: number; endMs: number }> => {
  return products
    .filter((product) => isEventProductType(product))
    .map((product) => {
      const event = product.structure?.event;
      const start = parseProductEventStart(event?.date, timezone);
      if (!start) {
        return null;
      }
      const durationRaw = event?.duration_minutes;
      const durationMinutes =
        typeof durationRaw === 'number' && Number.isFinite(durationRaw) && durationRaw > 0
          ? Math.max(15, Math.round(durationRaw))
          : 60;
      const end = new Date(start.getTime() + durationMinutes * 60 * 1000);
      return {
        startMs: start.getTime(),
        endMs: end.getTime(),
      };
    })
    .filter((item): item is { startMs: number; endMs: number } => item !== null);
};

const buildSlots = (
  availabilityEvents: AvailabilityEvent[],
  events: Event[],
  products: ClientProduct[],
  timezone: string,
  options?: BuildSlotsOptions
): Slot[] => {
  const tz = normalizeTenantTimezone(timezone);
  const nowTenant = toTenantDate(new Date(), tz);
  const todayTenant = normalizeDay(nowTenant);
  const excludeEventIds = options?.excludeEventIds || new Set<number>();
  const requiredDurationMinutes = Number(options?.requiredDurationMinutes) > 0
    ? Number(options?.requiredDurationMinutes)
    : null;

  const busyIntervals = events
    .filter((event) => event.status === 'scheduled' && !excludeEventIds.has(event.id))
    .map((event) => {
      const start = toTenantDate(event.start_time, tz);
      if (Number.isNaN(start.getTime())) {
        return null;
      }
      const parsedEnd = toTenantDate(event.end_time, tz);
      const end = Number.isNaN(parsedEnd.getTime())
        ? new Date(start.getTime() + 60 * 60 * 1000)
        : parsedEnd;
      return {
        startMs: start.getTime(),
        endMs: end.getTime(),
      };
    })
    .filter((item): item is { startMs: number; endMs: number } => item !== null);

  const productBusyIntervals = buildProductBusyIntervals(products, tz);
  const allBusyIntervals = [...busyIntervals, ...productBusyIntervals];
  const slots: Slot[] = [];

  for (let offset = 0; offset <= SLOT_LOOKAHEAD_DAYS; offset += 1) {
    const checkDate = addDays(todayTenant, offset);

    availabilityEvents.forEach((availability) => {
      const baseStart = toTenantDate(availability.start_time, tz);
      if (Number.isNaN(baseStart.getTime())) {
        return;
      }

      if (!availabilityMatchesDate(baseStart, checkDate, availability.repeat_type)) {
        return;
      }

      const duration = Number(availability.duration_minutes) > 0
        ? Number(availability.duration_minutes)
        : 60;
      if (requiredDurationMinutes !== null && duration < requiredDurationMinutes) {
        return;
      }
      const slotDuration = requiredDurationMinutes ?? duration;

      const startTenant = new Date(checkDate);
      startTenant.setHours(
        baseStart.getHours(),
        baseStart.getMinutes(),
        baseStart.getSeconds(),
        0
      );
      const endTenant = new Date(startTenant.getTime() + slotDuration * 60 * 1000);

      if (endTenant <= nowTenant) {
        return;
      }

      const isBusy = allBusyIntervals.some((busy) =>
        overlaps(startTenant.getTime(), endTenant.getTime(), busy.startMs, busy.endMs)
      );
      if (isBusy) {
        return;
      }

      const startAt = tenantDateToUtcISOString(startTenant, tz);
      const endAt = tenantDateToUtcISOString(endTenant, tz);
      if (!startAt || !endAt) {
        return;
      }

      slots.push({
        id: `${availability.id}:${startAt}`,
        startAt,
        endAt,
      });
    });
  }

  slots.sort((a, b) => new Date(a.startAt).getTime() - new Date(b.startAt).getTime());
  return slots;
};

const resolveProductPrice = (product: ClientProduct): number | null => {
  const packageWithPrice = Array.isArray(product?.packages)
    ? product.packages.find(
      (item) => typeof item?.price === 'number' && Number.isFinite(item.price) && item.price > 0
    )
    : undefined;
  return packageWithPrice?.price ?? null;
};

const isProductActive = (product: ClientProduct): boolean => {
  if (!product?.status) {
    return true;
  }
  return product.status === 'active';
};

const normalizeName = (value: string) => value.trim().toLowerCase();

const resolveBookingContact = (
  contacts: Contact[],
  clientName: string,
  brandName: string
): Contact | null => {
  if (!contacts.length) {
    return null;
  }

  const lookupNames = new Set(
    [clientName, brandName]
      .map((item) => normalizeName(item || ''))
      .filter(Boolean)
  );

  if (lookupNames.size > 0) {
    const byName = contacts.find((contact) => lookupNames.has(normalizeName(contact.name || '')));
    if (byName) {
      return byName;
    }
  }

  return contacts[0];
};

const toPlannedMeeting = (event: Event, timezone: string): PlannedMeeting | null => {
  const startDate = toTenantDate(event.start_time, timezone);
  if (Number.isNaN(startDate.getTime())) {
    return null;
  }
  const parsedEnd = toTenantDate(event.end_time, timezone);
  const endDate = Number.isNaN(parsedEnd.getTime())
    ? new Date(startDate.getTime() + 60 * 60 * 1000)
    : parsedEnd;
  const durationMinutes = Math.max(
    15,
    Math.round((endDate.getTime() - startDate.getTime()) / 60000) || 60
  );

  return {
    id: event.id,
    title: (event.title || 'Встреча').trim() || 'Встреча',
    startAt: tenantDateToUtcISOString(startDate, timezone) ?? event.start_time,
    endAt: tenantDateToUtcISOString(endDate, timezone) ?? event.end_time,
    startMs: startDate.getTime(),
    endMs: endDate.getTime(),
    durationMinutes,
  };
};

export default function ContactClientPage() {
  const { client_id: rawClientId } = useParams<{ client_id: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();

  const pageClientId = Number(rawClientId);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingSlotId, setBookingSlotId] = useState<string | null>(null);
  const [rescheduleMeetingId, setRescheduleMeetingId] = useState<number | null>(null);

  const [activeClientId, setActiveClientId] = useState<number | null>(null);
  const [activeClientName, setActiveClientName] = useState('');
  const [hasTenantSession, setHasTenantSession] = useState(false);
  const [bookingContactId, setBookingContactId] = useState<number | null>(null);
  const [bookingContactName, setBookingContactName] = useState('');
  const [settings, setSettings] = useState<ClientSettings | null>(null);
  const [products, setProducts] = useState<ClientProduct[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [availabilityEvents, setAvailabilityEvents] = useState<AvailabilityEvent[]>([]);
  const [timezone, setTimezone] = useState(DEFAULT_TENANT_TIMEZONE);
  const [weekCursor, setWeekCursor] = useState<Date>(() =>
    startOfWeek(toTenantDate(new Date(), DEFAULT_TENANT_TIMEZONE))
  );

  const [referralLoading, setReferralLoading] = useState(false);
  const [referralCount, setReferralCount] = useState<number>(0);
  const [referralLink, setReferralLink] = useState('');
  const [referralInvitations, setReferralInvitations] = useState<ReferralInvitation[]>([]);
  const [referralError, setReferralError] = useState<string | null>(null);
  const [inviterCodeInput, setInviterCodeInput] = useState('');
  const [inviterCodeLoading, setInviterCodeLoading] = useState(false);
  const [inviterCodeMessage, setInviterCodeMessage] = useState<string | null>(null);
  const [inviterCodeError, setInviterCodeError] = useState<string | null>(null);
  const [selectedPaymentProvider, setSelectedPaymentProvider] = useState<PaymentProvider>('yookassa');
  const [buyingProductId, setBuyingProductId] = useState<number | null>(null);
  const [purchaseStatusLoading, setPurchaseStatusLoading] = useState(false);
  const [purchaseStatusMessage, setPurchaseStatusMessage] = useState<string | null>(null);
  const [purchaseStatusError, setPurchaseStatusError] = useState<string | null>(null);
  const [purchaseDeliveryLink, setPurchaseDeliveryLink] = useState<string | null>(null);
  const [purchaseDeliveryTitle, setPurchaseDeliveryTitle] = useState<string | null>(null);
  const [checkedPurchasePaymentId, setCheckedPurchasePaymentId] = useState<string | null>(null);
  const [purchaseSuccessModalOpen, setPurchaseSuccessModalOpen] = useState(false);
  const [purchaseSuccessModalMessage, setPurchaseSuccessModalMessage] = useState<string | null>(null);
  const [purchasesLoading, setPurchasesLoading] = useState(false);
  const [purchases, setPurchases] = useState<ContactPurchaseListItem[]>([]);
  const [purchasesError, setPurchasesError] = useState<string | null>(null);

  const activeProducts = useMemo(
    () => products.filter((product) => isProductActive(product)),
    [products]
  );
  const rubFormatter = useMemo(
    () =>
      new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        maximumFractionDigits: 2,
      }),
    []
  );
  const eventProducts = useMemo(
    () => buildEventProductRows(activeProducts, timezone, rubFormatter),
    [activeProducts, rubFormatter, timezone]
  );

  const plannedMeetings = useMemo<PlannedMeeting[]>(() => {
    if (!bookingContactId) {
      return [];
    }

    const nowMs = toTenantDate(new Date(), timezone).getTime();

    return events
      .filter((event) => event.status === 'scheduled' && event.contact_id === bookingContactId)
      .map((event) => toPlannedMeeting(event, timezone))
      .filter((event): event is PlannedMeeting => event !== null)
      .filter((event) => event.endMs >= nowMs)
      .sort((a, b) => a.startMs - b.startMs);
  }, [bookingContactId, events, timezone]);
  const selectedMeetingForReschedule = useMemo(
    () => plannedMeetings.find((meeting) => meeting.id === rescheduleMeetingId) || null,
    [plannedMeetings, rescheduleMeetingId]
  );
  const slots = useMemo(
    () =>
      buildSlots(availabilityEvents, events, products, timezone, {
        excludeEventIds: selectedMeetingForReschedule
          ? new Set([selectedMeetingForReschedule.id])
          : undefined,
        requiredDurationMinutes: selectedMeetingForReschedule?.durationMinutes,
      }),
    [availabilityEvents, events, products, selectedMeetingForReschedule, timezone]
  );
  const currentWeekStart = useMemo(
    () => startOfWeek(toTenantDate(new Date(), timezone)),
    [timezone]
  );
  const maxWeekStart = useMemo(
    () => startOfWeek(addDays(currentWeekStart, SLOT_LOOKAHEAD_DAYS)),
    [currentWeekStart]
  );
  const todayKey = useMemo(
    () => formatKey(toTenantDate(new Date(), timezone)),
    [timezone]
  );
  const weekDates = useMemo(
    () => generateWeekDates(weekCursor),
    [weekCursor]
  );
  const canGoPrevWeek = weekCursor.getTime() > currentWeekStart.getTime();
  const canGoNextWeek = weekCursor.getTime() < maxWeekStart.getTime();
  const weekRangeLabel = useMemo(() => {
    const start = weekDates[0];
    const end = weekDates[6];
    if (!start || !end) {
      return '';
    }
    return `${formatTenantLocalDate(start, timezone, { day: '2-digit', month: 'short' })} - ${formatTenantLocalDate(end, timezone, { day: '2-digit', month: 'short' })}`;
  }, [weekDates, timezone]);
  const slotsByDate = useMemo(() => {
    const grouped = new Map<string, Slot[]>();
    slots.forEach((slot) => {
      const slotDate = toTenantDate(slot.startAt, timezone);
      if (Number.isNaN(slotDate.getTime())) {
        return;
      }
      const dayKey = formatKey(slotDate);
      const current = grouped.get(dayKey);
      if (current) {
        current.push(slot);
      } else {
        grouped.set(dayKey, [slot]);
      }
    });
    return grouped;
  }, [slots, timezone]);
  useEffect(() => {
    setWeekCursor(startOfWeek(toTenantDate(new Date(), timezone)));
  }, [timezone]);

  useEffect(() => {
    if (rescheduleMeetingId !== null && !selectedMeetingForReschedule) {
      setRescheduleMeetingId(null);
    }
  }, [rescheduleMeetingId, selectedMeetingForReschedule]);

  useEffect(() => {
    const title = (settings?.brand_name || activeClientName || '').trim();
    if (!title || typeof document === 'undefined') {
      return;
    }
    document.title = title;
  }, [activeClientName, settings?.brand_name]);

  useEffect(() => {
    const loadPage = async () => {
      if (!Number.isFinite(pageClientId) || pageClientId <= 0) {
        setError('Некорректный client_id в URL.');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);
      setHasTenantSession(false);
      setBookingContactId(null);
      setBookingContactName('');

      try {
        const [telegramAuthData, vkAuthData] = await Promise.all([
          fetchTelegramAuthOptional(),
          fetchVkAuthOptional(),
        ]);
        const authData = (() => {
          const tgTenant = Number(telegramAuthData?.user?.tenantId || 0);
          const tgContact = Number(telegramAuthData?.user?.contactId || 0);
          if (Number.isFinite(tgTenant) && Number.isFinite(tgContact) && tgTenant === pageClientId && tgContact > 0) {
            return telegramAuthData;
          }
          const vkTenant = Number(vkAuthData?.user?.tenantId || 0);
          const vkContact = Number(vkAuthData?.user?.contactId || 0);
          if (Number.isFinite(vkTenant) && Number.isFinite(vkContact) && vkTenant === pageClientId && vkContact > 0) {
            return vkAuthData as TelegramAuthResponse;
          }
          return (telegramAuthData || (vkAuthData as TelegramAuthResponse | null));
        })();

        const authTenantId = Number(authData?.user?.tenantId || 0);
        const authContactId = Number(authData?.user?.contactId || 0);
        const boundContactId = Number.isFinite(authContactId) && authContactId > 0
          && (!Number.isFinite(authTenantId) || authTenantId <= 0 || authTenantId === pageClientId)
          ? authContactId
          : null;

        try {
          const [info, settingsData, productsData, availabilityData, eventsData, contactsData] = await Promise.all([
            clientApi.info(),
            clientApi.getSettings(),
            clientProductsApi.list(),
            crmAvailabilityEventsApi.list(),
            crmEventsApi.list(),
            crmContactsApi.list(),
          ]);

          const activeId = Number(info?.client?.id || 0);
          const activeName = (info?.client?.name || '').trim();

          setHasTenantSession(true);
          setActiveClientId(Number.isFinite(activeId) && activeId > 0 ? activeId : null);
          setActiveClientName(activeName);
          setSettings(settingsData);
          setProducts(productsData);
          setAvailabilityEvents(availabilityData);
          setEvents(eventsData);
          setTimezone(normalizeTenantTimezone(settingsData?.timezone));

          if (!Number.isFinite(activeId) || activeId <= 0) {
            setError('Не удалось определить текущего клиента.');
            return;
          }

          if (activeId !== pageClientId) {
            setError(`Страница /c/${pageClientId} недоступна для этого аккаунта. Ваша страница: /c/${activeId}.`);
            return;
          }

          if (boundContactId) {
            const bookingContact = contactsData.find((contact) => contact.id === boundContactId) || null;
            setBookingContactId(bookingContact?.id ?? boundContactId);
            setBookingContactName((bookingContact?.name || '').trim());
          } else {
            setBookingContactId(null);
            setBookingContactName('');
          }
        } catch (privateLoadError) {
          if (!(privateLoadError instanceof ApiError) || privateLoadError.status !== 401) {
            throw privateLoadError;
          }

          const publicData = await apiFetch<PublicClientPageResponse>(`/public/client-page/${pageClientId}/`);
          const publicClientId = Number(publicData?.client?.id || pageClientId);
          const publicClientName = String(publicData?.client?.name || '').trim();
          const publicSettings = (publicData?.settings || null) as ClientSettings | null;

          setHasTenantSession(false);
          setActiveClientId(Number.isFinite(publicClientId) && publicClientId > 0 ? publicClientId : pageClientId);
          setActiveClientName(publicClientName);
          setSettings(publicSettings);
          setProducts(Array.isArray(publicData?.products) ? publicData.products : []);
          setAvailabilityEvents(Array.isArray(publicData?.availability_events) ? publicData.availability_events : []);
          setEvents(Array.isArray(publicData?.events) ? publicData.events : []);
          setTimezone(normalizeTenantTimezone(publicSettings?.timezone));
          setBookingContactId(boundContactId);
          setBookingContactName('');
        }
      } catch (loadError) {
        setError('Не удалось загрузить страницу клиента.');
      } finally {
        setLoading(false);
      }
    };

    void loadPage();
  }, [pageClientId, router]);

  useEffect(() => {
    const loadReferral = async () => {
      if (loading) {
        return;
      }

      if (!bookingContactId) {
        setReferralLoading(false);
        setReferralCount(0);
        setReferralLink('');
        setReferralInvitations([]);
        setReferralError(null);
        return;
      }

      setReferralLoading(true);
      setReferralError(null);
      try {
        const referralParams = new URLSearchParams({ type: 'contact' });
        referralParams.set('contact_id', String(bookingContactId));
        const referralQuery = `?${referralParams.toString()}`;

        let stats = await apiFetch<ReferralStatsResponse>(`${BACKEND_BASE_URL}/core/api/referral/stats/${referralQuery}`);
        if (!stats?.has_code) {
          try {
            await apiFetch(`${BACKEND_BASE_URL}/core/api/referral/create_code/${referralQuery}`, {
              method: 'POST',
            });
          } catch (createError) {
            if (!(createError instanceof ApiError && createError.status === 400)) {
              throw createError;
            }
          }
          stats = await apiFetch<ReferralStatsResponse>(`${BACKEND_BASE_URL}/core/api/referral/stats/${referralQuery}`);
        }

        let invitations = Array.isArray(stats?.invitations) ? stats.invitations : null;
        if (invitations === null) {
          try {
            const invitationsResponse = await apiFetch<ReferralInvitationsResponse>(
              `${BACKEND_BASE_URL}/core/api/referral/invitations/${referralQuery}`
            );
            invitations = Array.isArray(invitationsResponse?.items) ? invitationsResponse.items : [];
          } catch {
            invitations = [];
          }
        }

        setReferralCount(Number(stats?.total_referrals ?? 0));
        setReferralLink(buildCompactReferralUrl(stats));
        setReferralInvitations(invitations);
      } catch (referralLoadError) {
        if (referralLoadError instanceof ApiError && referralLoadError.status === 401) {
          setReferralInvitations([]);
          setReferralError('Войдите как контакт через Telegram или VK, чтобы использовать партнёрскую программу.');
          return;
        }
        setReferralInvitations([]);
        setReferralError('Не удалось загрузить партнёрскую программу.');
      } finally {
        setReferralLoading(false);
      }
    };

    void loadReferral();
  }, [loading, bookingContactId]);

  const loadContactPurchases = useCallback(async () => {
    if (!bookingContactId || !Number.isFinite(pageClientId) || pageClientId <= 0) {
      setPurchasesLoading(false);
      setPurchases([]);
      setPurchasesError(null);
      return;
    }

    setPurchasesLoading(true);
    setPurchasesError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/public/client-page/${pageClientId}/purchases/`, {
        method: 'GET',
        credentials: 'include',
      });
      if (response.status === 401) {
        setPurchases([]);
        setPurchasesError('Войдите как контакт через Telegram или VK, чтобы видеть список покупок.');
        return;
      }
      if (!response.ok) {
        throw new Error('failed to load purchases');
      }
      const payload = (await response.json()) as ContactPurchasesResponse;
      setPurchases(Array.isArray(payload?.items) ? payload.items : []);
    } catch {
      setPurchases([]);
      setPurchasesError('Не удалось загрузить список покупок.');
    } finally {
      setPurchasesLoading(false);
    }
  }, [bookingContactId, pageClientId]);

  const checkProductPurchaseStatus = useCallback(async (paymentId: string) => {
    if (!paymentId || !Number.isFinite(pageClientId) || pageClientId <= 0) {
      return;
    }

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
          ? 'Оплата прошла успешно. Ссылка на продукт доступна ниже.'
          : (delivery?.message || 'Оплата прошла успешно.');
        if (delivery?.ready && delivery.url) {
          setPurchaseDeliveryLink(delivery.url);
          setPurchaseDeliveryTitle((delivery.document_title || '').trim() || 'Открыть продукт');
        } else {
          setPurchaseDeliveryLink(null);
          setPurchaseDeliveryTitle(null);
        }
        setPurchaseStatusMessage(successMessage);
        setPurchaseSuccessModalMessage(successMessage);
        setPurchaseSuccessModalOpen(true);
        if (typeof window !== 'undefined') {
          window.localStorage.removeItem(getPendingProductPurchaseStorageKey(pageClientId));
        }
        void loadContactPurchases();
      } else if (paymentStatus) {
        setPurchaseStatusMessage(`Статус оплаты: ${paymentStatus}. Если вы уже оплатили, обновите страницу через несколько секунд.`);
      } else {
        setPurchaseStatusMessage('Статус оплаты пока не получен.');
      }
    } catch {
      setPurchaseStatusError('Не удалось проверить статус оплаты.');
    } finally {
      setPurchaseStatusLoading(false);
    }
  }, [pageClientId, loadContactPurchases]);

  useEffect(() => {
    if (loading) {
      return;
    }
    if (!bookingContactId) {
      setPurchasesLoading(false);
      setPurchases([]);
      setPurchasesError(null);
      return;
    }
    void loadContactPurchases();
  }, [loading, bookingContactId, loadContactPurchases]);

  useEffect(() => {
    if (loading || !Number.isFinite(pageClientId) || pageClientId <= 0) {
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
        const raw = window.localStorage.getItem(getPendingProductPurchaseStorageKey(pageClientId));
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

    if (!pendingPaymentId || checkedPurchasePaymentId === pendingPaymentId) {
      return;
    }

    setCheckedPurchasePaymentId(pendingPaymentId);
    void checkProductPurchaseStatus(pendingPaymentId);
  }, [loading, pageClientId, searchParams, checkedPurchasePaymentId, checkProductPurchaseStatus]);

  const handleBook = async (slot: Slot) => {
    if (!Number.isFinite(pageClientId) || pageClientId <= 0 || bookingSlotId) {
      return;
    }

    if (!bookingContactId) {
      setBookingError('Для записи войдите как контакт через Telegram или VK.');
      return;
    }

    setBookingSlotId(slot.id);
    setBookingError(null);
    setSuccess(null);

    try {
      const latestEvents = await crmEventsApi.list();
      const freshSlots = buildSlots(availabilityEvents, latestEvents, products, timezone, {
        excludeEventIds: selectedMeetingForReschedule
          ? new Set([selectedMeetingForReschedule.id])
          : undefined,
        requiredDurationMinutes: selectedMeetingForReschedule?.durationMinutes,
      });
      const picked = freshSlots.find((item) => item.id === slot.id);

      if (!picked) {
        setEvents(latestEvents);
        setBookingError(
          selectedMeetingForReschedule
            ? 'Этот слот уже занят. Выберите другое время для переноса.'
            : 'Этот слот уже занят. Выберите другой.'
        );
        return;
      }

      if (selectedMeetingForReschedule) {
        const latestMeetingEvent = latestEvents.find(
          (event) =>
            event.id === selectedMeetingForReschedule.id &&
            event.status === 'scheduled' &&
            event.contact_id === bookingContactId
        );
        const latestMeeting = latestMeetingEvent
          ? toPlannedMeeting(latestMeetingEvent, timezone)
          : null;
        if (!latestMeeting) {
          setEvents(latestEvents);
          setRescheduleMeetingId(null);
          setBookingError('Встреча для переноса больше недоступна.');
          return;
        }

        await crmEventsApi.update(selectedMeetingForReschedule.id, {
          start_time: picked.startAt,
          end_time: picked.endAt,
        });

        const eventsAfterUpdate = await crmEventsApi.list();
        setEvents(eventsAfterUpdate);
        setRescheduleMeetingId(null);
        setSuccess(
          `Встреча перенесена: было ${formatMeetingRange(latestMeeting.startAt, latestMeeting.endAt, timezone)}; стало ${formatMeetingRange(picked.startAt, picked.endAt, timezone)}.`
        );
      } else {
        await crmEventsApi.create({
          contact_id: bookingContactId,
          event_type_id: null,
          title: 'Запись через страницу клиента',
          description: '',
          start_time: picked.startAt,
          end_time: picked.endAt,
          location: '',
          status: 'scheduled',
          notes: '',
        });

        const eventsAfterCreate = await crmEventsApi.list();
        setEvents(eventsAfterCreate);
        setSuccess(`Готово! Вы записались на ${formatMeetingRange(picked.startAt, picked.endAt, timezone)}.`);
      }
    } catch (bookError) {
      if (bookError instanceof ApiError && bookError.status === 401) {
        setBookingError('Для записи войдите как контакт через Telegram или VK.');
        return;
      }
      setBookingError(
        selectedMeetingForReschedule
          ? 'Не удалось перенести встречу. Попробуйте другой слот.'
          : 'Не удалось записаться. Попробуйте другой слот.'
      );
    } finally {
      setBookingSlotId(null);
    }
  };

  const handleStartReschedule = (meetingId: number) => {
    setRescheduleMeetingId(meetingId);
    setSuccess(null);
    setBookingError(null);
  };

  const handleCancelReschedule = () => {
    setRescheduleMeetingId(null);
    setBookingError(null);
  };

  const handleCopyReferral = async () => {
    if (!referralLink) {
      setSuccess(null);
      setBookingError('Реферальная ссылка пока недоступна.');
      return;
    }

    try {
      await copyTextToClipboard(referralLink);
      setBookingError(null);
      setSuccess('Ссылка скопирована.');
      setTimeout(() => {
        setSuccess(null);
      }, 1500);
    } catch {
      setBookingError('Не удалось скопировать ссылку.');
    }
  };

  const handleApplyInviterCode = async () => {
    const normalizedCode = normalizeReferralCodeInput(inviterCodeInput);
    if (!normalizedCode) {
      setInviterCodeError('Введите код или ссылку приглашения.');
      setInviterCodeMessage(null);
      return;
    }

    setInviterCodeLoading(true);
    setInviterCodeError(null);
    setInviterCodeMessage(null);

    try {
      if (!bookingContactId) {
        setInviterCodeError('Для применения кода войдите как контакт через Telegram или VK.');
        setInviterCodeMessage(null);
        return;
      }
      const params = new URLSearchParams();
      params.set('contact_id', String(bookingContactId));
      const query = params.toString();
      const endpoint = `${BACKEND_BASE_URL}/core/api/referral/apply_code/${query ? `?${query}` : ''}`;

      const response = await apiFetch<ApplyReferralCodeResponse>(endpoint, {
        method: 'POST',
        body: { code: normalizedCode },
      });

      setInviterCodeMessage(response?.message || 'Код успешно применён.');
      setInviterCodeInput('');
    } catch (applyError) {
      if (applyError instanceof ApiError && applyError.status === 401) {
        setInviterCodeError('Для применения кода войдите как контакт через Telegram или VK.');
        return;
      }
      if (applyError instanceof ApiError) {
        try {
          const parsed = JSON.parse(applyError.body || '{}') as { error?: unknown };
          const maybeMessage = String(parsed.error || '').trim();
          setInviterCodeError(maybeMessage || 'Не удалось применить код.');
          return;
        } catch {
          // ignore parse error
        }
      }
      setInviterCodeError('Не удалось применить код.');
    } finally {
      setInviterCodeLoading(false);
    }
  };

  const handleBuySelectedProduct = async () => {
    if (!selectedTemplateProduct || buyingProductId !== null || !Number.isFinite(pageClientId) || pageClientId <= 0) {
      return;
    }
    if (!bookingContactId) {
      if (typeof window !== 'undefined') {
        const nextPath = `${window.location.pathname}${window.location.search}`;
        window.location.href = `/login?next=${encodeURIComponent(nextPath)}&tenant_id=${pageClientId}`;
      }
      return;
    }

    setBuyingProductId(selectedTemplateProduct.id);
    setPurchaseStatusError(null);
    setPurchaseStatusMessage(null);
    setPurchaseDeliveryLink(null);
    setPurchaseDeliveryTitle(null);
    setPurchaseSuccessModalOpen(false);
    setPurchaseSuccessModalMessage(null);

    try {
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const returnUrl = origin ? `${origin}/c/${pageClientId}` : `/c/${pageClientId}`;
      const response = await apiFetch<PublicBuyProductResponse>(`/public/client-page/${pageClientId}/buy/`, {
        method: 'POST',
        body: {
          product_id: selectedTemplateProduct.id,
          provider: selectedPaymentProvider,
          return_url: returnUrl,
        },
      });

      const paymentId = (response?.id || '').trim();
      const paymentUrl = (response?.payment_url || response?.confirmation_url || '').trim();
      if (!paymentId || !paymentUrl) {
        throw new Error('missing payment data');
      }

      if (typeof window !== 'undefined') {
        window.localStorage.setItem(
          getPendingProductPurchaseStorageKey(pageClientId),
          JSON.stringify({
            paymentId,
            productId: selectedTemplateProduct.id,
            createdAt: Date.now(),
          })
        );
        window.location.href = paymentUrl;
        return;
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && typeof window !== 'undefined') {
        const nextPath = `${window.location.pathname}${window.location.search}`;
        window.location.href = `/login?next=${encodeURIComponent(nextPath)}&tenant_id=${pageClientId}`;
        return;
      }
      setPurchaseStatusError('Не удалось создать оплату. Обратитесь к владельцу портала.');
    } finally {
      setBuyingProductId(null);
    }
  };

  const handlePrevWeek = () => {
    if (!canGoPrevWeek) {
      return;
    }
    setWeekCursor((prev) => addDays(prev, -7));
  };

  const handleNextWeek = () => {
    if (!canGoNextWeek) {
      return;
    }
    setWeekCursor((prev) => addDays(prev, 7));
  };

  const formatReferralTimestamp = (value?: string | null) => {
    if (!value) {
      return '—';
    }
    return formatInTenantTimezone(value, timezone, {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatPurchaseTimestamp = (value?: string | null) => {
    if (!value) {
      return 'Дата оплаты не указана';
    }
    return formatInTenantTimezone(value, timezone, {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const formatPurchaseAmount = (item: ContactPurchaseListItem) => {
    const rawAmount = typeof item.amount === 'string' ? Number(item.amount) : NaN;
    const currency = (item.currency || 'RUB').trim().toUpperCase() || 'RUB';
    if (!Number.isFinite(rawAmount) || rawAmount <= 0) {
      return '';
    }
    try {
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency,
        maximumFractionDigits: 2,
      }).format(rawAmount);
    } catch {
      return `${rawAmount} ${currency}`;
    }
  };

  const formatPurchasePackageAmount = (item: ContactPurchaseListItem) => {
    const rawAmount = item.package?.price;
    const amount =
      typeof rawAmount === 'number'
        ? rawAmount
        : typeof rawAmount === 'string'
          ? Number(rawAmount)
          : NaN;
    const currency = (item.currency || 'RUB').trim().toUpperCase() || 'RUB';
    if (!Number.isFinite(amount) || amount <= 0) {
      return '';
    }
    try {
      return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency,
        maximumFractionDigits: 2,
      }).format(amount);
    } catch {
      return `${amount} ${currency}`;
    }
  };

  const formatServicePackageRemaining = (item: ContactPurchaseListItem) => {
    const servicePackage = item.service_package;
    if (!servicePackage?.enabled) {
      return '';
    }
    const remainingLabel = (servicePackage.remaining_label || '').trim();
    if (!remainingLabel) {
      return '';
    }
    return `Осталось: ${remainingLabel}`;
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-2xl border p-6 text-sm text-muted-foreground">Загрузка...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-700">{error}</div>
      </div>
    );
  }

  const displayName = (settings?.brand_name || activeClientName || '').trim() || 'Клиент';
  const niche = (settings?.niche || '').trim() || 'Ниша не указана';
  const isRescheduleMode = selectedMeetingForReschedule !== null;
  const pageTemplateConfig = normalizeClientPageTemplateConfig(settings?.client_page_config);
  const selectedTemplateProduct = (() => {
    const selectedProductId = pageTemplateConfig.selected_product_id;
    if (selectedProductId) {
      return activeProducts.find((product) => product.id === selectedProductId) || null;
    }
    return activeProducts[0] || null;
  })();
  const selectedTemplateProductPrice = selectedTemplateProduct ? resolveProductPrice(selectedTemplateProduct) : null;
  const selectedTemplateProductPriceLabel = selectedTemplateProductPrice === null || !Number.isFinite(selectedTemplateProductPrice)
    ? 'Цена не указана'
    : rubFormatter.format(selectedTemplateProductPrice);
  const templateValues: Record<string, string> = {
    brand_name: displayName,
    niche,
    product_name: (selectedTemplateProduct?.name || '').trim(),
    product_price: selectedTemplateProductPriceLabel,
    product_service: (settings?.product_service || '').trim(),
  };
  const legacyCustomContent = normalizeTiptapJson(settings?.client_page_content);
  const heroConfig = pageTemplateConfig.hero;
  const heroTitle = replaceTemplateTokens(heroConfig.title, templateValues);
  const heroSubtitle = replaceTemplateTokens(heroConfig.subtitle, templateValues);
  const heroButtonText = replaceTemplateTokens(heroConfig.button_text, templateValues);
  const heroButtonUrl = replaceTemplateTokens(heroConfig.button_url, templateValues);
  const imageBlocks = (() => {
    const source = pageTemplateConfig.extra_blocks.images.length > 0
      ? pageTemplateConfig.extra_blocks.images
      : ((pageTemplateConfig.extra_blocks.image.url.trim() || pageTemplateConfig.blocks.image)
        ? [pageTemplateConfig.extra_blocks.image]
        : []);
    return source.map((item) => {
      const url = replaceTemplateTokens(item.url || '', templateValues).trim();
      return {
        ...item,
        url,
        alt: replaceTemplateTokens(item.alt || '', templateValues).trim(),
        caption: replaceTemplateTokens(item.caption || '', templateValues).trim(),
      };
    });
  })();
  const videoBlocks = (() => {
    const source = pageTemplateConfig.extra_blocks.videos.length > 0
      ? pageTemplateConfig.extra_blocks.videos
      : ((pageTemplateConfig.extra_blocks.video.url.trim() || pageTemplateConfig.blocks.video)
        ? [pageTemplateConfig.extra_blocks.video]
        : []);
    return source.map((item) => {
      const url = replaceTemplateTokens(item.url || '', templateValues).trim();
      return {
        ...item,
        url,
        caption: replaceTemplateTokens(item.caption || '', templateValues).trim(),
        source: resolveClientPageVideoSource(url),
      };
    });
  })();
  const textBlocksHtml = (() => {
    const source = pageTemplateConfig.extra_blocks.text_blocks.length > 0
      ? pageTemplateConfig.extra_blocks.text_blocks.map((item) => normalizeTiptapJson(item)).filter(Boolean)
      : (legacyCustomContent ? [legacyCustomContent] : []);
    return source.map((item) => {
      if (!item) {
        return '';
      }
      try {
        const replacedJson = replaceTemplateTokensInTiptapNode(item, templateValues) as Record<string, unknown>;
        return generateHTML(replacedJson, createKbExtensions());
      } catch {
        return '';
      }
    });
  })();
  const blockOrderMap = pageTemplateConfig.block_order.reduce<Record<string, number[]>>((acc, key, index) => {
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(index);
    return acc;
  }, {});
  const isBlockEnabled = (key: ClientPageBlockKey): boolean => {
    return Boolean(pageTemplateConfig.blocks[key]);
  };
  const getBlockOrder = (key: ClientPageBlockKey, occurrence = 0): number => {
    const explicitOrder = blockOrderMap[key]?.[occurrence];
    if (typeof explicitOrder === 'number') {
      return explicitOrder;
    }
    const fallbackOrder = CLIENT_PAGE_BLOCK_DEFAULT_ORDER.indexOf(key);
    return fallbackOrder >= 0
      ? pageTemplateConfig.block_order.length + fallbackOrder + occurrence
      : pageTemplateConfig.block_order.length + 100 + occurrence;
  };
  const imageRenderCount = isBlockEnabled('image')
    ? Math.max(imageBlocks.length, blockOrderMap.image?.length || 0, 1)
    : 0;
  const videoRenderCount = isBlockEnabled('video')
    ? Math.max(videoBlocks.length, blockOrderMap.video?.length || 0, 1)
    : 0;
  const textRenderCount = isBlockEnabled('custom_content')
    ? Math.max(textBlocksHtml.length, blockOrderMap.custom_content?.length || 0, 1)
    : 0;
  const canUseContactFeatures = bookingContactId !== null;
  const isClientPreviewMode = hasTenantSession && !canUseContactFeatures;
  const isPublicPreviewMode = !hasTenantSession && !canUseContactFeatures;

  return (
    <div className="mx-auto max-w-3xl p-6">
      {(isPublicPreviewMode || isClientPreviewMode) && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-sm text-amber-900 space-y-2">
          <div className="font-medium">
            {isClientPreviewMode
              ? 'Режим предпросмотра (вход как клиент)'
              : 'Публичный просмотр страницы'}
          </div>
          <div>
            Запись на слот и партнёрская программа доступны после входа как контакт через Telegram или VK.
          </div>
          <div>
            <button
              type="button"
              onClick={() => router.push(`/login?next=${encodeURIComponent(`/c/${pageClientId}`)}&tenant_id=${pageClientId}`)}
              className="rounded-md border border-amber-300 bg-white px-3 py-1.5 text-sm hover:bg-amber-100"
            >
              Войти
            </button>
          </div>
        </div>
      )}

      <div className={`${(isPublicPreviewMode || isClientPreviewMode) ? 'mt-6 ' : ''}flex flex-col gap-6`}>
        {isBlockEnabled('hero') && (
          <div style={{ order: getBlockOrder('hero') }}>
            <div className="overflow-hidden rounded-2xl border shadow-sm">
              <section
                className="relative px-8 py-14 sm:px-10"
                style={{ background: heroConfig.image_url ? undefined : heroConfig.background }}
              >
                {heroConfig.image_url && (
                  <div
                    className="absolute inset-0"
                    style={{
                      backgroundImage: `url(${heroConfig.image_url})`,
                      backgroundSize: 'cover',
                      backgroundPosition: 'center',
                    }}
                  />
                )}
                {heroConfig.image_url && (
                  <div
                    className="absolute inset-0"
                    style={{
                      background: heroConfig.background,
                      opacity: heroConfig.overlay_opacity / 100,
                    }}
                  />
                )}

                <div
                  className={`relative z-10 flex flex-col gap-4 ${
                    heroConfig.align === 'center'
                      ? 'items-center text-center'
                      : heroConfig.align === 'right'
                        ? 'items-end text-right'
                        : 'items-start text-left'
                  }`}
                >
                  <h1 className="whitespace-pre-line text-3xl font-semibold sm:text-4xl" style={{ color: heroConfig.text_color }}>
                    {heroTitle}
                  </h1>
                  {heroConfig.show_subtitle && (
                    <p className="max-w-2xl whitespace-pre-line text-base opacity-90 sm:text-lg" style={{ color: heroConfig.text_color }}>
                      {heroSubtitle}
                    </p>
                  )}
                  {heroConfig.show_button && (
                    <a
                      href={heroButtonUrl || '#'}
                      className="inline-flex rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-slate-900 hover:bg-slate-100"
                    >
                      {heroButtonText}
                    </a>
                  )}
                </div>
              </section>
            </div>
          </div>
        )}

        {Array.from({ length: imageRenderCount }).map((_, imageIndex) => {
          const imageBlock = imageBlocks[imageIndex] || null;
          const imageBlockUrl = imageBlock?.url?.trim() || '';
          return (
            <div key={`image-${imageIndex}`} style={{ order: getBlockOrder('image', imageIndex) }}>
              <div className="overflow-hidden rounded-2xl border p-4 shadow-sm">
                {!imageBlockUrl ? (
                  <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                    Изображение не настроено.
                  </div>
                ) : (
                  <figure className="space-y-3">
                    <Image
                      src={imageBlockUrl}
                      alt={imageBlock?.alt || 'Изображение'}
                      width={1600}
                      height={900}
                      unoptimized
                      loader={({ src }) => src}
                      className="w-full rounded-xl bg-slate-100"
                      style={{
                        maxHeight: imageBlock?.max_height || 420,
                        objectFit: imageBlock?.fit || 'cover',
                      }}
                    />
                    {imageBlock?.caption && (
                      <figcaption className="text-sm text-muted-foreground">{imageBlock.caption}</figcaption>
                    )}
                  </figure>
                )}
              </div>
            </div>
          );
        })}

        {Array.from({ length: videoRenderCount }).map((_, videoIndex) => {
          const videoBlock = videoBlocks[videoIndex] || null;
          const videoBlockUrl = videoBlock?.url?.trim() || '';
          return (
            <div key={`video-${videoIndex}`} style={{ order: getBlockOrder('video', videoIndex) }}>
              <div className="rounded-2xl border p-4 shadow-sm">
                {!videoBlockUrl ? (
                  <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                    Видео не настроено.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {videoBlock?.source.type === 'youtube' || videoBlock?.source.type === 'vimeo' ? (
                      <div className="aspect-video overflow-hidden rounded-xl border">
                        <iframe
                          src={videoBlock.source.embed_url}
                          title="Видео"
                          className="h-full w-full"
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                          allowFullScreen
                        />
                      </div>
                    ) : videoBlock?.source.type === 'direct' ? (
                      <video src={videoBlock.source.embed_url} controls className="aspect-video w-full rounded-xl border bg-black" />
                    ) : (
                      <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                        Неподдерживаемый формат видео. Используйте YouTube, Vimeo или прямую ссылку `.mp4/.webm/.ogg`.
                      </div>
                    )}

                    {videoBlock?.caption && (
                      <div className="text-sm text-muted-foreground">{videoBlock.caption}</div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isBlockEnabled('header') && (
          <div style={{ order: getBlockOrder('header') }}>
            <div className="rounded-2xl border p-6 shadow-sm space-y-2">
              <div className="text-2xl font-semibold">{displayName}</div>
              <div className="text-muted-foreground">{niche}</div>
              <div className="text-xs text-muted-foreground">ID клиента: #{activeClientId ?? pageClientId}</div>
              <div className="text-xs text-muted-foreground">
                Контакт Telegram/VK: {bookingContactId ? (bookingContactName || `#${bookingContactId}`) : 'не авторизован'}
              </div>
            </div>
          </div>
        )}

        {isBlockEnabled('product') && (
          <div style={{ order: getBlockOrder('product') }}>
            <div className="rounded-2xl border p-6 shadow-sm space-y-3">
          <div className="text-sm text-muted-foreground">Продукт</div>
          {!selectedTemplateProduct ? (
            <div className="text-muted-foreground">Активный продукт не выбран.</div>
          ) : (
            <div className="rounded-lg border px-4 py-3">
              <div className="flex items-baseline justify-between gap-3">
                <div className="text-lg font-medium">
                  {(selectedTemplateProduct.name || '').trim() || 'Продукт без названия'}
                </div>
                <div className="text-lg font-semibold whitespace-nowrap">
                  {selectedTemplateProductPriceLabel}
                </div>
              </div>
              {selectedTemplateProduct.short_description?.trim() && (
                <div className="mt-2 text-sm text-muted-foreground">
                  {selectedTemplateProduct.short_description.trim()}
                </div>
              )}

              <div className="mt-3 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">Оплата через:</span>
                  {(['yookassa', 'tbank'] as PaymentProvider[]).map((provider) => (
                    <button
                      key={provider}
                      type="button"
                      onClick={() => setSelectedPaymentProvider(provider)}
                      disabled={buyingProductId !== null}
                      className={`rounded-lg border px-3 py-1 text-xs font-medium transition disabled:opacity-60 ${
                        selectedPaymentProvider === provider
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border hover:bg-accent'
                      }`}
                    >
                      {PAYMENT_PROVIDER_LABELS[provider]}
                    </button>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void handleBuySelectedProduct()}
                    disabled={
                      buyingProductId !== null
                      || !canUseContactFeatures
                      || selectedTemplateProductPrice === null
                      || !Number.isFinite(selectedTemplateProductPrice)
                    }
                    className="rounded-xl border px-4 py-2 text-sm font-medium hover:bg-accent disabled:opacity-60"
                  >
                    {buyingProductId === selectedTemplateProduct.id
                      ? 'Переход к оплате…'
                      : `Купить через ${PAYMENT_PROVIDER_LABELS[selectedPaymentProvider]}`}
                  </button>
                  {(selectedTemplateProductPrice === null || !Number.isFinite(selectedTemplateProductPrice)) && (
                    <span className="text-xs text-muted-foreground">Цена не указана</span>
                  )}
                  {!canUseContactFeatures && (
                    <span className="text-xs text-muted-foreground">
                      Покупка доступна только после входа как контакт через Telegram или VK
                    </span>
                  )}
                </div>
              </div>
            </div>
          )}

          {(purchaseStatusLoading || purchaseStatusMessage || purchaseStatusError || purchaseDeliveryLink) && (
            <div className="rounded-xl border p-3 space-y-2">
              {purchaseStatusLoading && (
                <div className="text-sm text-muted-foreground">Проверяем оплату…</div>
              )}
              {purchaseStatusError && (
                <div className="text-sm text-red-600">{purchaseStatusError}</div>
              )}
              {purchaseStatusMessage && (
                <div className="text-sm text-green-700">{purchaseStatusMessage}</div>
              )}
              {purchaseDeliveryLink && (
                <a
                  href={purchaseDeliveryLink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent"
                >
                  {purchaseDeliveryTitle || 'Открыть цифровой продукт'}
                </a>
              )}
            </div>
          )}
            </div>
          </div>
        )}

        {isBlockEnabled('events') && (
          <div style={{ order: getBlockOrder('events') }}>
            <EventsContent
              clientId={pageClientId}
              displayName={displayName}
              eventProducts={eventProducts}
              titleAs="h2"
              showBackLink={false}
            />
          </div>
        )}

        {isBlockEnabled('purchases') && (
          <div style={{ order: getBlockOrder('purchases') }}>
            <div className="rounded-2xl border p-6 shadow-sm space-y-3">
          <div className="text-xl font-semibold">Список покупок</div>

          {!canUseContactFeatures && (
            <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-sm text-slate-700">
              Список покупок доступен после входа как контакт через Telegram или VK.
            </div>
          )}

          {canUseContactFeatures && purchasesLoading && (
            <div className="text-sm text-muted-foreground">Загружаем покупки...</div>
          )}

          {canUseContactFeatures && !purchasesLoading && purchases.length === 0 && !purchasesError && (
            <div className="text-sm text-muted-foreground">Пока покупок нет.</div>
          )}

          {canUseContactFeatures && purchases.length > 0 && (
            <ul className="space-y-2">
              {purchases.map((item) => {
                const itemKey = String(item.id ?? `${item.product_id ?? 'product'}:${item.payment_id ?? ''}`);
                const title = (item.product_name || '').trim() || `Продукт #${item.product_id ?? '—'}`;
                const amountLabel = formatPurchaseAmount(item);
                const packageName = (item.package?.name || '').trim();
                const packageDescription = (item.package?.description || '').trim();
                const packageAmountLabel = formatPurchasePackageAmount(item);
                const serviceRemainingLabel = formatServicePackageRemaining(item);
                const delivery = item.delivery || null;
                const deliveryReady = Boolean(delivery?.ready && delivery?.url);
                const isServicePackage = Boolean(item.service_package?.enabled);

                return (
                  <li
                    key={itemKey}
                    className="rounded-xl border p-3 space-y-2"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-sm font-medium text-foreground">{title}</div>
                        <div className="text-xs text-muted-foreground">
                          {formatPurchaseTimestamp(item.paid_at)}
                          {amountLabel ? ` · ${amountLabel}` : ''}
                        </div>
                        {packageName && (
                          <div className="text-xs text-muted-foreground">
                            Пакет: {packageName}
                            {packageAmountLabel ? ` · ${packageAmountLabel}` : ''}
                          </div>
                        )}
                        {packageDescription && (
                          <div className="text-xs text-muted-foreground">{packageDescription}</div>
                        )}
                        {serviceRemainingLabel && (
                          <div className="text-xs text-emerald-700">
                            {serviceRemainingLabel}
                          </div>
                        )}
                      </div>
                      {deliveryReady && (
                        <a
                          href={delivery?.url || '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="shrink-0 rounded-lg border px-3 py-1.5 text-sm hover:bg-accent"
                        >
                          {(delivery?.document_title || '').trim() || 'Открыть продукт'}
                        </a>
                      )}
                    </div>

                    {!deliveryReady && !isServicePackage && (
                      <div className="text-sm text-muted-foreground">
                        {(delivery?.message || '').trim() || 'Покажите информацию об оплате владельцу портала'}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}

              {purchasesError && <div className="text-sm text-red-600">{purchasesError}</div>}
            </div>
          </div>
        )}

        {Array.from({ length: textRenderCount }).map((_, textIndex) => {
          const html = textBlocksHtml[textIndex] || '';
          return (
            <div key={`custom-content-${textIndex}`} style={{ order: getBlockOrder('custom_content', textIndex) }}>
              <div className="rounded-2xl border p-6 shadow-sm">
                {html ? (
                  <div
                    className="tiptap prose prose-slate max-w-none"
                    dangerouslySetInnerHTML={{ __html: html }}
                  />
                ) : (
                  <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">
                    Текстовый блок пустой.
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {isBlockEnabled('booking') && (
      <div id="booking" style={{ order: getBlockOrder('booking') }}>
      <div className="rounded-2xl border p-6 shadow-sm space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-xl font-semibold">
            {isRescheduleMode ? 'Перенос встречи' : 'Запланировать встречу'}
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrevWeek}
              disabled={!canGoPrevWeek}
              className="rounded-md border px-2 py-1 text-sm hover:bg-accent disabled:opacity-50"
            >
              &larr;
            </button>
            <div className="min-w-[150px] text-center text-sm font-medium">{weekRangeLabel}</div>
            <button
              type="button"
              onClick={handleNextWeek}
              disabled={!canGoNextWeek}
              className="rounded-md border px-2 py-1 text-sm hover:bg-accent disabled:opacity-50"
            >
              &rarr;
            </button>
          </div>
        </div>

        {!canUseContactFeatures && (
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-sm text-slate-700">
            Чтобы записаться на слот, войдите как контакт через Telegram или VK. До входа доступен только просмотр расписания.
          </div>
        )}

        {isRescheduleMode && selectedMeetingForReschedule && (
          <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-3 text-sm text-slate-700">
            <div className="font-medium">
              Переносим: {selectedMeetingForReschedule.title}
            </div>
            <div className="mt-1">
              Было: {formatMeetingRange(selectedMeetingForReschedule.startAt, selectedMeetingForReschedule.endAt, timezone)}
            </div>
            <div className="mt-2">
              <button
                type="button"
                onClick={handleCancelReschedule}
                disabled={bookingSlotId !== null}
                className="rounded-md border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
              >
                Отменить перенос
              </button>
            </div>
          </div>
        )}

        {slots.length === 0 ? (
          <div className="text-muted-foreground">
            {isRescheduleMode ? 'Нет доступных слотов для переноса этой встречи.' : 'Свободных слотов пока нет.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="min-w-[980px] grid grid-cols-7 gap-3">
              {weekDates.map((day) => {
                const dayKey = formatKey(day);
                const daySlots = slotsByDate.get(dayKey) || [];
                const hasAvailableSlots = daySlots.length > 0;
                const isToday = dayKey === todayKey;

                return (
                  <div
                    key={dayKey}
                    className={`rounded-xl border p-3 space-y-2 ${hasAvailableSlots ? 'border-emerald-300 bg-emerald-50/70' : ''} ${isToday ? 'ring-1 ring-blue-300' : ''}`}
                  >
                    <div className="space-y-0.5">
                      <div className="text-xs uppercase tracking-wide text-muted-foreground">
                        {formatTenantLocalDate(day, timezone, { weekday: 'short' })}
                      </div>
                      <div className="text-sm font-semibold">
                        {formatTenantLocalDate(day, timezone, { day: '2-digit', month: 'short' })}
                      </div>
                    </div>

                    {daySlots.length === 0 ? (
                      <div className="text-xs text-muted-foreground">Нет слотов</div>
                    ) : (
                      <div className="space-y-2">
                        {daySlots.map((slot) => (
                          <button
                            key={slot.id}
                            onClick={() => void handleBook(slot)}
                            disabled={!bookingContactId || bookingSlotId !== null}
                            className="w-full rounded-lg border px-3 py-2 text-left text-sm hover:bg-accent disabled:opacity-60"
                          >
                            <div className="font-medium">
                              {formatInTenantTimezone(slot.startAt, timezone, {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {formatInTenantTimezone(slot.endAt, timezone, {
                                hour: '2-digit',
                                minute: '2-digit',
                              })}
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {bookingError && <div className="text-sm text-red-600">{bookingError}</div>}
        {success && <div className="text-sm text-green-700">{success}</div>}
      </div>
      </div>
      )}

        {isBlockEnabled('planned_meetings') && plannedMeetings.length > 0 && (
          <div style={{ order: getBlockOrder('planned_meetings') }}>
            <div className="rounded-2xl border p-6 shadow-sm space-y-3">
          <div className="text-xl font-semibold">Запланированы встречи:</div>
          <ul className="space-y-2">
            {plannedMeetings.map((meeting) => (
              <li
                key={meeting.id}
                className="flex items-center justify-between gap-3 rounded-lg border px-3 py-2 text-sm text-slate-700"
              >
                <span>{formatMeetingRange(meeting.startAt, meeting.endAt, timezone)}</span>
                {isBlockEnabled('booking') && (
                  <button
                    type="button"
                    onClick={() => handleStartReschedule(meeting.id)}
                    disabled={bookingSlotId !== null}
                    className="rounded-md border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
                  >
                    {meeting.id === rescheduleMeetingId ? 'Выбрана' : 'Перенести'}
                  </button>
                )}
              </li>
            ))}
          </ul>
            </div>
          </div>
        )}

        {isBlockEnabled('referrals') && (
      <div style={{ order: getBlockOrder('referrals') }}>
      <div className="rounded-2xl border p-6 shadow-sm space-y-2">
        <div className="text-xl font-semibold">Рефералы</div>
        <div className="text-muted-foreground">Приглашено: <b>{referralCount}</b></div>
        <div className="text-sm text-muted-foreground">Введите полученный код от пригласившего</div>

        {!canUseContactFeatures && (
          <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-sm text-slate-700">
            Партнёрская программа доступна после входа как контакт через Telegram или VK.
          </div>
        )}

        <div className="flex gap-2">
          <input
            className="flex-1 rounded-xl border px-3 py-2 text-sm"
            value={inviterCodeInput}
            onChange={(event) => setInviterCodeInput(event.target.value)}
            placeholder="ref_... или ссылка"
            disabled={!canUseContactFeatures}
          />
          <button
            onClick={() => void handleApplyInviterCode()}
            disabled={!canUseContactFeatures || inviterCodeLoading}
            className="rounded-xl border px-4 py-2 text-sm hover:bg-accent disabled:opacity-60"
          >
            Применить
          </button>
        </div>

        {inviterCodeError && <div className="text-sm text-red-600">{inviterCodeError}</div>}
        {inviterCodeMessage && <div className="text-sm text-green-700">{inviterCodeMessage}</div>}

        <div className="text-sm font-medium">Ваш код для приглашения других:</div>
        <div className="text-xs text-muted-foreground">Оба человека получают бонус!</div>

        <div className="flex gap-2">
          <input
            className="flex-1 rounded-xl border px-3 py-2 text-sm"
            readOnly
            value={referralLink}
          />
          <button
            onClick={() => void handleCopyReferral()}
            disabled={!canUseContactFeatures || referralLoading || !referralLink}
            className="rounded-xl border px-4 py-2 text-sm hover:bg-accent disabled:opacity-60"
          >
            Копировать
          </button>
        </div>

        <div className="rounded-xl border border-slate-200 bg-slate-50/40 p-3">
          <div className="text-sm font-medium">Приглашения:</div>
          {referralInvitations.length === 0 ? (
            <div className="mt-2 text-sm text-muted-foreground">Пока приглашений нет.</div>
          ) : (
            <ul className="mt-2 space-y-2">
              {referralInvitations.slice(0, 20).map((item) => {
                const statusLabel = REFERRAL_STATUS_LABELS[item.status || ''] || 'Неизвестно';
                const inviterName = (item.invited_telegram_username || '').trim();
                const codeTypeLabel = item.code_type === 'contact' ? 'contact' : 'client';
                const timestamp = formatReferralTimestamp(item.rewarded_at || item.registered_at || item.created_at);

                return (
                  <li
                    key={item.id}
                    className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white/70 px-3 py-2 text-sm"
                  >
                    <span className="text-slate-700">
                      {inviterName ? `@${inviterName}` : `#${item.id}`} · {statusLabel}
                    </span>
                    <span className="text-xs text-slate-500">
                      {codeTypeLabel} · {timestamp}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {referralError && <div className="text-sm text-red-600">{referralError}</div>}
      </div>
      </div>
      )}
    </div>
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
              {purchaseDeliveryTitle || 'Открыть цифровой продукт'}
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
