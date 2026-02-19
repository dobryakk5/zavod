'use client';

import { useEffect, useMemo, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  ApiError,
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
import {
  DEFAULT_TENANT_TIMEZONE,
  formatInTenantTimezone,
  normalizeTenantTimezone,
  tenantDateToUtcISOString,
  toTenantDate,
} from '@/lib/timezone';

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

const buildSlots = (
  availabilityEvents: AvailabilityEvent[],
  events: Event[],
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

      const isBusy = busyIntervals.some((busy) =>
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

  const pageClientId = Number(rawClientId);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [bookingError, setBookingError] = useState<string | null>(null);
  const [bookingSlotId, setBookingSlotId] = useState<string | null>(null);
  const [rescheduleMeetingId, setRescheduleMeetingId] = useState<number | null>(null);

  const [activeClientId, setActiveClientId] = useState<number | null>(null);
  const [activeClientName, setActiveClientName] = useState('');
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
      buildSlots(availabilityEvents, events, timezone, {
        excludeEventIds: selectedMeetingForReschedule
          ? new Set([selectedMeetingForReschedule.id])
          : undefined,
        requiredDurationMinutes: selectedMeetingForReschedule?.durationMinutes,
      }),
    [availabilityEvents, events, selectedMeetingForReschedule, timezone]
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

      try {
        const [info, settingsData, productsData, availabilityData, eventsData, contactsData, authData] = await Promise.all([
          clientApi.info(),
          clientApi.getSettings(),
          clientProductsApi.list(),
          crmAvailabilityEventsApi.list(),
          crmEventsApi.list(),
          crmContactsApi.list(),
          apiFetch<TelegramAuthResponse>('/auth/telegram'),
        ]);

        const activeId = Number(info?.client?.id || 0);
        const activeName = (info?.client?.name || '').trim();
        const brandName = (settingsData?.brand_name || '').trim();

        setActiveClientId(Number.isFinite(activeId) && activeId > 0 ? activeId : null);
        setActiveClientName(activeName);
        setSettings(settingsData);
        setProducts(productsData);
        setAvailabilityEvents(availabilityData);
        setEvents(eventsData);
        setTimezone(normalizeTenantTimezone(settingsData?.timezone));

        const bindingContactId = (() => {
          const raw = authData?.user?.contactId;
          return typeof raw === 'number' && Number.isFinite(raw) && raw > 0 ? raw : null;
        })();
        const bookingContact = bindingContactId
          ? contactsData.find((contact) => contact.id === bindingContactId) || null
          : resolveBookingContact(contactsData, activeName, brandName);
        setBookingContactId(bookingContact?.id ?? null);
        setBookingContactName((bookingContact?.name || '').trim());

        if (!Number.isFinite(activeId) || activeId <= 0) {
          setError('Не удалось определить текущего клиента.');
          return;
        }

        if (activeId !== pageClientId) {
          setError(`Страница /c/${pageClientId} недоступна для этого аккаунта. Ваша страница: /c/${activeId}.`);
          return;
        }
      } catch (loadError) {
        if (loadError instanceof ApiError && loadError.status === 401) {
          router.push('/login');
          return;
        }
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

      setReferralLoading(true);
      setReferralError(null);
      try {
        const referralParams = new URLSearchParams({ type: 'contact' });
        if (bookingContactId) {
          referralParams.set('contact_id', String(bookingContactId));
        }
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
          router.push('/login');
          return;
        }
        setReferralInvitations([]);
        setReferralError('Не удалось загрузить партнёрскую программу.');
      } finally {
        setReferralLoading(false);
      }
    };

    void loadReferral();
  }, [router, loading, bookingContactId]);

  const handleBook = async (slot: Slot) => {
    if (!Number.isFinite(pageClientId) || pageClientId <= 0 || bookingSlotId) {
      return;
    }

    if (!bookingContactId) {
      setBookingError('Не найден контакт для записи. Добавьте контакт в CRM.');
      return;
    }

    setBookingSlotId(slot.id);
    setBookingError(null);
    setSuccess(null);

    try {
      const latestEvents = await crmEventsApi.list();
      const freshSlots = buildSlots(availabilityEvents, latestEvents, timezone, {
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
        router.push('/login');
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
      const params = new URLSearchParams();
      if (bookingContactId) {
        params.set('contact_id', String(bookingContactId));
      }
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
        router.push('/login');
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

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div className="rounded-2xl border p-6 shadow-sm space-y-2">
        <div className="text-2xl font-semibold">{displayName}</div>
        <div className="text-muted-foreground">{niche}</div>
        <div className="text-xs text-muted-foreground">ID клиента: #{activeClientId ?? pageClientId}</div>
        <div className="text-xs text-muted-foreground">
          Контакт для записи: {bookingContactId ? (bookingContactName || `#${bookingContactId}`) : 'не найден'}
        </div>
      </div>

      <div className="rounded-2xl border p-6 shadow-sm space-y-3">
        <div className="text-sm text-muted-foreground">Активные продукты</div>
        {activeProducts.length === 0 ? (
          <div className="text-muted-foreground">Активных продуктов пока нет.</div>
        ) : (
          <ul className="space-y-2">
            {activeProducts.map((product) => {
              const price = resolveProductPrice(product);
              const priceLabel = price === null || !Number.isFinite(price)
                ? 'Цена не указана'
                : rubFormatter.format(price);
              return (
                <li
                  key={product.id}
                  className="flex items-baseline justify-between gap-4 rounded-lg border px-3 py-2"
                >
                  <span className="font-medium">{(product.name || '').trim() || 'Продукт без названия'}</span>
                  <span className="font-semibold whitespace-nowrap">{priceLabel}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

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
        {plannedMeetings.length > 0 && (
          <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-3">
            <div className="text-sm font-medium">Запланированы встречи:</div>
            <ul className="mt-2 space-y-2">
              {plannedMeetings.map((meeting) => (
                <li key={meeting.id} className="flex items-center justify-between gap-3 rounded-lg border border-emerald-100 bg-white/70 px-3 py-2 text-sm text-slate-700">
                  <span>{formatMeetingRange(meeting.startAt, meeting.endAt, timezone)}</span>
                  <button
                    type="button"
                    onClick={() => handleStartReschedule(meeting.id)}
                    disabled={bookingSlotId !== null}
                    className="rounded-md border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
                  >
                    {meeting.id === rescheduleMeetingId ? 'Выбрана' : 'Перенести'}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="rounded-2xl border p-6 shadow-sm space-y-2">
        <div className="text-xl font-semibold">Рефералы</div>
        <div className="text-muted-foreground">Приглашено: <b>{referralCount}</b></div>
        <div className="text-sm text-muted-foreground">Введите полученный код от пригласившего</div>

        <div className="flex gap-2">
          <input
            className="flex-1 rounded-xl border px-3 py-2 text-sm"
            value={inviterCodeInput}
            onChange={(event) => setInviterCodeInput(event.target.value)}
            placeholder="ref_... или ссылка"
          />
          <button
            onClick={() => void handleApplyInviterCode()}
            disabled={inviterCodeLoading}
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
            disabled={referralLoading || !referralLink}
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
  );
}
