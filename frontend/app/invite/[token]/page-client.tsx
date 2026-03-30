'use client';

import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ApiError, apiFetch } from '@/lib/api';

type InviteResolveResponse = {
  ok: boolean;
  clientId: number;
  clientName: string;
  coachName?: string;
};

export default function InvitePageClient({ token }: { token: string }) {
  const router = useRouter();
  const [state, setState] = useState<'loading' | 'error' | 'success'>('loading');
  const [errorMessage, setErrorMessage] = useState('');
  const [coachName, setCoachName] = useState('');
  const [clientName, setClientName] = useState('');

  useEffect(() => {
    const resolveInvite = async () => {
      try {
        const payload = await apiFetch<InviteResolveResponse>(`/auth/invite/${token}/`, {
          method: 'POST',
        });

        if (!payload.ok || !payload.clientId) {
          setErrorMessage('Ссылка недействительна.');
          setState('error');
          return;
        }

        setClientName(payload.clientName || '');
        setCoachName(payload.coachName || '');
        setState('success');

        await new Promise((resolve) => window.setTimeout(resolve, 1200));
        router.replace(`/c/${payload.clientId}/coaching`);
      } catch (error) {
        if (error instanceof ApiError && error.status === 410) {
          setErrorMessage('Ссылка уже была использована или устарела. Попросите коуча прислать новую.');
        } else if (error instanceof ApiError && error.status === 404) {
          setErrorMessage('Ссылка не найдена. Проверьте адрес или попросите коуча прислать новую.');
        } else {
          setErrorMessage('Не удалось войти. Попробуйте позже или обратитесь к коучу.');
        }
        setState('error');
      }
    };

    void resolveInvite();
  }, [router, token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f4f0] px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center text-[22px] font-medium text-[#1a1a18]">CoachSpace</div>

        {state === 'loading' ? (
          <StatusCard>
            <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-[#e0ddd6] border-t-[#1D9E75]" />
            <p className="text-[14px] font-medium text-[#1a1a18]">Входим в ваш кабинет...</p>
            <p className="mt-1 text-[12px] text-[#73726c]">Это займёт секунду</p>
          </StatusCard>
        ) : null}

        {state === 'success' ? (
          <StatusCard>
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#E1F5EE]">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M5 12l5 5L20 7" stroke="#1D9E75" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p className="text-[16px] font-medium text-[#1a1a18]">
              {clientName ? `Добро пожаловать, ${clientName.split(/\s+/)[0]}!` : 'Добро пожаловать!'}
            </p>
            {coachName ? (
              <p className="mt-1 text-[12px] text-[#73726c]">Ваш коуч: {coachName}</p>
            ) : null}
            <p className="mt-3 text-[12px] text-[#73726c]">Переходим в ваш кабинет...</p>
          </StatusCard>
        ) : null}

        {state === 'error' ? (
          <StatusCard>
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[#FAECE7]">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke="#993C1D" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </div>
            <p className="text-[14px] font-medium text-[#1a1a18]">Ссылка не работает</p>
            <p className="mt-2 text-[12px] leading-relaxed text-[#73726c]">{errorMessage}</p>
          </StatusCard>
        ) : null}
      </div>
    </div>
  );
}

function StatusCard({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-[12px] border-[0.5px] border-[#e0ddd6] bg-white p-8 text-center">
      {children}
    </div>
  );
}
