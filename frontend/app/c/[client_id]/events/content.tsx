'use client';

import Link from 'next/link';
import type { EventProductRow } from './event-products';

type EventsContentProps = {
  clientId: number;
  displayName: string;
  eventProducts: EventProductRow[];
  titleAs?: 'h1' | 'h2';
  showBackLink?: boolean;
  backHref?: string;
  backLabel?: string;
};

export default function EventsContent({
  clientId,
  displayName,
  eventProducts,
  titleAs = 'h1',
  showBackLink = true,
  backHref,
  backLabel = 'На страницу клиента',
}: EventsContentProps) {
  const TitleTag = titleAs;
  const resolvedBackHref = backHref || `/c/${clientId}`;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border p-6 shadow-sm space-y-2">
        <TitleTag className="text-2xl font-semibold">Мероприятия</TitleTag>
        <p className="text-sm text-muted-foreground">{displayName}</p>
        {showBackLink && (
          <Link href={resolvedBackHref} className="inline-flex rounded-lg border px-3 py-2 text-sm hover:bg-accent">
            {backLabel}
          </Link>
        )}
      </div>

      {eventProducts.length === 0 ? (
        <div className="rounded-2xl border p-6 text-sm text-muted-foreground">
          Сейчас нет опубликованных мероприятий.
        </div>
      ) : (
        <div className="space-y-3">
          {eventProducts.map((item) => (
            <Link
              key={item.id}
              href={`/c/${clientId}/events/${item.id}`}
              className="block rounded-2xl border p-5 shadow-sm transition-colors hover:border-primary/50 hover:bg-accent/20"
            >
              <article>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <h2 className="text-lg font-semibold">{item.eventTitle}</h2>
                  {(item.durationLabel || item.priceLabel) && (
                    <div className="text-right">
                      {item.durationLabel && <div className="text-sm text-muted-foreground">{item.durationLabel}</div>}
                      {item.priceLabel && <div className="text-base font-semibold">{item.priceLabel}</div>}
                    </div>
                  )}
                </div>
                <div className="mt-3 grid gap-1 text-sm text-muted-foreground sm:grid-cols-2">
                  <p>Дата: {item.dateLabel}</p>
                  <p>Локация: {item.locationLabel}</p>
                </div>
                {item.shortDescription && <p className="mt-3 text-sm text-foreground/90">{item.shortDescription}</p>}
              </article>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
