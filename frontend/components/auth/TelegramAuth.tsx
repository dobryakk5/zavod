'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { TelegramAuthButton } from './TelegramAuthButton';
import { Button } from '@/components/ui/button';

interface TelegramUser {
  telegramId: string;
  firstName: string;
  lastName?: string;
  username?: string;
  photoUrl?: string;
  authDate: string;
  isDev?: boolean;
}

interface TelegramAuthProps {
  open: boolean;
  onClose: () => void;
}

type TelegramAuthPayload = {
  user?: TelegramUser;
  error?: string;
};

type Status = {
  type: 'success' | 'error';
  text: string;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
const hasApiUrl = Boolean(API_URL);
const buildUrl = (path: string) => `${API_URL}${path}`;

const API_MISSING_MESSAGE = 'NEXT_PUBLIC_API_URL не задан — настроите URL бэкенда в .env';

const parseTelegramResponse = async (response: Response) => {
  const text = await response.text();
  if (!text) {
    return { payload: null as TelegramAuthPayload | null, text: '' };
  }
  try {
    return { payload: JSON.parse(text) as TelegramAuthPayload, text };
  } catch (error) {
    console.warn('Failed to parse Telegram auth response', text);
    return { payload: null as TelegramAuthPayload | null, text };
  }
};

const resolveErrorMessage = (payload: TelegramAuthPayload | null, rawText: string, fallback: string) =>
  payload?.error?.trim() || rawText.trim() || fallback;

export function TelegramAuth({ open, onClose }: TelegramAuthProps) {
  const router = useRouter();
  const [user, setUser] = useState<TelegramUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const ensureApiConfigured = () => {
    if (!hasApiUrl) {
      setStatus({ type: 'error', text: API_MISSING_MESSAGE });
      return false;
    }
    return true;
  };

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
  }, [open, router]);

  const checkAuth = async () => {
    if (!ensureApiConfigured()) {
      return;
    }
    try {
      const response = await fetch(buildUrl('/api/auth/telegram'), {
        credentials: 'include'
      });
      if (response.ok) {
        const { payload } = await parseTelegramResponse(response);
        if (payload?.user) {
          setUser(payload.user);
          onClose();
          router.push('/dashboard');
        }
      }
    } catch (error) {
      console.error('Error checking auth:', error);
    }
  };

  const handleTelegramResponse = async (response: any) => {
    if (!ensureApiConfigured()) {
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      const authResponse = await fetch(buildUrl('/api/auth/telegram'), {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(response)
      });

      const { payload, text } = await parseTelegramResponse(authResponse);

      if (authResponse.ok && payload?.user) {
        setUser(payload.user);
        setStatus({ type: 'success', text: 'Успешная авторизация!' });
        onClose();
        router.push('/dashboard');
      } else {
        setStatus({ type: 'error', text: resolveErrorMessage(payload, text, 'Ошибка авторизации') });
      }
    } catch (error) {
      console.error('Auth error:', error);
      setStatus({ type: 'error', text: 'Ошибка авторизации' });
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    if (!ensureApiConfigured()) {
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      const response = await fetch(buildUrl('/api/auth/telegram'), {
        method: 'DELETE',
        credentials: 'include'
      });

      if (response.ok) {
        setUser(null);
        setStatus({ type: 'success', text: 'Вы вышли из аккаунта' });
      } else {
        setStatus({ type: 'error', text: 'Ошибка при выходе' });
      }
    } catch (error) {
      console.error('Logout error:', error);
      setStatus({ type: 'error', text: 'Ошибка при выходе' });
    } finally {
      setLoading(false);
    }
  };

  const handleDevLogin = async () => {
    if (!ensureApiConfigured()) {
      return;
    }
    setLoading(true);
    setStatus(null);
    try {
      const response = await fetch(buildUrl('/api/auth/telegram'), {
        method: 'PUT',
        credentials: 'include'
      });

      const { payload, text } = await parseTelegramResponse(response);

      if (response.ok && payload?.user) {
        setUser(payload.user);
        setStatus({ type: 'success', text: 'Dev режим активирован!' });
        onClose();
        router.push('/dashboard');
      } else {
        setStatus({ type: 'error', text: resolveErrorMessage(payload, text, 'Ошибка dev авторизации') });
      }
    } catch (error) {
      console.error('Dev auth error:', error);
      setStatus({ type: 'error', text: 'Ошибка dev авторизации' });
    } finally {
      setLoading(false);
    }
  };

  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
  const isDevMode = process.env.NEXT_PUBLIC_DEV_MODE === 'true';

  if (!open) {
    return null;
  }

  const renderInitials = () => {
    if (!user) {
      return '';
    }
    const first = user.firstName?.[0] ?? '';
    const last = user.lastName?.[0] ?? '';
    return (first + last).toUpperCase() || user.username?.[0]?.toUpperCase() || 'S';
  };

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
            <p className="text-sm text-muted-foreground">Войдите через Telegram, чтобы продолжить</p>
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
                {user.isDev && (
                  <span className="mb-3 inline-flex rounded-full bg-orange-100 px-3 py-1 text-xs font-semibold text-orange-700">
                    DEV MODE
                  </span>
                )}
                <div className="mx-auto mb-3 flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-primary/10 text-2xl font-semibold text-primary">
                  {user.photoUrl ? (
                    <img src={user.photoUrl} alt={user.firstName} className="h-full w-full object-cover" />
                  ) : (
                    renderInitials()
                  )}
                </div>
                <div className="text-lg font-semibold">
                  {user.firstName} {user.lastName ?? ''}
                </div>
                {user.username && <div className="text-sm text-muted-foreground">@{user.username}</div>}
                <div className="mt-2 text-xs text-muted-foreground">Telegram ID: {user.telegramId}</div>
              </div>
              <Button variant="outline" className="w-full" onClick={handleLogout} disabled={loading}>
                Выйти
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">Наш бот запросит доступ к вашему профилю и вернет вас в кабинет.</p>
              {botUsername ? (
                <TelegramAuthButton
                  botUsername={botUsername}
                  onAuthCallback={handleTelegramResponse}
                  buttonSize="large"
                  cornerRadius={8}
                  showAvatar={false}
                  lang="ru"
                />
              ) : (
                <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-900">
                  Укажите <span className="font-semibold">NEXT_PUBLIC_TELEGRAM_BOT_USERNAME</span> в `.env` для подключения бота.
                </div>
              )}
              {isDevMode && (
                <div className="rounded-lg border border-dashed border-muted p-4">
                  <div className="mb-2 text-xs uppercase text-muted-foreground">Режим разработки</div>
                  <Button variant="outline" className="w-full" onClick={handleDevLogin} disabled={loading}>
                    Войти как Dev User
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
