'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
const VK_REDIRECT_URI =
  process.env.NEXT_PUBLIC_VK_AUTH_REDIRECT_URI ??
  (typeof window !== 'undefined' ? `${window.location.origin}/auth/vk/callback` : '');
const buildUrl = (path: string) => `${API_URL}${path}`;

type VkAuthPayload = {
  user?: {
    vkId?: string;
  };
  linked?: boolean;
  error?: string;
};

const parseResponse = async (response: Response) => {
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

export default function VkCallbackPage() {
  return (
    <Suspense fallback={<VkCallbackLoading statusText="Авторизация ВКонтакте..." />}>
      <VkCallbackContent />
    </Suspense>
  );
}

function VkCallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [statusText, setStatusText] = useState('Авторизация ВКонтакте...');

  useEffect(() => {
    const mode = (sessionStorage.getItem('vk_auth_mode') || 'login').trim() === 'link' ? 'link' : 'login';
    const isLinkMode = mode === 'link';

    const clearState = () => {
      sessionStorage.removeItem('vk_auth_state');
      sessionStorage.removeItem('vk_auth_mode');
    };

    const resolveErrorRoute = (code: string) =>
      isLinkMode ? `/settings?tab=social&error=${code}` : `/login?error=${code}`;

    const resolveSuccessRoute = () => (isLinkMode ? '/settings?tab=social&linked=vk' : '/welcome');

    const code = (params.get('code') || '').trim();
    const state = (params.get('state') || '').trim();
    const error = (params.get('error') || '').trim();

    if (error) {
      setStatusText(isLinkMode ? 'Привязка VK отменена' : 'Авторизация отменена');
      if (window.opener) {
        window.opener.postMessage({ type: 'VK_AUTH_ERROR', error }, window.location.origin);
        window.close();
      } else {
        clearState();
        router.replace(resolveErrorRoute('vk_cancelled'));
      }
      return;
    }

    if (!code) {
      setStatusText('Ошибка: VK не вернул код авторизации');
      if (window.opener) {
        window.opener.postMessage({ type: 'VK_AUTH_ERROR', error: 'no_code' }, window.location.origin);
        window.close();
      } else {
        clearState();
        router.replace(resolveErrorRoute('vk_no_code'));
      }
      return;
    }

    if (window.opener) {
      window.opener.postMessage({ type: 'VK_AUTH_SUCCESS', code, state }, window.location.origin);
      window.close();
      return;
    }

    if (!API_URL) {
      setStatusText('Ошибка: NEXT_PUBLIC_API_URL не задан');
      clearState();
      setTimeout(() => router.replace(isLinkMode ? '/settings?tab=social' : '/login'), 2000);
      return;
    }

    const savedState = (sessionStorage.getItem('vk_auth_state') || '').trim();
    const resolvedState = state || savedState;
    if (!resolvedState) {
      setStatusText('Ошибка: state не найден');
      clearState();
      setTimeout(() => router.replace(resolveErrorRoute('vk_state_missing')), 2000);
      return;
    }

    fetch(buildUrl(isLinkMode ? '/auth/social/link/vk' : '/auth/vk'), {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code,
        state: resolvedState,
        redirect_uri: VK_REDIRECT_URI
      })
    })
      .then(async (response) => ({ response, ...(await parseResponse(response)) }))
      .then(({ response, payload, text }) => {
        const success = isLinkMode ? Boolean(payload?.linked) : Boolean(payload?.user?.vkId);
        if (response.ok && success) {
          clearState();
          router.replace(resolveSuccessRoute());
          return;
        }
        setStatusText(payload?.error || text || 'Ошибка авторизации');
        clearState();
        setTimeout(() => router.replace(resolveErrorRoute(isLinkMode ? 'vk_link_failed' : 'vk_failed')), 2000);
      })
      .catch(() => {
        setStatusText('Ошибка соединения с сервером');
        clearState();
        setTimeout(() => router.replace(isLinkMode ? '/settings?tab=social' : '/login'), 2000);
      });
  }, [params, router]);

  return <VkCallbackLoading statusText={statusText} />;
}

function VkCallbackLoading({ statusText }: { statusText: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-white">
      <div className="space-y-4 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[#0077FF]/10">
          <svg className="h-6 w-6 animate-spin text-[#0077FF]" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
        </div>
        <p className="text-sm text-muted-foreground">{statusText}</p>
      </div>
    </div>
  );
}
