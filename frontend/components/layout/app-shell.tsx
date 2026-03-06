'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { ReactNode, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
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
  { href: '/seo', label: 'SEO' },
  { href: '/articles', label: 'Статьи' },
  { href: '/products', label: 'Продукты' },
  { href: '/clients', label: 'Клиенты' },
  { href: '/settings', label: 'Настройки' }
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarAvatarUrl, setSidebarAvatarUrl] = useState<string | null>(null);
  const [sidebarAvatarInitial, setSidebarAvatarInitial] = useState('U');
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [userModalLoading, setUserModalLoading] = useState(false);
  const [loggedUserData, setLoggedUserData] = useState<Record<string, unknown> | null>(null);
  const isClientPageEditorRoute = /^\/c\/[^/]+\/edit(?:\/.*)?$/.test(pathname);
  const isPublicRoute =
    pathname === '/'
    || pathname.startsWith('/login')
    || pathname.startsWith('/kb/share')
    || pathname.startsWith('/quiz/')
    || (pathname.startsWith('/c/') && !isClientPageEditorRoute);

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

  const openLoggedUserModal = async () => {
    setUserModalOpen(true);
    setUserModalLoading(true);

    try {
      const [accountsResponse, telegramResponse, vkResponse] = await Promise.all([
        fetch(buildApiUrl('/auth/social/accounts'), { credentials: 'include' }),
        fetch(buildApiUrl('/auth/telegram'), { credentials: 'include' }),
        fetch(buildApiUrl('/auth/vk'), { credentials: 'include' })
      ]);

      const accountsPayload = accountsResponse.ok ? await accountsResponse.json().catch(() => null) : null;
      const telegramPayload = telegramResponse.ok ? await telegramResponse.json().catch(() => null) : null;
      const vkPayload = vkResponse.ok ? await vkResponse.json().catch(() => null) : null;

      const accounts = Array.isArray(accountsPayload?.accounts) ? accountsPayload.accounts : [];
      setLoggedUserData({
        sources: {
          social_accounts: accountsPayload,
          telegram_auth: telegramPayload,
          vk_auth: vkPayload
        },
        user: {
          primary: telegramPayload?.user ?? vkPayload?.user ?? null,
          telegram: telegramPayload?.user ?? null,
          vk: vkPayload?.user ?? null
        },
        accounts
      });
    } catch {
      setLoggedUserData({
        error: 'Не удалось загрузить данные пользователя'
      });
    } finally {
      setUserModalLoading(false);
    }
  };

  useEffect(() => {
    if (!isPublicRoute) {
      setMobileMenuOpen(false);
    }
  }, [isPublicRoute, pathname]);

  useEffect(() => {
    if (isPublicRoute) {
      setSidebarAvatarUrl(null);
      setSidebarAvatarInitial('U');
      return;
    }

    let cancelled = false;

    const fetchSidebarAvatar = async () => {
      try {
        const response = await fetch(buildApiUrl('/auth/social/accounts'), {
          credentials: 'include'
        });
        if (!response.ok) {
          return;
        }

        const data = await response.json();
        const accounts = Array.isArray(data?.accounts) ? data.accounts : [];
        const photoUrl = accounts
          .map((account: {
            extra_data?: {
              photo_url?: string;
              photo_storage_url?: string;
              first_name?: string;
              username?: string;
              screen_name?: string;
            };
          }) => account?.extra_data?.photo_storage_url || account?.extra_data?.photo_url)
          .find((url: unknown) => typeof url === 'string' && url.trim().length > 0) as string | undefined;
        const name = accounts
          .map((account: {
            extra_data?: {
              first_name?: string;
              username?: string;
              screen_name?: string;
            };
          }) => account?.extra_data?.username || account?.extra_data?.screen_name || account?.extra_data?.first_name)
          .find((value: unknown) => typeof value === 'string' && value.trim().length > 0) as string | undefined;
        const normalizedName = (name || '').trim().replace(/^@+/, '');
        const initial = (normalizedName[0] || 'U').toUpperCase();

        if (!cancelled) {
          setSidebarAvatarUrl(photoUrl ?? null);
          setSidebarAvatarInitial(initial);
        }
      } catch {
        if (!cancelled) {
          setSidebarAvatarUrl(null);
          setSidebarAvatarInitial('U');
        }
      }
    };

    void fetchSidebarAvatar();

    return () => {
      cancelled = true;
    };
  }, [isPublicRoute]);

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
            <div className="text-xl font-bold">ИИ маркетинг</div>
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
        <div className="text-xl font-bold">Fibonatty</div>
        <nav className="flex flex-col gap-1">{navLinks}</nav>
        <div className="mt-auto flex items-center gap-2">
          <Button variant="outline" className="flex-1" onClick={onLogout}>
            Выйти
          </Button>
          <button
            type="button"
            aria-label="Открыть данные пользователя"
            className="flex h-8 w-8 items-center justify-center overflow-hidden rounded-full ring-1 ring-border"
            onClick={() => {
              void openLoggedUserModal();
            }}
          >
            {sidebarAvatarUrl ? (
              <Image
                src={sidebarAvatarUrl}
                alt="Аватар пользователя"
                width={32}
                height={32}
                className="h-8 w-8 rounded-full object-cover"
                unoptimized
                loading="lazy"
                onError={() => setSidebarAvatarUrl(null)}
              />
            ) : (
              <span className="flex h-8 w-8 items-center justify-center bg-primary/15 text-xs font-semibold text-primary">
                {sidebarAvatarInitial}
              </span>
            )}
          </button>
        </div>
      </aside>

      <main className="flex-1 p-4 md:p-6">{children}</main>

      <Dialog open={userModalOpen} onOpenChange={setUserModalOpen}>
        <DialogContent className="sm:max-w-2xl bg-white text-gray-900 dark:bg-white dark:text-gray-900 dark:border-gray-200">
          <DialogHeader>
            <DialogTitle>Данные авторизованного пользователя</DialogTitle>
            <DialogDescription className="text-gray-600">
              Telegram/VK auth profile и связанные социальные аккаунты.
            </DialogDescription>
          </DialogHeader>

          {userModalLoading ? (
            <div className="text-sm text-gray-600">Загрузка...</div>
          ) : (
            <pre className="max-h-[60vh] overflow-auto rounded-md bg-muted p-3 text-xs leading-relaxed">
              {JSON.stringify(loggedUserData, null, 2)}
            </pre>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
