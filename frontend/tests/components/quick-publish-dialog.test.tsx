import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  listAccounts: vi.fn(),
  quickPublish: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('@/lib/api/posts', () => ({
  postsApi: {
    quickPublish: (...args: any[]) => testState.quickPublish(...args),
  },
}));

vi.mock('@/lib/api/socialAccounts', () => ({
  socialAccountsApi: {
    list: (...args: any[]) => testState.listAccounts(...args),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: (...args: any[]) => testState.toastSuccess(...args),
    error: (...args: any[]) => testState.toastError(...args),
  },
}));

vi.mock('@/components/ui/dialog', async () => {
  const ReactModule = await import('react');
  const DialogCtx = ReactModule.createContext<{ open: boolean; onOpenChange?: (value: boolean) => void } | null>(null);

  const Dialog = ({ open, onOpenChange, children }: any) =>
    ReactModule.createElement(DialogCtx.Provider, { value: { open, onOpenChange } }, children);

  const DialogTrigger = ({ asChild, children }: any) => {
    const ctx = ReactModule.useContext(DialogCtx);
    const onlyChild = ReactModule.Children.only(children) as React.ReactElement<any>;

    if (asChild) {
      return ReactModule.cloneElement(onlyChild, {
        ...onlyChild.props,
        onClick: (event: any) => {
          onlyChild.props.onClick?.(event);
          if (!onlyChild.props.disabled) {
            ctx?.onOpenChange?.(true);
          }
        },
      });
    }

    return ReactModule.createElement(
      'button',
      {
        type: 'button',
        onClick: () => ctx?.onOpenChange?.(true),
      },
      children
    );
  };

  const DialogContent = ({ children, ...props }: any) => {
    const ctx = ReactModule.useContext(DialogCtx);
    if (!ctx?.open) return null;
    return ReactModule.createElement('div', props, children);
  };

  const wrap =
    (tag: string) =>
    ({ children, ...props }: any) =>
      ReactModule.createElement(tag, props, children);

  return {
    Dialog,
    DialogTrigger,
    DialogContent,
    DialogHeader: wrap('div'),
    DialogTitle: wrap('h2'),
    DialogDescription: wrap('p'),
  };
});

describe('QuickPublishDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetModules();
  });

  const loadComponent = async () => {
    const mod = await import('@/components/posts/quick-publish-dialog');
    return mod.QuickPublishDialog;
  };

  it('opens dialog, loads accounts and publishes to selected account', async () => {
    testState.listAccounts.mockResolvedValueOnce([
      { id: 11, platform: 'vk', name: 'VK Main', is_active: true },
      { id: 12, platform: 'telegram', name: 'TG Channel', is_active: false },
    ]);
    testState.quickPublish.mockResolvedValueOnce({ task_id: 'task-1' });

    const QuickPublishDialog = await loadComponent();
    render(<QuickPublishDialog postId={55} />);

    fireEvent.click(screen.getByRole('button', { name: 'Быстрая публикация' }));

    expect(await screen.findByText('Выберите социальную сеть')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: /VK Main/i })).toBeInTheDocument();
    expect(testState.listAccounts).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /VK Main/i }));

    await waitFor(() => {
      expect(testState.quickPublish).toHaveBeenCalledWith(55, { social_account_id: 11 });
      expect(testState.toastSuccess).toHaveBeenCalledWith('Публикация запущена');
    });

    expect(screen.queryByText('Выберите социальную сеть')).not.toBeInTheDocument();
  });

  it('shows toast and empty-state fallback when accounts loading fails', async () => {
    testState.listAccounts.mockRejectedValueOnce(new Error('boom'));

    const QuickPublishDialog = await loadComponent();
    render(<QuickPublishDialog postId={1} />);

    fireEvent.click(screen.getByRole('button', { name: 'Быстрая публикация' }));

    expect(await screen.findByText('Нет подключенных аккаунтов')).toBeInTheDocument();
    expect(testState.toastError).toHaveBeenCalledWith('Не удалось загрузить аккаунты');
  });

  it('shows error toast when quick publish fails and keeps dialog open', async () => {
    testState.listAccounts.mockResolvedValueOnce([
      { id: 21, platform: 'telegram', name: 'TG Channel', is_active: true },
    ]);
    testState.quickPublish.mockRejectedValueOnce(new Error('publish failed'));

    const QuickPublishDialog = await loadComponent();
    render(<QuickPublishDialog postId={88} />);

    fireEvent.click(screen.getByRole('button', { name: 'Быстрая публикация' }));
    fireEvent.click(await screen.findByRole('button', { name: /TG Channel/i }));

    await waitFor(() => {
      expect(testState.quickPublish).toHaveBeenCalledWith(88, { social_account_id: 21 });
      expect(testState.toastError).toHaveBeenCalledWith('Ошибка при публикации');
    });

    expect(screen.getByText('Выберите социальную сеть')).toBeInTheDocument();
  });

  it('does not open or load accounts when trigger is disabled', async () => {
    const QuickPublishDialog = await loadComponent();
    render(<QuickPublishDialog postId={5} disabled />);

    const trigger = screen.getByRole('button', { name: 'Быстрая публикация' });
    expect(trigger).toBeDisabled();

    fireEvent.click(trigger);

    expect(testState.listAccounts).not.toHaveBeenCalled();
    expect(screen.queryByText('Выберите социальную сеть')).not.toBeInTheDocument();
  });
});
