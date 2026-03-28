'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { DEFAULT_AUTH_REDIRECT } from '@/lib/routes';

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
const hasApiUrl = Boolean(API_URL);
const buildUrl = (path: string) => `${API_URL}${path}`;
const EMAIL_AUTH_REDIRECT_KEY = 'email_auth_redirect';

export default function EmailVerifyPage() {
  return (
    <Suspense fallback={<VerifyStatus text="Проверяем ссылку..." />}>
      <EmailVerifyContent />
    </Suspense>
  );
}

function EmailVerifyContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [statusText, setStatusText] = useState('Проверяем ссылку...');
  const [isError, setIsError] = useState(false);

  useEffect(() => {
    const token = (params.get('token') || '').trim();

    if (!token) {
      setStatusText('Ссылка недействительна.');
      setIsError(true);
      setTimeout(() => router.replace('/login'), 2500);
      return;
    }

    if (!hasApiUrl) {
      setStatusText('Ошибка: NEXT_PUBLIC_API_URL не задан');
      setIsError(true);
      setTimeout(() => router.replace('/login'), 2500);
      return;
    }

    fetch(buildUrl('/auth/email/verify-magic-link'), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
      .then(async (response) => {
        if (response.ok) {
          setStatusText('Вход выполнен. Перенаправляем...');
          const redirectTo = (sessionStorage.getItem(EMAIL_AUTH_REDIRECT_KEY) || '').trim();
          sessionStorage.removeItem(EMAIL_AUTH_REDIRECT_KEY);
          router.replace(redirectTo.startsWith('/') ? redirectTo : DEFAULT_AUTH_REDIRECT);
          return;
        }

        const data = await response.json().catch(() => ({}));
        setStatusText(data.detail || 'Ссылка недействительна или устарела.');
        setIsError(true);
        setTimeout(() => router.replace('/login'), 3000);
      })
      .catch(() => {
        setStatusText('Ошибка соединения с сервером.');
        setIsError(true);
        setTimeout(() => router.replace('/login'), 3000);
      });
  }, [params, router]);

  return <VerifyStatus text={statusText} isError={isError} />;
}

function VerifyStatus({ text, isError = false }: { text: string; isError?: boolean }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
      <div className="space-y-4 text-center">
        <div className={`mx-auto flex h-12 w-12 items-center justify-center rounded-full ${isError ? 'bg-destructive/10' : 'bg-primary/10'}`}>
          {isError ? (
            <svg className="h-6 w-6 text-destructive" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <path d="M15 9l-6 6M9 9l6 6" />
            </svg>
          ) : (
            <svg className="h-6 w-6 animate-spin text-primary" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
            </svg>
          )}
        </div>
        <p className="text-sm text-muted-foreground">{text}</p>
      </div>
    </div>
  );
}
