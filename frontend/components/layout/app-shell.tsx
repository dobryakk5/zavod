'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ReactNode } from 'react';
import { Button } from '@/components/ui/button';

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000';

const navItems = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/posts', label: 'Посты' },
  { href: '/schedule', label: 'Расписание' },
  { href: '/analytics', label: 'Аналитика' }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const onLogout = async () => {
    try {
      await fetch(`${API_URL}/api/auth/logout/`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch (error) {
      console.error('logout failed', error);
    }
    router.push('/login');
  };

  if (pathname === '/' || pathname.startsWith('/login')) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 flex-col gap-4 border-r bg-muted/30 p-4">
        <div className="text-xl font-bold">Контент-завод</div>
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`rounded-md px-3 py-2 text-sm ${active ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto">
          <Button variant="outline" className="w-full" onClick={onLogout}>
            Выйти
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
