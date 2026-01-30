import { NextResponse } from 'next/server';

const formatIcsDate = (date: Date) =>
  date.toISOString().replace(/[-:]/g, '').split('.')[0] + 'Z';

const escapeIcsValue = (value: string) =>
  value
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,');

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const title = searchParams.get('title') || 'Встреча';
  const description = searchParams.get('description') || '';
  const location = searchParams.get('location') || '';
  const startParam = searchParams.get('start');
  const endParam = searchParams.get('end');
  const uidParam = searchParams.get('uid');

  if (!startParam) {
    return new NextResponse('Missing start time', { status: 400 });
  }

  const startDate = new Date(startParam);
  if (Number.isNaN(startDate.getTime())) {
    return new NextResponse('Invalid start time', { status: 400 });
  }

  let endDate = endParam ? new Date(endParam) : null;
  if (!endDate || Number.isNaN(endDate.getTime())) {
    endDate = new Date(startDate.getTime() + 60 * 60 * 1000);
  }

  const uid =
    uidParam && uidParam.trim()
      ? `${uidParam.trim()}@zavod`
      : `${Date.now()}-${Math.random().toString(16).slice(2)}@zavod`;

  const icsLines = [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Zavod//Calendar//EN',
    'CALSCALE:GREGORIAN',
    'BEGIN:VEVENT',
    `UID:${uid}`,
    `DTSTAMP:${formatIcsDate(new Date())}`,
    `DTSTART:${formatIcsDate(startDate)}`,
    `DTEND:${formatIcsDate(endDate)}`,
    `SUMMARY:${escapeIcsValue(title)}`,
    `DESCRIPTION:${escapeIcsValue(description)}`,
  ];

  if (location) {
    icsLines.push(`LOCATION:${escapeIcsValue(location)}`);
  }

  icsLines.push('END:VEVENT', 'END:VCALENDAR');

  const ics = icsLines.join('\r\n');

  return new NextResponse(ics, {
    headers: {
      'Content-Type': 'text/calendar; charset=utf-8',
      'Content-Disposition': 'attachment; filename="event.ics"',
      'Cache-Control': 'no-store',
    },
  });
}
