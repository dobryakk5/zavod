import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  push: vi.fn(),
  router: { push: vi.fn() },
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

type MockResponseInit = {
  ok: boolean;
  status?: number;
  body?: unknown;
  text?: string;
};

const makeResponse = ({ ok, status = ok ? 200 : 400, body, text }: MockResponseInit): Response =>
  ({
    ok,
    status,
    text: vi.fn().mockResolvedValue(text ?? (body === undefined ? '' : JSON.stringify(body))),
  }) as unknown as Response;

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalVkRedirectUri = process.env.NEXT_PUBLIC_VK_AUTH_REDIRECT_URI;

describe('VKAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.router.push = testState.push;
    vi.stubGlobal('fetch', vi.fn());
    process.env.NEXT_PUBLIC_API_URL = 'https://api.example.com';
    process.env.NEXT_PUBLIC_VK_AUTH_REDIRECT_URI = 'https://frontend.example.com/auth/vk/callback';
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.resetModules();
    sessionStorage.clear();

    if (originalApiUrl === undefined) delete process.env.NEXT_PUBLIC_API_URL;
    else process.env.NEXT_PUBLIC_API_URL = originalApiUrl;

    if (originalVkRedirectUri === undefined) delete process.env.NEXT_PUBLIC_VK_AUTH_REDIRECT_URI;
    else process.env.NEXT_PUBLIC_VK_AUTH_REDIRECT_URI = originalVkRedirectUri;
  });

  const loadComponent = async () => {
    const mod = await import('@/components/auth/VKAuth');
    return mod.VKAuth;
  };

  const getFetchMock = () => global.fetch as unknown as ReturnType<typeof vi.fn>;

  it('shows API configuration error when NEXT_PUBLIC_API_URL is missing', async () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    const VKAuth = await loadComponent();

    render(<VKAuth open onClose={vi.fn()} />);

    expect(await screen.findByText(/NEXT_PUBLIC_API_URL не задан/i)).toBeInTheDocument();
    expect(getFetchMock()).not.toHaveBeenCalled();
  });

  it('starts VK popup flow and stores auth state in sessionStorage', async () => {
    const fetchMock = getFetchMock();
    fetchMock
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401, text: '' })) // initial checkAuth
      .mockResolvedValueOnce(
        makeResponse({
          ok: true,
          body: {
            url: 'https://id.vk.com/authorize?test=1',
            state: 'vk-state-1',
          },
        })
      );

    const popup = { closed: false, close: vi.fn() };
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => popup as any);

    const VKAuth = await loadComponent();
    render(<VKAuth open onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Войти через ВКонтакте' }));

    await waitFor(() => {
      expect(openSpy).toHaveBeenCalled();
    });

    expect(fetchMock).toHaveBeenNthCalledWith(2, 'https://api.example.com/auth/vk/url', {
      credentials: 'include',
    });
    expect(sessionStorage.getItem('vk_auth_state')).toBe('vk-state-1');
    expect(sessionStorage.getItem('vk_auth_mode')).toBe('login');
  });

  it('handles popup error message and clears auth state', async () => {
    const fetchMock = getFetchMock();
    fetchMock
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401, text: '' }))
      .mockResolvedValueOnce(
        makeResponse({
          ok: true,
          body: {
            url: 'https://id.vk.com/authorize?test=1',
            state: 'vk-state-err',
          },
        })
      );

    const popup = { closed: false, close: vi.fn() };
    vi.spyOn(window, 'open').mockImplementation(() => popup as any);

    const VKAuth = await loadComponent();
    render(<VKAuth open onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Войти через ВКонтакте' }));

    await waitFor(() => {
      expect(sessionStorage.getItem('vk_auth_state')).toBe('vk-state-err');
    });

    window.dispatchEvent(
      new MessageEvent('message', {
        origin: window.location.origin,
        data: { type: 'VK_AUTH_ERROR' },
      })
    );

    expect(await screen.findByText('Авторизация VK отменена или завершилась ошибкой')).toBeInTheDocument();
    expect(popup.close).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem('vk_auth_state')).toBeNull();
    expect(sessionStorage.getItem('vk_auth_mode')).toBeNull();
  });

  it('does not redirect when authenticated user is bound to another tenant', async () => {
    const fetchMock = getFetchMock();
    fetchMock.mockResolvedValueOnce(
      makeResponse({
        ok: true,
        body: {
          user: {
            vkId: '501',
            firstName: 'Виктор',
            username: 'victor',
            authDate: '2026-02-25T00:00:00Z',
            tenantId: 100,
            contactId: 12,
          },
        },
      })
    );

    const VKAuth = await loadComponent();
    const onClose = vi.fn();
    render(<VKAuth open onClose={onClose} tenantId={7} />);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    expect(onClose).not.toHaveBeenCalled();
    expect(testState.push).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Войти через ВКонтакте' })).toBeInTheDocument();
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
              vkId: '77',
              firstName: 'Олег',
              lastName: 'Сидоров',
              username: 'oleg',
              authDate: '2026-02-25T00:00:00Z',
            },
          },
        })
      )
      .mockResolvedValueOnce(makeResponse({ ok: true, body: {} }));

    const VKAuth = await loadComponent();
    const onClose = vi.fn();
    render(<VKAuth open onClose={onClose} />);

    const logoutButton = await screen.findByRole('button', { name: 'Выйти' });
    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(testState.push).toHaveBeenCalledWith('/welcome');
    });

    onClose.mockClear();
    testState.push.mockClear();

    fireEvent.click(logoutButton);

    expect(await screen.findByText('Вы вышли из аккаунта')).toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    expect(testState.push).toHaveBeenCalledWith('/login');
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      'https://api.example.com/auth/vk',
      expect.objectContaining({
        method: 'DELETE',
        credentials: 'include',
      })
    );
  });

  it('shows validation error when VK popup success message has no device_id', async () => {
    const fetchMock = getFetchMock();
    fetchMock
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401, text: '' }))
      .mockResolvedValueOnce(
        makeResponse({
          ok: true,
          body: {
            url: 'https://id.vk.com/authorize?test=1',
            state: 'vk-state-nodevice',
          },
        })
      );

    const popup = { closed: false, close: vi.fn() };
    vi.spyOn(window, 'open').mockImplementation(() => popup as any);

    const VKAuth = await loadComponent();
    render(<VKAuth open onClose={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Войти через ВКонтакте' }));

    await waitFor(() => {
      expect(sessionStorage.getItem('vk_auth_state')).toBe('vk-state-nodevice');
    });

    window.dispatchEvent(
      new MessageEvent('message', {
        origin: window.location.origin,
        data: {
          type: 'VK_AUTH_SUCCESS',
          code: 'code-1',
          state: 'vk-state-nodevice',
          deviceId: '',
        },
      })
    );

    expect(await screen.findByText('VK не вернул device_id')).toBeInTheDocument();
    expect(popup.close).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('exchanges popup success message code and redirects on successful VK login', async () => {
    const fetchMock = getFetchMock();
    fetchMock
      .mockResolvedValueOnce(makeResponse({ ok: false, status: 401, text: '' })) // initial checkAuth
      .mockResolvedValueOnce(
        makeResponse({
          ok: true,
          body: {
            url: 'https://id.vk.com/authorize?test=1',
            state: 'vk-state-success',
          },
        })
      )
      .mockResolvedValueOnce(
        makeResponse({
          ok: true,
          body: {
            user: {
              vkId: '99',
              firstName: 'Виктор',
              lastName: 'Иванов',
              username: 'victor',
              authDate: '2026-02-25T00:00:00Z',
            },
          },
        })
      );

    const popup = { closed: false, close: vi.fn() };
    vi.spyOn(window, 'open').mockImplementation(() => popup as any);

    const VKAuth = await loadComponent();
    const onClose = vi.fn();
    render(<VKAuth open onClose={onClose} tenantId={7} redirectTo="/vk-dashboard" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Войти через ВКонтакте' }));

    await waitFor(() => {
      expect(sessionStorage.getItem('vk_auth_state')).toBe('vk-state-success');
    });

    window.dispatchEvent(
      new MessageEvent('message', {
        origin: window.location.origin,
        data: {
          type: 'VK_AUTH_SUCCESS',
          code: ' code-123 ',
          state: ' vk-state-success ',
          deviceId: ' dev-456 ',
        },
      })
    );

    await waitFor(() => {
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(testState.push).toHaveBeenCalledWith('/vk-dashboard');
    });

    expect(popup.close).toHaveBeenCalledTimes(1);
    expect(sessionStorage.getItem('vk_auth_state')).toBeNull();
    expect(sessionStorage.getItem('vk_auth_mode')).toBeNull();
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      'https://api.example.com/auth/vk',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const thirdCall = fetchMock.mock.calls[2];
    const body = JSON.parse(thirdCall?.[1]?.body as string);
    expect(body).toMatchObject({
      code: 'code-123',
      state: 'vk-state-success',
      device_id: 'dev-456',
      tenant_id: 7,
      redirect_uri: 'https://frontend.example.com/auth/vk/callback',
    });
  });
});
