import React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { TelegramAuthButton } from '@/components/auth/TelegramAuthButton';

describe('TelegramAuthButton', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('shows validation message for invalid bot username', () => {
    render(<TelegramAuthButton botUsername="@bad bot!" onAuthCallback={vi.fn()} />);

    expect(
      screen.getByText(/Некорректное имя Telegram-бота/i)
    ).toBeInTheDocument();
    expect(document.querySelector('script[src*="telegram-widget"]')).not.toBeInTheDocument();
  });

  it('normalizes bot username, injects script and calls auth callback via global handler', () => {
    vi.spyOn(Date, 'now').mockReturnValue(123456);
    const onAuthCallback = vi.fn();

    const { unmount } = render(
      <TelegramAuthButton
        botUsername="https://t.me/solarlab_bot?start=1"
        onAuthCallback={onAuthCallback}
        buttonSize="small"
        cornerRadius={12}
        showAvatar={false}
        lang="ru"
      />
    );

    const script = document.querySelector('script[src*="telegram-widget"]') as HTMLScriptElement | null;
    expect(script).toBeTruthy();
    expect(script?.getAttribute('data-telegram-login')).toBe('solarlab_bot');
    expect(script?.getAttribute('data-size')).toBe('small');
    expect(script?.getAttribute('data-radius')).toBe('12');
    expect(script?.getAttribute('data-userpic')).toBe('false');
    expect(script?.getAttribute('data-lang')).toBe('ru');
    expect(script?.getAttribute('data-onauth')).toBe('onTelegramAuth_123456(user)');

    const payload = { id: 1, first_name: 'Test' };
    (window as any).onTelegramAuth_123456(payload);
    expect(onAuthCallback).toHaveBeenCalledWith(payload);

    unmount();
    expect((window as any).onTelegramAuth_123456).toBeUndefined();
  });

  it('shows script loading error and fallback Telegram link', async () => {
    render(<TelegramAuthButton botUsername="solarlab_bot" onAuthCallback={vi.fn()} />);

    const script = document.querySelector('script[src*="telegram-widget"]') as HTMLScriptElement | null;
    expect(script).toBeTruthy();

    act(() => {
      script?.onerror?.(new Event('error'));
    });

    expect(await screen.findByText(/Не удалось загрузить скрипт Telegram/i)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /Открыть @solarlab_bot/i });
    expect(link).toHaveAttribute('href', 'https://t.me/solarlab_bot');
  });

  it('shows render probe timeout error when widget does not appear after script load', async () => {
    vi.useFakeTimers();
    render(<TelegramAuthButton botUsername="solarlab_bot" onAuthCallback={vi.fn()} />);

    const script = document.querySelector('script[src*="telegram-widget"]') as HTMLScriptElement | null;
    expect(script).toBeTruthy();

    act(() => {
      script?.onload?.(new Event('load'));
    });

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.getByText(/Виджет Telegram не загрузился/i)).toBeInTheDocument();
  });
});
