'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { clientApi } from '@/lib/api/client';
import type { ClientInfo } from '@/lib/types';
import { DASHBOARD_ROUTE, MARKETING_ROUTE } from '@/lib/routes';

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:4000').replace(/\/$/, '');

const buildApiUrl = (path: string) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

const VK_CLIENT_NAME_RE = /^vk_\d+$/i;

export const APP_SHELL_NAV_ITEMS = [
  { href: DASHBOARD_ROUTE, label: 'Дашборд' },
  { href: MARKETING_ROUTE, label: 'Маркетинг' },
  { href: '/products', label: 'Продукты' },
  { href: '/settings', label: 'Настройки' },
];

export function getAppShellRouteTitle(pathname: string): string {
  const matchedNavItem = APP_SHELL_NAV_ITEMS.find(
    (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
  );

  if (matchedNavItem) {
    return matchedNavItem.label;
  }

  if (pathname === DASHBOARD_ROUTE || pathname.startsWith(`${DASHBOARD_ROUTE}/`)) return 'Дашборд';
  if (pathname === '/analytics' || pathname.startsWith('/analytics/')) return 'Аналитика';
  if (pathname === '/posts' || pathname.startsWith('/posts/')) return 'Посты';
  if (pathname === '/seo' || pathname.startsWith('/seo/')) return 'SEO';
  if (pathname === '/articles' || pathname.startsWith('/articles/')) return 'Статьи';
  if (pathname === '/clients' || pathname.startsWith('/clients/')) return 'Клиенты';
  if (pathname === '/templates' || pathname.startsWith('/templates/')) return 'Шаблоны';
  if (pathname === '/topics' || pathname.startsWith('/topics/')) return 'Темы';
  if (pathname === '/schedule' || pathname.startsWith('/schedule/')) return 'Расписание';
  if (pathname === '/product' || pathname.startsWith('/product/')) return 'Продукт';
  if (pathname === '/map' || pathname.startsWith('/map/')) return 'Карта';
  if (pathname === '/contact' || pathname.startsWith('/contact/')) return 'Контакт';

  return 'Платформа';
}

export function isAppShellPublicRoute(pathname: string): boolean {
  const isClientPageEditorRoute = /^\/c\/[^/]+\/edit(?:\/.*)?$/.test(pathname);
  return (
    pathname === '/'
    || pathname.startsWith('/features')
    || pathname.startsWith('/login')
    || pathname.startsWith('/auth/')
    || pathname.startsWith('/kb/share')
    || pathname.startsWith('/quiz/')
    || (pathname.startsWith('/c/') && !isClientPageEditorRoute)
  );
}

type SocialAccount = {
  provider?: string;
  provider_id?: string;
  created_at?: string;
  extra_data?: {
    photo_url?: string;
    photo_storage_url?: string;
    first_name?: string;
    username?: string;
    screen_name?: string;
    last_name?: string;
    email?: string;
  };
};

export type AuthProviderUser = {
  telegramId?: string;
  vkId?: string;
  firstName?: string;
  lastName?: string;
  username?: string;
  photoUrl?: string | null;
  authDate?: string;
  isDev?: boolean;
  contactId?: number | null;
  tenantId?: number | null;
};

export type LoggedUserModalData = {
  error?: string;
  sources?: {
    social_accounts?: unknown;
    telegram_auth?: unknown;
    vk_auth?: unknown;
  };
  user?: {
    primary?: AuthProviderUser | null;
    telegram?: AuthProviderUser | null;
    vk?: AuthProviderUser | null;
  };
  accounts?: SocialAccount[];
};

function getVkDisplayName(accounts: SocialAccount[]): string | null {
  const vkAccount = accounts.find((account) => account.provider === 'vk');
  const firstName = (vkAccount?.extra_data?.first_name || '').trim();
  const lastName = (vkAccount?.extra_data?.last_name || '').trim();
  const screenName = (vkAccount?.extra_data?.screen_name || '').trim();
  const username = (vkAccount?.extra_data?.username || '').trim().replace(/^@+/, '');
  const fullName = [firstName, lastName].filter(Boolean).join(' ').trim();

  return fullName || screenName || username || null;
}

function getDisplayClientName(clientName: string | undefined, vkDisplayName: string | null): string | null {
  const normalizedClientName = (clientName || '').trim();
  if (!normalizedClientName) return null;
  if (!VK_CLIENT_NAME_RE.test(normalizedClientName)) return normalizedClientName;
  return vkDisplayName || normalizedClientName;
}

export function useAppShellState() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [avatarInitial, setAvatarInitial] = useState('U');
  const [userModalOpen, setUserModalOpen] = useState(false);
  const [userModalLoading, setUserModalLoading] = useState(false);
  const [loggedUserData, setLoggedUserData] = useState<LoggedUserModalData | null>(null);
  const [clientInfo, setClientInfo] = useState<ClientInfo | null>(null);
  const [clientInfoLoading, setClientInfoLoading] = useState(false);
  const [switchingClient, setSwitchingClient] = useState(false);
  const [vkDisplayName, setVkDisplayName] = useState<string | null>(null);

  const isPublicRoute = isAppShellPublicRoute(pathname);

  const onLogout = async () => {
    try {
      await fetch(buildApiUrl('/auth/logout/'), {
        method: 'POST',
        credentials: 'include',
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
        fetch(buildApiUrl('/auth/vk'), { credentials: 'include' }),
      ]);

      const accountsPayload = accountsResponse.ok ? await accountsResponse.json().catch(() => null) : null;
      const telegramPayload = telegramResponse.ok ? await telegramResponse.json().catch(() => null) : null;
      const vkPayload = vkResponse.ok ? await vkResponse.json().catch(() => null) : null;

      const accounts = Array.isArray(accountsPayload?.accounts) ? accountsPayload.accounts : [];
      setLoggedUserData({
        sources: {
          social_accounts: accountsPayload,
          telegram_auth: telegramPayload,
          vk_auth: vkPayload,
        },
        user: {
          primary: telegramPayload?.user ?? vkPayload?.user ?? null,
          telegram: telegramPayload?.user ?? null,
          vk: vkPayload?.user ?? null,
        },
        accounts,
      });
    } catch {
      setLoggedUserData({
        error: 'Не удалось загрузить данные пользователя',
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
      setAvatarUrl(null);
      setAvatarInitial('U');
      setClientInfo(null);
      setVkDisplayName(null);
      return;
    }

    let cancelled = false;

    const fetchAvatar = async () => {
      try {
        const response = await fetch(buildApiUrl('/auth/social/accounts'), {
          credentials: 'include',
        });

        if (!response.ok) {
          return;
        }

        const data = await response.json();
        const accounts = Array.isArray(data?.accounts) ? (data.accounts as SocialAccount[]) : [];
        const photoUrl = accounts
          .map((account) => account.extra_data?.photo_storage_url || account.extra_data?.photo_url)
          .find((url): url is string => typeof url === 'string' && url.trim().length > 0);
        const name = accounts
          .map((account) => account.extra_data?.username || account.extra_data?.screen_name || account.extra_data?.first_name)
          .find((value): value is string => typeof value === 'string' && value.trim().length > 0);
        const normalizedName = (name || '').trim().replace(/^@+/, '');
        const initial = (normalizedName[0] || 'U').toUpperCase();

        if (!cancelled) {
          setAvatarUrl(photoUrl ?? null);
          setAvatarInitial(initial);
          setVkDisplayName(getVkDisplayName(accounts));
        }
      } catch {
        if (!cancelled) {
          setAvatarUrl(null);
          setAvatarInitial('U');
          setVkDisplayName(null);
        }
      }
    };

    void fetchAvatar();

    return () => {
      cancelled = true;
    };
  }, [isPublicRoute]);

  useEffect(() => {
    if (isPublicRoute) {
      return;
    }

    let cancelled = false;

    const fetchClientInfo = async () => {
      setClientInfoLoading(true);
      try {
        const info = await clientApi.info();
        if (!cancelled) {
          setClientInfo(info);
        }
      } catch {
        if (!cancelled) {
          setClientInfo(null);
        }
      } finally {
        if (!cancelled) {
          setClientInfoLoading(false);
        }
      }
    };

    void fetchClientInfo();

    return () => {
      cancelled = true;
    };
  }, [isPublicRoute, pathname]);

  const handleClientSwitch = async (value: string) => {
    const nextClientId = Number(value);
    if (!Number.isFinite(nextClientId) || clientInfo?.active_client_id === nextClientId) {
      return;
    }

    setSwitchingClient(true);
    try {
      const nextInfo = await clientApi.setActiveClient(nextClientId);
      setClientInfo(nextInfo);
      window.location.reload();
    } catch (error) {
      console.error('Failed to switch active client', error);
      setSwitchingClient(false);
    }
  };

  const activeClientDisplayName = getDisplayClientName(clientInfo?.client.name, vkDisplayName);

  return {
    pathname,
    isPublicRoute,
    navItems: APP_SHELL_NAV_ITEMS,
    mobileMenuOpen,
    setMobileMenuOpen,
    avatarUrl,
    avatarInitial,
    clearAvatar: () => setAvatarUrl(null),
    userModalOpen,
    setUserModalOpen,
    userModalLoading,
    loggedUserData,
    clientInfo,
    activeClientDisplayName,
    clientInfoLoading,
    switchingClient,
    openLoggedUserModal,
    onLogout,
    handleClientSwitch,
  };
}
