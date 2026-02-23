export type TimeZoneOption = {
  value: string;
  label: string;
};

const TIMEZONE_CHOICES = [
  'Africa/Abidjan',
  'Africa/Lagos',
  'Africa/Johannesburg',
  'Europe/Moscow',
  'Asia/Dubai',
  'Asia/Karachi',
  'Asia/Dhaka',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Tokyo',
];

const toPartsMap = (date: Date, timeZone: string) => {
  const formatter = new Intl.DateTimeFormat('en-US', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
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
  const parts = toPartsMap(date, timeZone);
  const asUTC = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second)
  );
  return (asUTC - date.getTime()) / 60000;
};

const formatOffsetLabel = (offsetMinutes: number) => {
  if (!Number.isFinite(offsetMinutes)) {
    return 'UTC+0';
  }
  const rounded = Math.round(offsetMinutes);
  const sign = rounded < 0 ? '-' : '+';
  const absMinutes = Math.abs(rounded);
  const hours = Math.floor(absMinutes / 60);
  const minutes = absMinutes % 60;
  if (!minutes) {
    return `UTC${sign}${hours}`;
  }
  return `UTC${sign}${hours}:${String(minutes).padStart(2, '0')}`;
};

export const getTimeZonesForSelect = (date: Date = new Date()): TimeZoneOption[] => {
  return TIMEZONE_CHOICES.map((timeZone) => {
    try {
      const offsetMinutes = getTimeZoneOffsetMinutes(date, timeZone);
      const offsetLabel = formatOffsetLabel(offsetMinutes);
      return {
        value: timeZone,
        label: `${offsetLabel} → ${timeZone}`,
      };
    } catch {
      // Some runtimes may not support all IANA zones; keep the option without offset.
      return {
        value: timeZone,
        label: timeZone,
      };
    }
  });
};
