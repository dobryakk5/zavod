import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  push: vi.fn(),
  router: { push: vi.fn() },
  widgetPayload: {
    id: 777,
    first_name: 'Widget',
    username: 'widget_user',
    auth_date: '1700000000',
    hash: 'mock-hash',
  },
}));

vi.mock('next/navigation', () => ({
  useRouter: () => testState.router,
}));

vi.mock('next/image', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ alt, ...props }: any) => ReactModule.createElement('img', { alt, ...props }),
  };
});

vi.mock('@/components/auth/TelegramAuthButton', async () => {
  const ReactModule = await import('react');
  return {
    TelegramAuthButton: ({ botUsername, onAuthCallback }: any) =>
      ReactModule.createElement(
        'button',
        {
          type: 'button',
          'data-testid': 'mock-telegram-auth-button',
          'data-bot-username': botUsername,
          onClick: () => onAuthCallback(testState.widgetPayload),
        },
        'Mock Telegram Widget'
      ),
  };
});

type MockResponseInit = {
  ok: boolean;
  body?: unknown;
  text?: string;
};

const makeResponse = ({ ok, body, text }: MockResponseInit): Response =>
  ({
    ok,
    text: vi.fn().mockResolvedValue(text ?? (body === undefined ? '' : JSON.stringify(body))),
  }) as unknown as Response;

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalBotUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
const originalDevMode = process.env.NEXT_PUBLIC_DEV_MODE;

describe('TelegramAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.router.push = testState.push;
    vi.stubGlobal('fetch', vi.fn());
    process.env.NEXT_PUBLIC_API_URL = 'https://api.example.com';
    process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME = 'solarlab_bot';
    delete process.env.NEXT_PUBLIC_DEV_MODE;
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.resetModules();

    if (originalApiUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalApiUrl;

    if (originalBotUsername === undefined) delete process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
    else process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME = originalBotUsername;

    if (originalDevMode === undefined) delete process.env.NEXT_PUBLIC_DEV_MODE;
    else process.env.NEXT_PUBLIC_DEV_MODE = originalDevMode;
  });

  const loadComponent = async () => {
    const mod = await import('@/components/auth/TelegramAuth');
    return mod.TelegramAuth;
  };

  const getFetchMock = () => global.fetch as unknown as ReturnType<typeof vi.fn>;

  it('shows API configuration error when NEXT_PUBLIC_API_URL is missing', async () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    const TelegramAuth = await loadComponent();

    render(<TelegramAuth open onClose={vi.fn()} />);

    expect(await screen.findByText(/NEXT_PUBLIC_API_URL не задан/i)).toBeInTheDocument();
    expect(getFetchMock()).not.toHaveBeenCalled();
  });

  it('checks existing auth on open and redirects authenticated user', async () => {
    const fetchMock = getFetchMock();
    fetchMock.mockResolvedValueOnce(
      makeResponse({
        ok: true,
        body: {
          user: {
            telegramId: '42',
            firstName: 'Иван',
            lastName: 'Иванов',
            username: 'ivan',
            authDate: '2026-02-25T00:00:00Z',
          },
        },
      })
    );

    const TelegramAuth = await loadComponent();
    const onClose = vi.fn();
    render(<TelegramAuth open onClose={onClose} redirectTo="/dashboard" />);

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(testState.push).toHaveBeenCalledWith('/dashboard');
    });

    expect(fetchMock).toHaveBeenCalledWith('https://api.example.com/auth/telegram', {
      credentials: 'include',
    });
  });

  it('sends telegram widget payload to backend and redirects on successful login', async () => {
    const fetchMock = getFetchMock();
    fetchMock
      .mockResolvedValueOnce(makeResponse({ ok: false, text: '' })) // initial checkAuth
      .mockResolvedValueOnce(
        makeResponse({
          ok: true,
          body: {
            user: {
              telegramId: '77',
              firstName: 'Widget',
              username: 'widget_user',
              authDate: '2026-02-25T00:00:00Z',
            },
          },
        })
      );

    const TelegramAuth = await loadComponent();
    const onClose = vi.fn();
    render(<TelegramAuth open onClose={onClose} tenantId={99} />);

    const widgetButton = await screen.findByTestId('mock-telegram-auth-button');
    expect(widgetButton).toHaveAttribute('data-bot-username', 'solarlab_bot');

    fireEvent.click(widgetButton);

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(testState.push).toHaveBeenCalledWith('/dashboard');
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://api.example.com/auth/telegram',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const secondCall = fetchMock.mock.calls[1];
    const body = JSON.parse(secondCall?.[1]?.body as string);
    expect(body).toMatchObject({
      ...testState.widgetPayload,
      tenant_id: 99,
    });
  });

  it('shows backend error message when login request fails', async () => {
    const fetchMock = getFetchMock();
    fetchMock
      .mockResolvedValueOnce(makeResponse({ ok: false, text: '' }))
      .mockResolvedValueOnce(
        makeResponse({
          ok: false,
          body: { error: 'Неверная подпись Telegram' },
        })
      );

    const TelegramAuth = await loadComponent();
    const onClose = vi.fn();
    render(<TelegramAuth open onClose={onClose} />);

    fireEvent.click(await screen.findByTestId('mock-telegram-auth-button'));

    expect(await screen.findByText('Неверная подпись Telegram')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(testState.push).not.toHaveBeenCalled();
  });

  it('does not redirect when authenticated user is bound to another tenant', async () => {
    const fetchMock = getFetchMock();
    fetchMock.mockResolvedValueOnce(
      makeResponse({
        ok: true,
        body: {
          user: {
            telegramId: '42',
            firstName: 'Иван',
            username: 'ivan',
            authDate: '2026-02-25T00:00:00Z',
            tenantId: 100,
            contactId: 15,
          },
        },
      })
    );

    const TelegramAuth = await loadComponent();
    const onClose = vi.fn();
    render(<TelegramAuth open onClose={onClose} tenantId={99} />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    expect(onClose).not.toHaveBeenCalled();
    expect(testState.push).not.toHaveBeenCalled();
    expect(screen.getByTestId('mock-telegram-auth-button')).toBeInTheDocument();
    expect(screen.getByText(/После авторизации произойдет вход в кабинет/i)).toBeInTheDocument();
  });

  it('allows logout after authenticated state is loaded', async () => {
    const fetchMock = getFetchMock();
    fetchMock
      .mockResolvedValueOnce(
        makeResponse({
          ok: true,
          body: {
            user: {
              telegramId: '55',
              firstName: 'Петр',
              lastName: 'Петров',
              username: 'petr',
              authDate: '2026-02-25T00:00:00Z',
            },
          },
        })
      )
      .mockResolvedValueOnce(makeResponse({ ok: true, body: {} }));

    const TelegramAuth = await loadComponent();
    const onClose = vi.fn();
    render(<TelegramAuth open onClose={onClose} />);

    const logoutButton = await screen.findByRole('button', { name: 'Выйти' });
    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(testState.push).toHaveBeenCalledWith('/dashboard');
    });

    onClose.mockClear();
    testState.push.mockClear();

    fireEvent.click(logoutButton);

    expect(await screen.findByText('Вы вышли из аккаунта')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(testState.push).toHaveBeenCalledWith('/login');
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://api.example.com/auth/telegram',
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'include',
      })
    );
  });

  it('shows dev mode action and performs dev login', async () => {
    process.env.NEXT_PUBLIC_DEV_MODE = 'true';
    const fetchMock = getFetchMock();
    fetchMock
      .mockResolvedValueOnce(makeResponse({ ok: false, text: '' })) // initial checkAuth
      .mockResolvedValueOnce(
        makeResponse({
          ok: true,
          body: {
            user: {
              telegramId: '999',
              firstName: 'Dev',
              lastName: 'User',
              authDate: '2026-02-25T00:00:00Z',
              isDev: true,
            },
          },
        })
      );

    const TelegramAuth = await loadComponent();
    const onClose = vi.fn();
    render(<TelegramAuth open onClose={onClose} />);

    const devButton = await screen.findByRole('button', { name: 'Войти как Dev User' });
    fireEvent.click(devButton);

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(testState.push).toHaveBeenCalledWith('/dashboard');
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://api.example.com/auth/telegram',
      expect.objectContaining({
        method: 'PUT',
        credentials: 'include',
      })
    );
  });
});
