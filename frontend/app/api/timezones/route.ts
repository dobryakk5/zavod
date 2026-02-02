import { NextResponse } from 'next/server';
import { getTimeZonesForSelect } from '@/lib/timezones';

export const dynamic = 'force-dynamic';

export async function GET() {
  const timezones = getTimeZonesForSelect();
  return NextResponse.json(
    { timezones },
    {
      headers: {
        'Cache-Control': 'no-store',
      },
    }
  );
}
