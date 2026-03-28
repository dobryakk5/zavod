import React from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  search: '',
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(testState.search),
}));

vi.mock('@/components/auth/TelegramAuth', () => ({
  TelegramAuth: () => <div>TelegramAuth</div>,
}));

vi.mock('@/components/auth/VKAuth', () => ({
  VKAuth: () => <div>VKAuth</div>,
}));

vi.mock('@/components/auth/EmailAuth', () => ({
  EmailAuth: () => <div>EmailAuth</div>,
}));

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.search = '';
  });

  afterEach(() => {
    cleanup();
  });

  it('shows email login on regular login page', async () => {
    const mod = await import('@/app/login/page');
    const LoginPage = mod.default;

    render(<LoginPage />);

    expect(screen.getByRole('button', { name: /Войти по email/i })).toBeInTheDocument();
  });

  it('hides email login in contact login mode', async () => {
    testState.search = 'tenant_id=42';
    const mod = await import('@/app/login/page');
    const LoginPage = mod.default;

    render(<LoginPage />);

    expect(screen.queryByRole('button', { name: /Войти по email/i })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Войти как контакт' })).toBeInTheDocument();
  });
});
