import { describe, expect, it } from 'vitest';
import {
  DEFAULT_TENANT_TIMEZONE,
  formatTenantDateTimeInput,
  formatTenantOffsetLabel,
  localDateTimeStringToUtcISOString,
  normalizeTenantTimezone,
  tenantDateToUtcISOString,
} from '@/lib/timezone';

describe('timezone helpers', () => {
  it('normalizes invalid or empty timezones to default', () => {
    expect(normalizeTenantTimezone('')).toBe(DEFAULT_TENANT_TIMEZONE);
    expect(normalizeTenantTimezone('Invalid/Timezone')).toBe(DEFAULT_TENANT_TIMEZONE);
    expect(normalizeTenantTimezone('Europe/Moscow')).toBe('Europe/Moscow');
  });

  it('converts local tenant datetime string to UTC ISO string', () => {
    expect(localDateTimeStringToUtcISOString('2024-01-01T12:30', 'Europe/Moscow')).toBe(
      '2024-01-01T09:30:00.000Z'
    );
  });

  it('returns empty string for invalid local datetime input', () => {
    expect(localDateTimeStringToUtcISOString('', 'Europe/Moscow')).toBe('');
    expect(localDateTimeStringToUtcISOString('bad-value', 'Europe/Moscow')).toBe('');
  });

  it('formats UTC date for tenant datetime input control', () => {
    expect(formatTenantDateTimeInput('2024-01-01T09:30:00.000Z', 'Europe/Moscow')).toBe('2024-01-01T12:30');
  });

  it('converts local Date components to UTC ISO string using tenant timezone', () => {
    const localLikeDate = new Date(2024, 0, 1, 12, 30, 0);
    expect(tenantDateToUtcISOString(localLikeDate, 'Europe/Moscow')).toBe('2024-01-01T09:30:00.000Z');
  });

  it('formats timezone offset labels including half-hour offsets', () => {
    const fixedDate = new Date('2024-01-01T00:00:00.000Z');
    expect(formatTenantOffsetLabel('Europe/Moscow', fixedDate)).toBe('UTC+03');
    expect(formatTenantOffsetLabel('Asia/Kolkata', fixedDate)).toBe('UTC+05:30');
  });
});
