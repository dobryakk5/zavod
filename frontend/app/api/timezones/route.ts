import { NextResponse } from 'next/server';
import { getTimeZonesForSelect } from '@/lib/timezones';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const timezones = getTimeZonesForSelect();
    return NextResponse.json(
      { timezones },
      {
        headers: {
          'Cache-Control': 'no-store',
        },
      }
    );
  } catch (error) {
    console.error('Failed to build timezones list', error);
    return NextResponse.json(
      {
        timezones: [],
      },
      {
        headers: {
          'Cache-Control': 'no-store',
        },
      }
    );
  }
}
