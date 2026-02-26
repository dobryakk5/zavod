import React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { toast } from 'sonner';
import { TrialLimitModal } from '@/components/layout/trial-limit-modal';
import { TRIAL_LIMIT_PAYMENT_URL, emitTrialLimitModalOpen } from '@/lib/trial-limit';

vi.mock('next/link', async () => {
  const ReactModule = await import('react');

  return {
    default: ({ href, children, ...props }: any) =>
      ReactModule.createElement(
        'a',
        {
          href: typeof href === 'string' ? href : String(href),
          ...props,
        },
        children
      ),
  };
});

vi.mock('@/components/ui/dialog', async () => {
  const ReactModule = await import('react');

  const wrap =
    (tag: string) =>
    ({ children, ...props }: any) =>
      ReactModule.createElement(tag, props, children);

  return {
    Dialog: ({ open, children }: any) => (open ? ReactModule.createElement('div', { 'data-testid': 'dialog' }, children) : null),
    DialogContent: wrap('div'),
    DialogHeader: wrap('div'),
    DialogTitle: wrap('h2'),
    DialogDescription: wrap('p'),
  };
});

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(() => 'toast-id'),
  },
}));

describe('TrialLimitModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('opens when trial-limit event is emitted and shows summary/link', async () => {
    render(<TrialLimitModal />);

    expect(screen.queryByText('Лимит ознакомительного тарифа исчерпан')).not.toBeInTheDocument();

    act(() => {
      emitTrialLimitModalOpen({ label: 'Посты', used: 3, limit: 3 });
    });

    expect(await screen.findByText('Лимит ознакомительного тарифа исчерпан')).toBeInTheDocument();
    expect(screen.getByText('Посты 3/3')).toBeInTheDocument();

    const link = screen.getByRole('link', { name: 'Получить безлимит' });
    expect(link).toHaveAttribute('href', TRIAL_LIMIT_PAYMENT_URL);
  });

  it('patches toast.error to intercept trial-limit messages and delegate other errors', async () => {
    const originalToastError = toast.error as unknown as ReturnType<typeof vi.fn>;

    render(<TrialLimitModal />);

    const patchedToastError = toast.error as typeof toast.error;
    expect(patchedToastError).not.toBe(originalToastError);

    act(() => {
      patchedToastError('Обычная ошибка');
    });
    expect(originalToastError).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Лимит ознакомительного тарифа исчерпан')).not.toBeInTheDocument();

    act(() => {
      patchedToastError('Лимит ознакомительного тарифа для "Видео" исчерпан (5/5)');
    });

    expect(originalToastError).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Лимит ознакомительного тарифа исчерпан')).toBeInTheDocument();
    expect(screen.getByText('Видео 5/5')).toBeInTheDocument();
  });
});
