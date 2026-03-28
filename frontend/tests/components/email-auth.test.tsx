import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

type MockResponseInit = {
  ok: boolean;
  body?: unknown;
};

const makeResponse = ({ ok, body }: MockResponseInit): Response =>
  ({
    ok,
    json: vi.fn().mockResolvedValue(body ?? {}),
  }) as unknown as Response;

const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

describe('EmailAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', vi.fn());
    process.env.NEXT_PUBLIC_API_URL = 'https://api.example.com';
    sessionStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.resetModules();
    sessionStorage.clear();

    if (originalApiUrl === undefined) {
      delete process.env.NEXT_PUBLIC_API_URL;
    } else {
      process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
    }
  });

  const loadComponent = async () => {
    const mod = await import('@/components/auth/EmailAuth');
    return mod.EmailAuth;
  };

  const getFetchMock = () => global.fetch as unknown as ReturnType<typeof vi.fn>;

  it('shows API configuration error when NEXT_PUBLIC_API_URL is missing', async () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    const EmailAuth = await loadComponent();

    render(<EmailAuth open onClose={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
      target: { value: 'test@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Отправить ссылку' }));

    expect(await screen.findByText(/NEXT_PUBLIC_API_URL не задан/i)).toBeInTheDocument();
    expect(getFetchMock()).not.toHaveBeenCalled();
  });

  it('sends email magic link request and persists redirect target', async () => {
    const fetchMock = getFetchMock();
    fetchMock.mockResolvedValueOnce(makeResponse({ ok: true, body: { detail: 'Письмо отправлено.' } }));

    const EmailAuth = await loadComponent();
    render(<EmailAuth open onClose={vi.fn()} redirectTo="/seo" />);

    fireEvent.change(screen.getByPlaceholderText('you@example.com'), {
      target: { value: 'TeSt@example.com ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Отправить ссылку' }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('https://api.example.com/auth/email/send-magic-link', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@example.com' }),
      });
    });

    expect(sessionStorage.getItem('email_auth_redirect')).toBe('/seo');
    expect(await screen.findByText('Письмо отправлено')).toBeInTheDocument();
  });
});
