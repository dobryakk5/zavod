'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ReactNode, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetClose, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Menu } from 'lucide-react';

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000')
  .replace(/\/$/, '');
const buildApiUrl = (path: string) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

const navItems = [
  { href: '/welcome', label: 'Приветствие' },
  { href: '/analytics', label: 'Аналитика' },
  { href: '/posts', label: 'Посты' },
  { href: '/schedule', label: 'Расписание' },
  { href: '/seo', label: 'SEO' },
  { href: '/articles', label: 'Статьи' },
  { href: '/settings', label: 'Настройки' },
  { href: '/products', label: 'Продукты' }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isPublicRoute = pathname === '/' || pathname.startsWith('/login');

  const onLogout = async () => {
    try {
      await fetch(buildApiUrl('/auth/logout/'), {
        method: 'POST',
        credentials: 'include'
      });
    } catch (error) {
      console.error('logout failed', error);
    }
    router.push('/');
  };

  useEffect(() => {
    if (!isPublicRoute) {
      setMobileMenuOpen(false);
    }
  }, [isPublicRoute, pathname]);

  const navLinks = useMemo(() => {
    return navItems.map((item) => {
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
    });
  }, [pathname]);

  if (isPublicRoute) {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen md:flex">
      <header className="sticky top-0 z-40 flex items-center justify-between border-b bg-background px-4 py-3 md:hidden">
        <Link href="/dashboard" className="text-base font-semibold">
          Контент-завод
        </Link>
        <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" aria-label="Открыть меню">
              <Menu className="h-5 w-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="flex w-72 flex-col gap-4 p-4">
            <div className="text-xl font-bold">Контент-завод</div>
            <nav className="flex flex-col gap-1">
              {navItems.map((item) => {
                const active = pathname === item.href || pathname.startsWith(`${item.href}/`);

                return (
                  <SheetClose key={item.href} asChild>
                    <Link
                      href={item.href}
                      className={`rounded-md px-3 py-2 text-sm ${active ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}`}
                    >
                      {item.label}
                    </Link>
                  </SheetClose>
                );
              })}
            </nav>
            <div className="mt-auto">
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  setMobileMenuOpen(false);
                  void onLogout();
                }}
              >
                Выйти
              </Button>
            </div>
          </SheetContent>
        </Sheet>
      </header>

      <aside className="hidden w-64 flex-col gap-4 border-r bg-muted/30 p-4 md:flex">
        <div className="text-xl font-bold">Контент-завод</div>
        <nav className="flex flex-col gap-1">{navLinks}</nav>
        <div className="mt-auto">
          <Button variant="outline" className="w-full" onClick={onLogout}>
            Выйти
          </Button>
        </div>
      </aside>

      <main className="flex-1 p-4 md:p-6">{children}</main>
    </div>
  );
}
