'use client';

import Image from 'next/image';
import Link from 'next/link';
import { ReactNode } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Sheet, SheetClose, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { LayoutDashboard, Megaphone, Menu, Package2, Settings2 } from 'lucide-react';
import { getAppShellRouteTitle, useAppShellState } from './use-app-shell-state';
import { DASHBOARD_ROUTE, MARKETING_ROUTE } from '@/lib/routes';

function UserAvatar({
  avatarUrl,
  avatarInitial,
  onClick,
  onImageError,
  interactive = true,
}: {
  avatarUrl: string | null;
  avatarInitial: string;
  onClick?: () => void;
  onImageError?: () => void;
  interactive?: boolean;
}) {
  const content = (
    <>
      {avatarUrl ? (
        <Image
          src={avatarUrl}
          alt="Аватар пользователя"
          width={40}
          height={40}
          className="h-10 w-10 rounded-full object-cover"
          unoptimized
          loading="lazy"
          onError={onImageError}
        />
      ) : (
        <span className="flex h-full w-full items-center justify-center bg-emerald-50 text-sm font-semibold text-emerald-700">
          {avatarInitial}
        </span>
      )}
    </>
  );

  if (!interactive) {
    return (
      <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-gray-200 bg-white shadow-sm">
        {content}
      </div>
    );
  }

  return (
    <button
      type="button"
      aria-label="Открыть данные пользователя"
      className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border border-gray-200 bg-white shadow-sm transition-colors hover:border-gray-300"
      onClick={onClick}
    >
      {content}
    </button>
  );
}

function ClientSwitcher({
  value,
  loading,
  switching,
  memberships,
  onChange,
}: {
  value?: string;
  loading: boolean;
  switching: boolean;
  memberships: Array<{ client: { id: number; name: string } }>;
  onChange: (value: string) => void;
}) {
  return (
    <div className="min-w-[200px]">
      <Select value={value} onValueChange={onChange} disabled={loading || switching}>
        <SelectTrigger className="h-10 w-full rounded-2xl border-gray-200 bg-white text-sm text-gray-700 shadow-none">
          <SelectValue placeholder={loading ? 'Загрузка проектов...' : 'Выберите проект'} />
        </SelectTrigger>
        <SelectContent>
          {memberships.map((membership) => (
            <SelectItem key={membership.client.id} value={String(membership.client.id)}>
              {membership.client.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function getNavItemIcon(href: string) {
  if (href === DASHBOARD_ROUTE) return LayoutDashboard;
  if (href === MARKETING_ROUTE) return Megaphone;
  if (href === '/products') return Package2;
  if (href === '/settings') return Settings2;
  return LayoutDashboard;
}

function formatRoleLabel(role?: string | null) {
  if (role === 'owner') return 'Владелец';
  if (role === 'editor') return 'Редактор';
  if (role === 'viewer') return 'Наблюдатель';
  return 'Участник команды';
}

function NavigationLink({
  href,
  label,
  active,
  mobile = false,
}: {
  href: string;
  label: string;
  active: boolean;
  mobile?: boolean;
}) {
  const Icon = getNavItemIcon(href);

  if (mobile) {
    return (
      <Link
        href={href}
        className={`flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition-colors ${
          active
            ? 'border-gray-200 bg-white font-medium text-gray-950'
            : 'border-gray-100 bg-white text-gray-600 hover:text-gray-950'
        }`}
      >
        <Icon className={`h-4 w-4 ${active ? 'text-gray-900' : 'text-gray-400'}`} />
        {label}
      </Link>
    );
  }

  return (
    <Link
      href={href}
      className={`flex items-center gap-3 rounded-2xl px-4 py-3 text-base transition-colors ${
        active
          ? 'bg-[rgba(92,82,224,0.12)] font-medium text-[#5c52e0]'
          : 'text-[#746d66] hover:bg-white/60 hover:text-gray-950'
      }`}
    >
      <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-current opacity-50" />
      {label}
    </Link>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const {
    pathname,
    isPublicRoute,
    navItems,
    mobileMenuOpen,
    setMobileMenuOpen,
    avatarUrl,
    avatarInitial,
    clearAvatar,
    userModalOpen,
    setUserModalOpen,
    userModalLoading,
    loggedUserData,
    clientInfo,
    clientInfoLoading,
    switchingClient,
    openLoggedUserModal,
    onLogout,
    handleClientSwitch,
  } = useAppShellState();

  const currentTitle = getAppShellRouteTitle(pathname);

  if (isPublicRoute) {
    return <>{children}</>;
  }

  const memberships = clientInfo?.memberships ?? [];
  const canSwitchClient = memberships.length > 1;
  const activeMembership = memberships.find((membership) => membership.client.id === clientInfo?.active_client_id) ?? memberships[0];

  return (
    <div className="min-h-screen bg-[#f4f1ea] text-gray-900">
      <div className="flex min-h-screen w-full">
        <aside className="hidden w-[250px] shrink-0 border-r border-black/5 bg-[linear-gradient(180deg,#f3f0ea_0%,#ebe7e0_100%)] px-[18px] py-[26px] lg:flex lg:flex-col">
          <Link href={DASHBOARD_ROUTE} className="px-3 py-1">
            <div
              className="text-[24px] text-gray-950"
              style={{ fontFamily: 'Georgia, Times New Roman, serif' }}
            >
              Fibo<span className="text-[#5c52e0]">n</span>atty
            </div>
          </Link>

          <div className="-mx-[18px] mt-6 border-y border-black/5 bg-white px-[18px] py-5">
            <div className="px-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-[#948c84]">Активный проект</div>
              <div className="mt-2 text-[17px] font-semibold text-gray-950">
                {clientInfo?.client.name || 'Загрузка проекта...'}
              </div>
              <div className="mt-1 text-sm text-[#746d66]">{formatRoleLabel(activeMembership?.role)}</div>

              {canSwitchClient ? (
                <div className="mt-4">
                  <ClientSwitcher
                    value={clientInfo ? String(clientInfo.active_client_id) : undefined}
                    loading={clientInfoLoading}
                    switching={switchingClient}
                    memberships={memberships}
                    onChange={(value) => void handleClientSwitch(value)}
                  />
                </div>
              ) : null}
            </div>
          </div>

          <nav className="mt-6 space-y-[10px]">
            {navItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return <NavigationLink key={item.href} href={item.href} label={item.label} active={active} />;
            })}
          </nav>

          <div className="mt-auto space-y-3">
            <button
              type="button"
              className="flex w-full items-center gap-3 rounded-[22px] border border-black/10 bg-[rgba(255,255,255,0.88)] px-4 py-4 text-left shadow-[0_10px_24px_rgba(0,0,0,0.04)] transition-colors hover:border-black/15"
              onClick={() => {
                void openLoggedUserModal();
              }}
            >
              <UserAvatar
                avatarUrl={avatarUrl}
                avatarInitial={avatarInitial}
                onImageError={clearAvatar}
                interactive={false}
              />
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-gray-950">Профиль и соцаккаунты</div>
                <div className="mt-1 text-xs text-[#746d66]">Telegram, VK и связанные учётные записи</div>
              </div>
            </button>

            <Button
              variant="outline"
              className="h-11 w-full rounded-2xl border-black/10 bg-white/90"
              onClick={() => void onLogout()}
            >
              Выйти
            </Button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-black/5 bg-white/90 px-4 py-4 backdrop-blur sm:px-6 lg:hidden">
            <div className="flex items-center justify-between gap-4">
              <div className="min-w-0">
                <Link href={DASHBOARD_ROUTE} className="text-sm font-medium text-gray-950">
                  ✦ Fibonatty
                </Link>
                <div className="truncate text-sm text-gray-500">{currentTitle}</div>
              </div>

              <Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
                <SheetTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-9 w-9" aria-label="Открыть меню">
                    <Menu className="h-5 w-5" />
                  </Button>
                </SheetTrigger>
                <SheetContent side="right" className="w-[320px] border-l border-gray-100 bg-[#f4f1ea] px-0">
                  <div className="flex h-full flex-col">
                    <div className="border-b border-gray-100 px-6 py-5">
                      <div className="text-sm font-medium text-gray-950">✦ Fibonatty</div>
                      <div className="mt-1 text-sm text-gray-500">{currentTitle}</div>
                    </div>

                    <div className="flex-1 space-y-6 overflow-y-auto px-6 py-6">
                      <div className="rounded-3xl border border-gray-200 bg-white px-4 py-4 shadow-sm">
                        <div className="text-xs uppercase tracking-[0.16em] text-gray-400">Активный проект</div>
                        <div className="mt-2 text-base font-semibold text-gray-950">
                          {clientInfo?.client.name || 'Загрузка проекта...'}
                        </div>
                        <div className="mt-1 text-sm text-gray-500">{formatRoleLabel(activeMembership?.role)}</div>

                        {canSwitchClient ? (
                          <div className="mt-4">
                            <ClientSwitcher
                              value={clientInfo ? String(clientInfo.active_client_id) : undefined}
                              loading={clientInfoLoading}
                              switching={switchingClient}
                              memberships={memberships}
                              onChange={(value) => void handleClientSwitch(value)}
                            />
                          </div>
                        ) : null}
                      </div>

                      <nav className="space-y-2">
                        {navItems.map((item) => {
                          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
                          return (
                            <SheetClose key={item.href} asChild>
                              <div>
                                <NavigationLink href={item.href} label={item.label} active={active} mobile />
                              </div>
                            </SheetClose>
                          );
                        })}
                      </nav>

                      <button
                        type="button"
                        className="flex w-full items-center gap-3 rounded-3xl border border-gray-200 bg-white px-4 py-4 text-left shadow-sm"
                        onClick={() => {
                          void openLoggedUserModal();
                        }}
                      >
                        <UserAvatar
                          avatarUrl={avatarUrl}
                          avatarInitial={avatarInitial}
                          onImageError={clearAvatar}
                          interactive={false}
                        />
                        <div>
                          <div className="text-sm font-medium text-gray-950">Профиль и соц. аккаунты</div>
                          <div className="text-xs text-gray-500">Telegram, VK и связанные учётные записи</div>
                        </div>
                      </button>
                    </div>

                    <div className="border-t border-gray-200 px-6 py-5">
                      <Button
                        variant="outline"
                        className="w-full border-gray-200 bg-white"
                        onClick={() => {
                          setMobileMenuOpen(false);
                          void onLogout();
                        }}
                      >
                        Выйти
                      </Button>
                    </div>
                  </div>
                </SheetContent>
              </Sheet>
            </div>
          </header>

          <main className="flex-1 px-4 py-4 sm:px-6 sm:py-6 lg:px-8 lg:py-6">{children}</main>
        </div>
      </div>

      <Dialog open={userModalOpen} onOpenChange={setUserModalOpen}>
        <DialogContent className="border-gray-200 bg-white text-gray-900 sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Данные авторизованного пользователя</DialogTitle>
            <DialogDescription className="text-gray-600">
              Telegram/VK auth profile и связанные социальные аккаунты.
            </DialogDescription>
          </DialogHeader>

          {userModalLoading ? (
            <div className="text-sm text-gray-600">Загрузка...</div>
          ) : (
            <pre className="max-h-[60vh] overflow-auto rounded-2xl bg-gray-50 p-4 text-xs leading-relaxed text-gray-700">
              {JSON.stringify(loggedUserData, null, 2)}
            </pre>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
