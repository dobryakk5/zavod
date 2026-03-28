'use client';

import { Suspense, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { TelegramAuth } from '@/components/auth/TelegramAuth';
import { VKAuth } from '@/components/auth/VKAuth';
import { EmailAuth } from '@/components/auth/EmailAuth';
import { DEFAULT_AUTH_REDIRECT } from '@/lib/routes';

export default function LoginPage() {
  return (
    <Suspense fallback={<LoginPageFallback />}>
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
      <div className="w-full max-w-lg rounded-2xl border bg-background p-8 text-center shadow">
        <p className="text-sm text-muted-foreground">Загрузка страницы входа...</p>
      </div>
    </div>
  );
}

function LoginPageContent() {
  const searchParams = useSearchParams();
  const [telegramOpen, setTelegramOpen] = useState(false);
  const [vkOpen, setVkOpen] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const nextParam = (searchParams.get('next') || '').trim();
  const redirectTo = nextParam.startsWith('/') ? nextParam : DEFAULT_AUTH_REDIRECT;
  const tenantIdParam = Number(searchParams.get('tenant_id') || 0);
  const contactTenantId = Number.isFinite(tenantIdParam) && tenantIdParam > 0 ? tenantIdParam : null;
  const isContactLoginMode = contactTenantId !== null;

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 px-4">
      <div className="w-full max-w-lg space-y-4 rounded-2xl border bg-background p-8 text-center shadow">
        <h1 className="text-2xl font-semibold">
          {isContactLoginMode ? 'Войти как контакт' : 'Войти в личный кабинет'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {isContactLoginMode
            ? 'Авторизация привяжет Telegram к странице клиента для записи и рефералов'
            : 'Выберите удобный способ авторизации'}
        </p>

        <div className="space-y-3 pt-2">
          <button
            type="button"
            onClick={() => setTelegramOpen(true)}
            className="flex w-full items-center gap-4 rounded-xl border bg-background px-4 py-3 text-left transition hover:bg-muted/50"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#0088cc]/10">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="#0088cc" aria-hidden="true">
                <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.17 13.967l-2.965-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.983.592z" />
              </svg>
            </span>
            <span className="flex-1">
              <span className="block text-sm font-medium">Войти через Telegram</span>
              <span className="block text-xs text-muted-foreground">Popup-вход через Telegram</span>
            </span>
            <svg className="h-4 w-4 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>

          <button
            type="button"
            onClick={() => setVkOpen(true)}
            className="flex w-full items-center gap-4 rounded-xl border bg-background px-4 py-3 text-left transition hover:bg-muted/50"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#0077FF]/10">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="#0077FF" aria-hidden="true">
                <path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.744c-.66 0-.862-.523-2.049-1.727-1.033-1-1.49-1.135-1.744-1.135-.356 0-.458.102-.458.593v1.575c0 .424-.135.678-1.253.678-1.846 0-3.896-1.118-5.335-3.202C5.1 11.366 4.5 9.218 4.5 8.775c0-.254.102-.491.593-.491h1.744c.44 0 .61.203.78.677.863 2.49 2.303 4.675 2.896 4.675.22 0 .322-.102.322-.66V9.633c-.068-1.186-.695-1.287-.695-1.71 0-.204.17-.407.44-.407h2.744c.373 0 .508.203.508.643v3.473c0 .372.17.508.271.508.22 0 .407-.136.813-.542 1.254-1.406 2.151-3.574 2.151-3.574.119-.254.322-.491.763-.491h1.744c.525 0 .644.27.525.643-.22 1.017-2.354 4.031-2.354 4.031-.186.305-.254.44 0 .78.186.254.796.779 1.203 1.253.745.847 1.32 1.558 1.473 2.049.17.491-.085.745-.576.745z" />
              </svg>
            </span>
            <span className="flex-1">
              <span className="block text-sm font-medium">Войти через ВКонтакте</span>
              <span className="block text-xs text-muted-foreground">Вход через аккаунт VK</span>
            </span>
            <svg className="h-4 w-4 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>

          {!isContactLoginMode && (
            <button
              type="button"
              onClick={() => setEmailOpen(true)}
              className="flex w-full items-center gap-4 rounded-xl border bg-background px-4 py-3 text-left transition hover:bg-muted/50"
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-muted">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                  <polyline points="22,6 12,13 2,6" />
                </svg>
              </span>
              <span className="flex-1">
                <span className="block text-sm font-medium">Войти по email</span>
                <span className="block text-xs text-muted-foreground">Ссылка для входа придёт на почту</span>
              </span>
              <svg className="h-4 w-4 text-muted-foreground" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M9 18l6-6-6-6" />
              </svg>
            </button>
          )}
        </div>

        <p className="pt-2 text-xs text-muted-foreground">
          Если у вас нет доступа, напишите в{' '}
          <a href="https://t.me/fibonatty_bot" className="underline underline-offset-2">
            @fibonatty_bot
          </a>
          , чтобы получить приглашение.
        </p>
      </div>

      <TelegramAuth
        open={telegramOpen}
        onClose={() => setTelegramOpen(false)}
        redirectTo={redirectTo}
        tenantId={contactTenantId}
      />
      <VKAuth
        open={vkOpen}
        onClose={() => setVkOpen(false)}
        redirectTo={redirectTo}
        tenantId={contactTenantId}
      />
      <EmailAuth
        open={emailOpen}
        onClose={() => setEmailOpen(false)}
        redirectTo={redirectTo}
      />
    </div>
  );
}
