'use client';

import { useCallback, useState } from 'react';
import { DEFAULT_AUTH_REDIRECT } from '@/lib/routes';

interface EmailAuthProps {
  open: boolean;
  onClose: () => void;
  redirectTo?: string;
}

type Stage = 'input' | 'sent';

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
const hasApiUrl = Boolean(API_URL);
const buildUrl = (path: string) => `${API_URL}${path}`;
const EMAIL_AUTH_REDIRECT_KEY = 'email_auth_redirect';
const API_MISSING_MESSAGE = 'NEXT_PUBLIC_API_URL не задан — настроите URL бэкенда в .env';

export function EmailAuth({ open, onClose, redirectTo }: EmailAuthProps) {
  const [stage, setStage] = useState<Stage>('input');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const resolvedRedirectTo = redirectTo && redirectTo.startsWith('/') ? redirectTo : DEFAULT_AUTH_REDIRECT;

  const handleClose = useCallback(() => {
    setStage('input');
    setEmail('');
    setError(null);
    setLoading(false);
    onClose();
  }, [onClose]);

  const sendMagicLink = useCallback(
    async (emailToSend: string) => {
      if (!hasApiUrl) {
        setError(API_MISSING_MESSAGE);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        sessionStorage.setItem(EMAIL_AUTH_REDIRECT_KEY, resolvedRedirectTo);

        const res = await fetch(buildUrl('/auth/email/send-magic-link'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email: emailToSend }),
        });

        const data = await res.json().catch(() => ({}));

        if (!res.ok) {
          setError(data.detail || 'Ошибка отправки письма. Попробуйте позже.');
          return;
        }

        setStage('sent');
      } catch {
        setError('Ошибка соединения с сервером.');
      } finally {
        setLoading(false);
      }
    },
    [resolvedRedirectTo]
  );

  const handleSubmit = useCallback(async () => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed || !trimmed.includes('@')) {
      setError('Укажите корректный email.');
      return;
    }
    await sendMagicLink(trimmed);
  }, [email, sendMagicLink]);

  const handleResend = useCallback(async () => {
    await sendMagicLink(email.trim().toLowerCase());
  }, [email, sendMagicLink]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      onClick={handleClose}
    >
      <div
        className="w-full max-w-sm rounded-2xl border bg-background p-6 shadow-lg"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Войти по email</h2>
          <button
            type="button"
            onClick={handleClose}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted"
            aria-label="Закрыть"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {stage === 'input' && (
          <>
            <p className="mb-4 text-sm text-muted-foreground">
              Введите email. Мы отправим ссылку для входа, пароль не нужен.
            </p>

            <div className="space-y-3">
              <input
                type="email"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setError(null);
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    void handleSubmit();
                  }
                }}
                placeholder="you@example.com"
                autoFocus
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
                disabled={loading}
              />

              {error && <p className="text-xs text-destructive">{error}</p>}

              <button
                type="button"
                onClick={() => void handleSubmit()}
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-60"
              >
                {loading ? (
                  <>
                    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                    </svg>
                    Отправляем...
                  </>
                ) : (
                  'Отправить ссылку'
                )}
              </button>
            </div>
          </>
        )}

        {stage === 'sent' && (
          <div className="space-y-4 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2" aria-hidden="true">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
            </div>

            <div>
              <p className="font-medium">Письмо отправлено</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Проверьте <span className="font-medium text-foreground">{email}</span>. Ссылка действует 15 минут.
              </p>
            </div>

            {error && <p className="text-xs text-destructive">{error}</p>}

            <div className="space-y-2">
              <button
                type="button"
                onClick={() => void handleResend()}
                disabled={loading}
                className="text-xs text-muted-foreground underline underline-offset-2 hover:text-foreground disabled:opacity-50"
              >
                {loading ? 'Отправляем...' : 'Отправить повторно'}
              </button>

              <button
                type="button"
                onClick={() => {
                  setStage('input');
                  setError(null);
                }}
                className="block w-full text-xs text-muted-foreground hover:text-foreground"
              >
                Изменить email
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
