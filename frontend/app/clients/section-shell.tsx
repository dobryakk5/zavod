import Link from 'next/link';
import type { ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { CLIENTS_SECTION_LINKS, type ClientsSectionKey } from './navigation';

type ClientsSectionShellProps = {
  section?: ClientsSectionKey | null;
  title: string;
  description: string;
  children: ReactNode;
  primaryAction?: ReactNode;
  desktopActions?: ReactNode;
  backHref?: string;
  backLabel?: string;
  showBackButton?: boolean;
};

export function ClientsSectionShell({
  section = null,
  title,
  description,
  children,
  primaryAction,
  desktopActions,
  backHref = '/clients',
  backLabel = 'Все разделы CRM',
  showBackButton = true,
}: ClientsSectionShellProps) {
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <div className="-mx-4 sticky top-0 z-20 border-b border-black/5 bg-[#f4f1ea]/95 px-4 pb-3 pt-2 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
        <div className="flex flex-col gap-3">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              {showBackButton ? (
                <Link
                  href={backHref}
                  className="mb-1 inline-flex text-xs font-medium text-slate-500 transition-colors hover:text-slate-900"
                >
                  {backLabel}
                </Link>
              ) : null}
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-3xl">{title}</h1>
              <p className="mt-1 max-w-3xl text-sm text-slate-600">{description}</p>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              {primaryAction}
              {desktopActions ? <div className="hidden md:flex md:items-center md:gap-2">{desktopActions}</div> : null}
            </div>
          </div>

          <nav aria-label="Разделы CRM" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
            {CLIENTS_SECTION_LINKS.map((item) => {
              const isActive = item.key === section;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'border-slate-900 bg-slate-900 text-white'
                      : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900'
                  )}
                >
                  {item.title}
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      <div className="space-y-4 pb-6">{children}</div>
    </div>
  );
}
