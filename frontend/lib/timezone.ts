export const DEFAULT_TENANT_TIMEZONE = 'Europe/Moscow';

export const normalizeTenantTimezone = (value?: string | null) => {
  const candidate = (value ?? '').trim() || DEFAULT_TENANT_TIMEZONE;
  try {
    new Intl.DateTimeFormat('en-US', { timeZone: candidate });
    return candidate;
  } catch {
    return DEFAULT_TENANT_TIMEZONE;
  }
};

const DATE_TIME_PARTS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
};

const DATE_TIME_INPUT_PARTS: Intl.DateTimeFormatOptions = {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
};

type DateParts = {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
};

const toPartsMap = (date: Date, timeZone: string, options: Intl.DateTimeFormatOptions) => {
  const formatter = new Intl.DateTimeFormat('en-US', { timeZone, ...options });
  const parts = formatter.formatToParts(date);
  const map: Record<string, string> = {};
  parts.forEach(({ type, value }) => {
    if (type !== 'literal') {
      map[type] = value;
    }
  });
  return map;
};

const getTimeZoneOffsetMinutes = (date: Date, timeZone: string) => {
  const parts = toPartsMap(date, timeZone, DATE_TIME_PARTS);
  const asUTC = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second)
  );
  return Math.round((asUTC - date.getTime()) / 60000);
};

const parseLocalDateTime = (value: string): DateParts | null => {
  const normalized = (value || '').trim();
  if (!normalized) return null;
  const [datePart, timePart] = normalized.split(/[T ]/);
  if (!datePart || !timePart) return null;
  const [year, month, day] = datePart.split('-').map((v) => Number(v));
  const [hour, minute, second] = timePart.split(':').map((v) => Number(v));
  if (!year || !month || !day || Number.isNaN(hour) || Number.isNaN(minute)) return null;
  return {
    year,
    month,
    day,
    hour,
    minute,
    second: Number.isFinite(second) ? second : 0,
  };
};

const localPartsToUtcDate = (parts: DateParts, timeZone: string) => {
  const utcGuess = new Date(Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second));
  const offset = getTimeZoneOffsetMinutes(utcGuess, timeZone);
  return new Date(utcGuess.getTime() - offset * 60000);
};

export const toTenantDate = (utcTime: string | Date, timeZone: string) => {
  const tz = normalizeTenantTimezone(timeZone);
  const baseDate = typeof utcTime === 'string' ? new Date(utcTime) : utcTime;
  if (Number.isNaN(baseDate.getTime())) return new Date(NaN);
  return new Date(baseDate.toLocaleString('en-US', { timeZone: tz }));
};

export const formatInTenantTimezone = (
  utcTime: string | Date,
  timeZone: string,
  options: Intl.DateTimeFormatOptions
) => {
  const tz = normalizeTenantTimezone(timeZone);
  const date = typeof utcTime === 'string' ? new Date(utcTime) : utcTime;
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('ru-RU', { ...options, timeZone: tz });
};

export const formatTimeRangeInTenantTimezone = (start: string, end: string, timeZone: string) => {
  const startDate = new Date(start);
  if (Number.isNaN(startDate.getTime())) return '';
  const startTime = formatInTenantTimezone(startDate, timeZone, { hour: '2-digit', minute: '2-digit' });
  const endDate = new Date(end);
  if (Number.isNaN(endDate.getTime())) return startTime;
  const endTime = formatInTenantTimezone(endDate, timeZone, { hour: '2-digit', minute: '2-digit' });
  return startTime === endTime ? startTime : `${startTime}–${endTime}`;
};

export const formatTenantDateTimeInput = (utcTime: string | Date, timeZone: string) => {
  const tz = normalizeTenantTimezone(timeZone);
  const date = typeof utcTime === 'string' ? new Date(utcTime) : utcTime;
  if (Number.isNaN(date.getTime())) return '';
  const parts = toPartsMap(date, tz, DATE_TIME_INPUT_PARTS);
  if (!parts.year || !parts.month || !parts.day || !parts.hour || !parts.minute) return '';
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
};

export const localDateTimeStringToUtcISOString = (value: string, timeZone: string) => {
  const tz = normalizeTenantTimezone(timeZone);
  const parts = parseLocalDateTime(value);
  if (!parts) return '';
  return localPartsToUtcDate(parts, tz).toISOString();
};

export const tenantDateToUtcISOString = (value: Date, timeZone: string) => {
  if (Number.isNaN(value.getTime())) return '';
  const tz = normalizeTenantTimezone(timeZone);
  const parts: DateParts = {
    year: value.getFullYear(),
    month: value.getMonth() + 1,
    day: value.getDate(),
    hour: value.getHours(),
    minute: value.getMinutes(),
    second: value.getSeconds(),
  };
  return localPartsToUtcDate(parts, tz).toISOString();
};

export const formatTenantOffsetLabel = (timeZone: string, date: Date = new Date()) => {
  const tz = normalizeTenantTimezone(timeZone);
  if (Number.isNaN(date.getTime())) return 'UTC+00';
  const offsetMinutes = getTimeZoneOffsetMinutes(date, tz);
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const absMinutes = Math.abs(offsetMinutes);
  const hours = Math.floor(absMinutes / 60);
  const minutes = absMinutes % 60;
  const hourLabel = String(hours).padStart(2, '0');
  if (!minutes) {
    return `UTC${sign}${hourLabel}`;
  }
  return `UTC${sign}${hourLabel}:${String(minutes).padStart(2, '0')}`;
};
