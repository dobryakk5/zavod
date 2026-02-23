'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import { Button } from '@/components/ui/button';
import { TelegramAuthButton } from '@/components/auth/TelegramAuthButton';

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
const hasApiUrl = Boolean(API_URL);
const buildUrl = (path: string) => `${API_URL}${path}`;
const VK_REDIRECT_URI =
  process.env.NEXT_PUBLIC_VK_AUTH_REDIRECT_URI ??
  (typeof window !== 'undefined' ? `${window.location.origin}/auth/vk/callback` : '');

type ProviderId = 'telegram' | 'vk';

interface LinkedAccount {
  provider: ProviderId;
  provider_id: string;
  extra_data: {
    first_name?: string;
    last_name?: string;
    username?: string;
    screen_name?: string;
    photo_url?: string;
  };
}

const PROVIDERS: Array<{
  id: ProviderId;
  label: string;
  description: string;
  bgClass: string;
  icon: React.ReactNode;
}> = [
  {
    id: 'telegram',
    label: 'Telegram',
    description: 'Вход через Telegram-бота',
    bgClass: 'bg-[#0088cc]/10',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="#0088cc" aria-hidden="true">
        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.17 13.967l-2.965-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.983.592z" />
      </svg>
    ),
  },
  {
    id: 'vk',
    label: 'ВКонтакте',
    description: 'Вход через аккаунт VK',
    bgClass: 'bg-[#0077FF]/10',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="#0077FF" aria-hidden="true">
        <path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.744c-.66 0-.862-.523-2.049-1.727-1.033-1-1.49-1.135-1.744-1.135-.356 0-.458.102-.458.593v1.575c0 .424-.135.678-1.253.678-1.846 0-3.896-1.118-5.335-3.202C5.1 11.366 4.5 9.218 4.5 8.775c0-.254.102-.491.593-.491h1.744c.44 0 .61.203.78.677.863 2.49 2.303 4.675 2.896 4.675.22 0 .322-.102.322-.66V9.633c-.068-1.186-.695-1.287-.695-1.71 0-.204.17-.407.44-.407h2.744c.373 0 .508.203.508.643v3.473c0 .372.17.508.271.508.22 0 .407-.136.813-.542 1.254-1.406 2.151-3.574 2.151-3.574.119-.254.322-.491.763-.491h1.744c.525 0 .644.27.525.643-.22 1.017-2.354 4.031-2.354 4.031-.186.305-.254.44 0 .78.186.254.796.779 1.203 1.253.745.847 1.32 1.558 1.473 2.049.17.491-.085.745-.576.745z" />
      </svg>
    ),
  },
];

export function ConnectedAccounts() {
  const [accounts, setAccounts] = useState<LinkedAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<ProviderId | null>(null);
  const [errors, setErrors] = useState<Partial<Record<ProviderId, string>>>({});
  const [showTgWidget, setShowTgWidget] = useState(false);
  const closeTimerRef = useRef<number | null>(null);
  const messageHandlerRef = useRef<((event: MessageEvent) => void) | null>(null);

  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? '';

  const clearPopupHandlers = useCallback(() => {
    if (closeTimerRef.current !== null) {
      window.clearInterval(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    if (messageHandlerRef.current) {
      window.removeEventListener('message', messageHandlerRef.current);
      messageHandlerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearPopupHandlers(), [clearPopupHandlers]);

  const setError = (provider: ProviderId, message: string) => {
    setErrors((prev) => ({ ...prev, [provider]: message }));
  };

  const clearError = (provider: ProviderId) => {
    setErrors((prev) => ({ ...prev, [provider]: undefined }));
  };

  const fetchAccounts = useCallback(async () => {
    if (!hasApiUrl) {
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(buildUrl('/auth/social/accounts'), { credentials: 'include' });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setAccounts(Array.isArray(data?.accounts) ? data.accounts : []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchAccounts();
  }, [fetchAccounts]);

  const findLinked = (provider: ProviderId) => accounts.find((account) => account.provider === provider);

  const handleUnlink = async (provider: ProviderId) => {
    if (!hasApiUrl) {
      setError(provider, 'NEXT_PUBLIC_API_URL не задан');
      return;
    }
    if (!confirm(`Отвязать ${provider === 'telegram' ? 'Telegram' : 'ВКонтакте'}?`)) {
      return;
    }

    setActionLoading(provider);
    clearError(provider);
    try {
      const response = await fetch(buildUrl(`/auth/social/unlink/${provider}`), {
        method: 'DELETE',
        credentials: 'include',
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok) {
        await fetchAccounts();
      } else {
        setError(provider, data?.error || 'Ошибка отвязки');
      }
    } catch {
      setError(provider, 'Ошибка соединения');
    } finally {
      setActionLoading(null);
    }
  };

  const handleLinkVk = async () => {
    if (!hasApiUrl) {
      setError('vk', 'NEXT_PUBLIC_API_URL не задан');
      return;
    }

    setActionLoading('vk');
    clearError('vk');
    clearPopupHandlers();

    try {
      const response = await fetch(buildUrl('/auth/vk/url'), { credentials: 'include' });
      const data = await response.json().catch(() => ({}));
      const url = data?.url as string | undefined;
      const state = data?.state as string | undefined;
      if (!response.ok || !url || !state) {
        sessionStorage.removeItem('vk_auth_mode');
        sessionStorage.removeItem('vk_auth_state');
        setError('vk', data?.error || 'Не удалось получить URL авторизации VK');
        setActionLoading(null);
        return;
      }

      sessionStorage.setItem('vk_auth_state', state);
      sessionStorage.setItem('vk_auth_mode', 'link');

      const width = 600;
      const height = 700;
      const left = Math.round(window.screenX + (window.outerWidth - width) / 2);
      const top = Math.round(window.screenY + (window.outerHeight - height) / 2);
      const popup = window.open(
        url,
        'vk_link',
        `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`
      );

      if (!popup) {
        window.location.href = url;
        return;
      }

      const onMessage = async (event: MessageEvent) => {
        if (event.origin !== window.location.origin || !event.data || typeof event.data !== 'object') {
          return;
        }
        if ((event.data as { type?: string }).type === 'VK_AUTH_ERROR') {
          clearPopupHandlers();
          popup.close();
          sessionStorage.removeItem('vk_auth_mode');
          sessionStorage.removeItem('vk_auth_state');
          setActionLoading(null);
          setError('vk', 'Авторизация VK отменена или завершилась ошибкой');
          return;
        }
        if ((event.data as { type?: string }).type !== 'VK_AUTH_SUCCESS') {
          return;
        }

        clearPopupHandlers();
        popup.close();

        const code = ((event.data as { code?: string }).code || '').trim();
        const returnedState = ((event.data as { state?: string }).state || '').trim();
        const deviceId = ((event.data as { deviceId?: string }).deviceId || '').trim();
        const savedState = (sessionStorage.getItem('vk_auth_state') || '').trim();
        const finalState = returnedState || savedState;

        const linkResponse = await fetch(buildUrl('/auth/social/link/vk'), {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, state: finalState, device_id: deviceId, redirect_uri: VK_REDIRECT_URI }),
        });

        const linkData = await linkResponse.json().catch(() => ({}));
        sessionStorage.removeItem('vk_auth_mode');
        sessionStorage.removeItem('vk_auth_state');
        if (linkResponse.ok && linkData?.linked) {
          await fetchAccounts();
        } else {
          setError('vk', linkData?.error || 'Ошибка привязки VK');
        }
        setActionLoading(null);
      };

      messageHandlerRef.current = onMessage;
      window.addEventListener('message', onMessage);

      closeTimerRef.current = window.setInterval(() => {
        if (popup.closed) {
          clearPopupHandlers();
          sessionStorage.removeItem('vk_auth_mode');
          sessionStorage.removeItem('vk_auth_state');
          setActionLoading(null);
        }
      }, 500);
    } catch {
      sessionStorage.removeItem('vk_auth_mode');
      sessionStorage.removeItem('vk_auth_state');
      setError('vk', 'Ошибка запуска привязки VK');
      setActionLoading(null);
    }
  };

  const handleLinkTelegram = async (telegramPayload: Record<string, unknown>) => {
    if (!hasApiUrl) {
      setError('telegram', 'NEXT_PUBLIC_API_URL не задан');
      return;
    }

    setActionLoading('telegram');
    clearError('telegram');
    setShowTgWidget(false);
    try {
      const response = await fetch(buildUrl('/auth/social/link/telegram'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(telegramPayload),
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok && data?.linked) {
        await fetchAccounts();
      } else {
        setError('telegram', data?.error || 'Ошибка привязки Telegram');
      }
    } catch {
      setError('telegram', 'Ошибка соединения');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        {PROVIDERS.map((provider) => (
          <div key={provider.id} className="h-[72px] animate-pulse rounded-xl border bg-muted/40" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {PROVIDERS.map((provider) => {
        const account = findLinked(provider.id);
        const isLoading = actionLoading === provider.id;
        const error = errors[provider.id];
        const displayName = account
          ? [account.extra_data.first_name, account.extra_data.last_name].filter(Boolean).join(' ') ||
            account.extra_data.username ||
            account.extra_data.screen_name ||
            account.provider_id
          : null;

        return (
          <div key={provider.id} className="space-y-1">
            <div className="flex items-center justify-between rounded-xl border bg-background p-4">
              <div className="flex items-center gap-3">
                <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${provider.bgClass}`}>
                  {provider.icon}
                </span>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{provider.label}</span>
                    {account && (
                      <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
                        Привязан
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {account ? (
                      <>
                        {account.extra_data.photo_url && (
                          <Image
                            src={account.extra_data.photo_url}
                            alt=""
                            width={16}
                            height={16}
                            className="rounded-full"
                            unoptimized
                          />
                        )}
                        {displayName}
                      </>
                    ) : (
                      provider.description
                    )}
                  </div>
                </div>
              </div>

              <div>
                {account ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    onClick={() => handleUnlink(provider.id)}
                    disabled={isLoading}
                  >
                    {isLoading ? '...' : 'Отвязать'}
                  </Button>
                ) : provider.id === 'vk' ? (
                  <Button size="sm" variant="outline" onClick={handleLinkVk} disabled={isLoading}>
                    {isLoading ? '...' : 'Привязать'}
                  </Button>
                ) : (
                  <Button size="sm" variant="outline" onClick={() => setShowTgWidget((value) => !value)} disabled={isLoading}>
                    {isLoading ? '...' : 'Привязать'}
                  </Button>
                )}
              </div>
            </div>

            {provider.id === 'telegram' && !account && showTgWidget && (
              <div className="rounded-xl border bg-muted/30 p-4">
                {botUsername ? (
                  <TelegramAuthButton
                    botUsername={botUsername}
                    onAuthCallback={handleLinkTelegram}
                    buttonSize="medium"
                    cornerRadius={8}
                    showAvatar={false}
                    lang="ru"
                  />
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Укажите <code>NEXT_PUBLIC_TELEGRAM_BOT_USERNAME</code> в .env
                  </p>
                )}
              </div>
            )}

            {error && <p className="px-1 text-xs text-destructive">{error}</p>}
          </div>
        );
      })}
    </div>
  );
}
