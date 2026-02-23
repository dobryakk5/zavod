'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Image from 'next/image';
import { Button } from '@/components/ui/button';

interface VkUser {
  vkId: string;
  firstName: string;
  lastName?: string;
  username?: string;
  photoUrl?: string;
  authDate: string;
}

interface VKAuthProps {
  open: boolean;
  onClose: () => void;
}

type VkAuthPayload = {
  user?: VkUser;
  error?: string;
};

type Status = {
  type: 'success' | 'error';
  text: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
const hasApiUrl = Boolean(API_URL);
const buildUrl = (path: string) => `${API_URL}${path}`;
const VK_REDIRECT_URI =
  process.env.NEXT_PUBLIC_VK_AUTH_REDIRECT_URI ??
  (typeof window !== 'undefined' ? `${window.location.origin}/auth/vk/callback` : '');
const API_MISSING_MESSAGE = 'NEXT_PUBLIC_API_URL не задан — настроите URL бэкенда в .env';
type VkBridgeWindow = { vkBridge?: { send?: Function } };

const isVkMiniApp = () =>
  typeof window !== 'undefined' &&
  typeof (window as unknown as VkBridgeWindow).vkBridge?.send === 'function';

const parseVkResponse = async (response: Response) => {
  const text = await response.text();
  if (!text) {
    return { payload: null as VkAuthPayload | null, text: '' };
  }
  try {
    return { payload: JSON.parse(text) as VkAuthPayload, text };
  } catch {
    return { payload: null as VkAuthPayload | null, text };
  }
};

const resolveErrorMessage = (payload: VkAuthPayload | null, rawText: string, fallback: string) =>
  payload?.error?.trim() || rawText.trim() || fallback;

export function VKAuth({ open, onClose }: VKAuthProps) {
  const router = useRouter();
  const [user, setUser] = useState<VkUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const closeTimerRef = useRef<number | null>(null);
  const messageHandlerRef = useRef<((event: MessageEvent) => void) | null>(null);

  const cleanupPopupFlow = useCallback(() => {
    if (closeTimerRef.current !== null) {
      window.clearInterval(closeTimerRef.current);
      closeTimerRef.current = null;
    }
    if (messageHandlerRef.current) {
      window.removeEventListener('message', messageHandlerRef.current);
      messageHandlerRef.current = null;
    }
  }, []);

  const ensureApiConfigured = useCallback(() => {
    if (!hasApiUrl) {
      setStatus({ type: 'error', text: API_MISSING_MESSAGE });
      return false;
    }
    return true;
  }, []);

  const exchangeCode = useCallback(
    async (code: string, state: string) => {
      if (!ensureApiConfigured()) {
        return;
      }
      if (!code) {
        setStatus({ type: 'error', text: 'VK не вернул код авторизации' });
        return;
      }

      setLoading(true);
      setStatus(null);
      try {
        const response = await fetch(buildUrl('/auth/vk'), {
          method: 'POST',
          credentials: 'include',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            code,
            state,
            redirect_uri: VK_REDIRECT_URI
          })
        });
        const { payload, text } = await parseVkResponse(response);
        if (response.ok && payload?.user) {
          setUser(payload.user);
          setStatus({ type: 'success', text: 'Успешная авторизация!' });
          sessionStorage.removeItem('vk_auth_state');
          sessionStorage.removeItem('vk_auth_mode');
          onClose();
          router.push('/welcome');
        } else {
          setStatus({ type: 'error', text: resolveErrorMessage(payload, text, 'Ошибка авторизации VK') });
        }
      } catch {
        setStatus({ type: 'error', text: 'Ошибка авторизации VK' });
      } finally {
        setLoading(false);
      }
    },
    [ensureApiConfigured, onClose, router]
  );

  const handleVkBridgeLogin = useCallback(async () => {
    if (!ensureApiConfigured()) {
      return;
    }

    const appId = Number.parseInt(process.env.NEXT_PUBLIC_VK_APP_ID ?? '', 10);
    if (!Number.isFinite(appId) || appId <= 0) {
      setStatus({ type: 'error', text: 'NEXT_PUBLIC_VK_APP_ID не задан' });
      return;
    }

    setLoading(true);
    setStatus(null);

    try {
      const bridge = (window as unknown as { vkBridge: { send: Function } }).vkBridge;
      const result = (await bridge.send('VKWebAppGetAuthToken', {
        app_id: appId,
        scope: ''
      })) as { access_token?: string; user_id?: number | string };

      const accessToken = (result.access_token || '').trim();
      const userId = result.user_id;
      if (!accessToken || !userId) {
        setStatus({ type: 'error', text: 'VK Bridge не вернул токен' });
        return;
      }

      const response = await fetch(buildUrl('/auth/vk/bridge'), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ access_token: accessToken, user_id: userId })
      });

      const { payload, text } = await parseVkResponse(response);
      if (response.ok && payload?.user) {
        setUser(payload.user);
        setStatus({ type: 'success', text: 'Успешная авторизация!' });
        onClose();
        router.push('/welcome');
      } else {
        setStatus({ type: 'error', text: resolveErrorMessage(payload, text, 'Ошибка авторизации VK') });
      }
    } catch (error: unknown) {
      const bridgeError = error as { error_data?: { error_message?: string } };
      setStatus({ type: 'error', text: bridgeError?.error_data?.error_message || 'Ошибка VK Bridge' });
    } finally {
      setLoading(false);
    }
  }, [ensureApiConfigured, onClose, router]);

  const checkAuth = useCallback(async () => {
    if (!ensureApiConfigured()) {
      return;
    }
    try {
      const response = await fetch(buildUrl('/auth/vk'), { credentials: 'include' });
      if (!response.ok) {
        return;
      }
      const { payload } = await parseVkResponse(response);
      if (payload?.user) {
        setUser(payload.user);
        onClose();
        router.push('/welcome');
      }
    } catch {
      // no-op
    }
  }, [ensureApiConfigured, onClose, router]);

  useEffect(() => {
    if (open) {
      if (!hasApiUrl) {
        setStatus({ type: 'error', text: API_MISSING_MESSAGE });
        return;
      }
      void checkAuth();
    } else {
      setStatus(null);
    }
  }, [checkAuth, open]);

  useEffect(() => () => cleanupPopupFlow(), [cleanupPopupFlow]);

  const handleVkWebLogin = useCallback(async () => {
    if (!ensureApiConfigured()) {
      return;
    }

    setLoading(true);
    setStatus(null);
    cleanupPopupFlow();

    try {
      const response = await fetch(buildUrl('/auth/vk/url'), { credentials: 'include' });
      const { payload, text } = await parseVkResponse(response);
      const fallbackError = response.status === 503 ? 'VK auth не настроен на сервере' : 'Ошибка запуска авторизации VK';
      const authUrl = (payload as unknown as { url?: string })?.url;
      const authState = (payload as unknown as { state?: string })?.state;

      if (!response.ok || !authUrl || !authState) {
        setStatus({ type: 'error', text: resolveErrorMessage(payload, text, fallbackError) });
        setLoading(false);
        return;
      }

      sessionStorage.setItem('vk_auth_state', authState);
      sessionStorage.setItem('vk_auth_mode', 'login');

      const width = 600;
      const height = 700;
      const left = Math.round(window.screenX + (window.outerWidth - width) / 2);
      const top = Math.round(window.screenY + (window.outerHeight - height) / 2);

      const popup = window.open(
        authUrl,
        'vk_auth',
        `width=${width},height=${height},left=${left},top=${top},toolbar=no,menubar=no`
      );

      if (!popup) {
        window.location.href = authUrl;
        return;
      }

      const onMessage = async (event: MessageEvent) => {
        if (event.origin !== window.location.origin || !event.data || typeof event.data !== 'object') {
          return;
        }

        if ((event.data as { type?: string }).type === 'VK_AUTH_ERROR') {
          cleanupPopupFlow();
          popup.close();
          sessionStorage.removeItem('vk_auth_state');
          sessionStorage.removeItem('vk_auth_mode');
          setLoading(false);
          setStatus({ type: 'error', text: 'Авторизация VK отменена или завершилась ошибкой' });
          return;
        }

        if ((event.data as { type?: string }).type !== 'VK_AUTH_SUCCESS') {
          return;
        }

        cleanupPopupFlow();
        popup.close();
        const code = ((event.data as { code?: string }).code || '').trim();
        const returnedState = ((event.data as { state?: string }).state || '').trim();
        const savedState = (sessionStorage.getItem('vk_auth_state') || '').trim();
        const state = returnedState || savedState || authState;
        await exchangeCode(code, state);
      };

      messageHandlerRef.current = onMessage;
      window.addEventListener('message', onMessage);

      closeTimerRef.current = window.setInterval(() => {
        if (popup.closed) {
          cleanupPopupFlow();
          sessionStorage.removeItem('vk_auth_state');
          sessionStorage.removeItem('vk_auth_mode');
          setLoading(false);
        }
      }, 500);
    } catch {
      sessionStorage.removeItem('vk_auth_state');
      sessionStorage.removeItem('vk_auth_mode');
      setStatus({ type: 'error', text: 'Ошибка запуска авторизации VK' });
      setLoading(false);
    }
  }, [cleanupPopupFlow, ensureApiConfigured, exchangeCode]);

  const handleVkLogin = useCallback(async () => {
    if (isVkMiniApp()) {
      await handleVkBridgeLogin();
      return;
    }
    await handleVkWebLogin();
  }, [handleVkBridgeLogin, handleVkWebLogin]);

  const handleLogout = async () => {
    if (!ensureApiConfigured()) {
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      const response = await fetch(buildUrl('/auth/vk'), {
        method: 'DELETE',
        credentials: 'include'
      });
      if (response.ok) {
        setUser(null);
        setStatus({ type: 'success', text: 'Вы вышли из аккаунта' });
        router.push('/login');
      } else {
        setStatus({ type: 'error', text: 'Ошибка при выходе' });
      }
    } catch {
      setStatus({ type: 'error', text: 'Ошибка при выходе' });
    } finally {
      setLoading(false);
    }
  };

  const renderInitials = () => {
    if (!user) {
      return '';
    }
    const first = user.firstName?.[0] ?? '';
    const last = user.lastName?.[0] ?? '';
    return (first + last).toUpperCase() || user.username?.[0]?.toUpperCase() || 'V';
  };

  if (!open) {
    return null;
  }

  const handleOverlayClick = () => {
    if (!loading) {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4 py-6" onClick={handleOverlayClick}>
      <div className="relative w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(event) => event.stopPropagation()}>
        <button
          type="button"
          className="absolute right-4 top-4 text-sm text-muted-foreground hover:text-foreground"
          onClick={handleOverlayClick}
          aria-label="Закрыть окно авторизации"
        >
          ×
        </button>

        <div className="space-y-5">
          <div>
            <h2 className="text-xl font-semibold">Личный кабинет</h2>
            <p className="text-sm text-muted-foreground">Войдите через ВКонтакте, чтобы продолжить</p>
          </div>

          {status && (
            <div
              className={`rounded-md border px-3 py-2 text-sm ${
                status.type === 'success'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-red-200 bg-red-50 text-red-700'
              }`}
            >
              {status.text}
            </div>
          )}

          {user ? (
            <div className="space-y-4">
              <div className="text-center">
                <div className="mx-auto mb-3 flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-[#0077FF]/10 text-2xl font-semibold text-[#0077FF]">
                  {user.photoUrl ? (
                    <Image
                      src={user.photoUrl}
                      alt={user.firstName}
                      width={80}
                      height={80}
                      className="h-full w-full object-cover"
                      unoptimized
                    />
                  ) : (
                    renderInitials()
                  )}
                </div>
                <div className="text-lg font-semibold">
                  {user.firstName} {user.lastName ?? ''}
                </div>
                {user.username && <div className="text-sm text-muted-foreground">@{user.username}</div>}
                <div className="mt-2 text-xs text-muted-foreground">VK ID: {user.vkId}</div>
              </div>
              <Button variant="outline" className="w-full" onClick={handleLogout} disabled={loading}>
                Выйти
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">После авторизации произойдет вход в кабинет.</p>
              <button
                type="button"
                onClick={handleVkLogin}
                disabled={loading}
                className="flex w-full items-center justify-center gap-3 rounded-xl bg-[#0077FF] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#0066DD] disabled:opacity-50"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.744c-.66 0-.862-.523-2.049-1.727-1.033-1-1.49-1.135-1.744-1.135-.356 0-.458.102-.458.593v1.575c0 .424-.135.678-1.253.678-1.846 0-3.896-1.118-5.335-3.202C5.1 11.366 4.5 9.218 4.5 8.775c0-.254.102-.491.593-.491h1.744c.44 0 .61.203.78.677.863 2.49 2.303 4.675 2.896 4.675.22 0 .322-.102.322-.66V9.633c-.068-1.186-.695-1.287-.695-1.71 0-.204.17-.407.44-.407h2.744c.373 0 .508.203.508.643v3.473c0 .372.17.508.271.508.22 0 .407-.136.813-.542 1.254-1.406 2.151-3.574 2.151-3.574.119-.254.322-.491.763-.491h1.744c.525 0 .644.27.525.643-.22 1.017-2.354 4.031-2.354 4.031-.186.305-.254.44 0 .78.186.254.796.779 1.203 1.253.745.847 1.32 1.558 1.473 2.049.17.491-.085.745-.576.745z" />
                </svg>
                {loading ? 'Подождите...' : 'Войти через ВКонтакте'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
