import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  listAccounts: vi.fn(),
  getPost: vi.fn(),
  updatePost: vi.fn(),
  createSchedule: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('@/lib/api/socialAccounts', () => ({
  socialAccountsApi: {
    list: (...args: any[]) => testState.listAccounts(...args),
  },
}));

vi.mock('@/lib/api/posts', () => ({
  postsApi: {
    get: (...args: any[]) => testState.getPost(...args),
    update: (...args: any[]) => testState.updatePost(...args),
  },
}));

vi.mock('@/lib/api/schedules', () => ({
  schedulesApi: {
    create: (...args: any[]) => testState.createSchedule(...args),
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
      { type: 'button', onClick: () => ctx?.onOpenChange?.(true) },
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

vi.mock('@/components/ui/select', async () => {
  const ReactModule = await import('react');
  const SelectCtx = ReactModule.createContext<{
    value: string;
    onValueChange?: (value: string) => void;
    disabled?: boolean;
  } | null>(null);

  const Select = ({ value, onValueChange, disabled, children }: any) =>
    ReactModule.createElement(SelectCtx.Provider, { value: { value, onValueChange, disabled } }, children);

  const SelectTrigger = ({ children, ...props }: any) => {
    const ctx = ReactModule.useContext(SelectCtx);
    return ReactModule.createElement(
      'button',
      {
        type: 'button',
        disabled: ctx?.disabled,
        ...props,
      },
      children
    );
  };

  const SelectValue = ({ placeholder }: any) => {
    const ctx = ReactModule.useContext(SelectCtx);
    return ReactModule.createElement('span', null, ctx?.value || placeholder || '');
  };

  const SelectContent = ({ children, ...props }: any) => ReactModule.createElement('div', props, children);

  const SelectItem = ({ value, children, ...props }: any) => {
    const ctx = ReactModule.useContext(SelectCtx);
    return ReactModule.createElement(
      'button',
      {
        type: 'button',
        'data-select-item': value,
        onClick: () => !ctx?.disabled && ctx?.onValueChange?.(value),
        ...props,
      },
      children
    );
  };

  return {
    Select,
    SelectTrigger,
    SelectValue,
    SelectContent,
    SelectItem,
  };
});

describe('SchedulePostDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetModules();
  });

  const loadComponent = async () => {
    const mod = await import('@/components/posts/schedule-post-dialog');
    return mod.SchedulePostDialog;
  };

  const baseAccounts = [
    { id: 10, name: 'VK Main', platform: 'vk', is_active: true },
    { id: 11, name: 'TG Channel', platform: 'telegram', is_active: true },
  ];

  const basePost = {
    id: 123,
    publish_text: true,
    publish_image: true,
    publish_video: true,
  };

  it('opens dialog, loads accounts and post content settings, and reflects checkbox values', async () => {
    testState.listAccounts.mockResolvedValueOnce(baseAccounts);
    testState.getPost.mockResolvedValueOnce({ ...basePost, publish_image: false });

    const SchedulePostDialog = await loadComponent();
    render(<SchedulePostDialog postId={123} />);

    fireEvent.click(screen.getByRole('button', { name: 'Запланировать' }));

    expect(await screen.findByText('Запланировать публикацию')).toBeInTheDocument();
    expect(await screen.findByText(/VK Main \(vk\)/i)).toBeInTheDocument();
    expect(testState.listAccounts).toHaveBeenCalledTimes(1);
    expect(testState.getPost).toHaveBeenCalledWith(123);

    const textCheckbox = screen.getByLabelText('Текст') as HTMLInputElement;
    const imageCheckbox = screen.getByLabelText('Фото') as HTMLInputElement;
    const videoCheckbox = screen.getByLabelText('Видео') as HTMLInputElement;
    expect(textCheckbox.checked).toBe(true);
    expect(imageCheckbox.checked).toBe(false);
    expect(videoCheckbox.checked).toBe(true);
  });

  it('validates that at least one content type is selected', async () => {
    testState.listAccounts.mockResolvedValueOnce(baseAccounts);
    testState.getPost.mockResolvedValueOnce(basePost);

    const SchedulePostDialog = await loadComponent();
    render(<SchedulePostDialog postId={123} />);

    fireEvent.click(screen.getByRole('button', { name: 'Запланировать' }));
    await screen.findByText('Запланировать публикацию');

    fireEvent.click(screen.getByLabelText('Текст'));
    fireEvent.click(screen.getByLabelText('Фото'));
    fireEvent.click(screen.getByLabelText('Видео'));

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    expect(testState.toastError).toHaveBeenCalledWith('Выберите хотя бы один тип контента');
    expect(testState.updatePost).not.toHaveBeenCalled();
    expect(testState.createSchedule).not.toHaveBeenCalled();
  });

  it('updates post content settings and creates schedule on successful submit', async () => {
    testState.listAccounts.mockResolvedValueOnce(baseAccounts);
    testState.getPost.mockResolvedValueOnce(basePost);
    testState.updatePost.mockResolvedValueOnce({ ...basePost, publish_video: false });
    testState.createSchedule.mockResolvedValueOnce({ id: 1 });

    const onScheduled = vi.fn().mockResolvedValue(undefined);
    const SchedulePostDialog = await loadComponent();
    render(<SchedulePostDialog postId={123} onScheduled={onScheduled} />);

    fireEvent.click(screen.getByRole('button', { name: 'Запланировать' }));
    await screen.findByText('Запланировать публикацию');

    fireEvent.click(screen.getByLabelText('Видео'));

    const dateInput = screen.getByLabelText('Дата и время') as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: '2026-03-01T15:30' } });

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(testState.updatePost).toHaveBeenCalledWith(123, {
        publish_text: true,
        publish_image: true,
        publish_video: false,
      });
      expect(testState.createSchedule).toHaveBeenCalledTimes(1);
      expect(testState.toastSuccess).toHaveBeenCalledWith('Публикация запланирована');
      expect(onScheduled).toHaveBeenCalledTimes(1);
    });

    expect(testState.createSchedule).toHaveBeenCalledWith({
      post: 123,
      social_account: 10,
      scheduled_at: new Date('2026-03-01T15:30').toISOString(),
    });
    expect(screen.queryByText('Запланировать публикацию')).not.toBeInTheDocument();
  });

  it('skips post settings update when content selection is unchanged and shows schedule error toast', async () => {
    testState.listAccounts.mockResolvedValueOnce(baseAccounts);
    testState.getPost.mockResolvedValueOnce(basePost);
    testState.createSchedule.mockRejectedValueOnce(new Error('create failed'));

    const SchedulePostDialog = await loadComponent();
    render(<SchedulePostDialog postId={123} />);

    fireEvent.click(screen.getByRole('button', { name: 'Запланировать' }));
    await screen.findByText('Запланировать публикацию');

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(testState.createSchedule).toHaveBeenCalledTimes(1);
      expect(testState.toastError).toHaveBeenCalledWith('Не удалось запланировать пост');
    });

    expect(testState.updatePost).not.toHaveBeenCalled();
    expect(screen.getByText('Запланировать публикацию')).toBeInTheDocument();
  });

  it('does not open or load data when trigger is disabled', async () => {
    const SchedulePostDialog = await loadComponent();
    render(<SchedulePostDialog postId={123} disabled />);

    const trigger = screen.getByRole('button', { name: 'Запланировать' });
    expect(trigger).toBeDisabled();

    fireEvent.click(trigger);

    expect(testState.listAccounts).not.toHaveBeenCalled();
    expect(testState.getPost).not.toHaveBeenCalled();
    expect(screen.queryByText('Запланировать публикацию')).not.toBeInTheDocument();
  });
});
