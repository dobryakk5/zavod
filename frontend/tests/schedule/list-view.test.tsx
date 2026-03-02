import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  push: vi.fn(),
  router: { push: vi.fn() },
  list: vi.fn(),
  useTenantTimezone: vi.fn(() => ({ timezone: 'Europe/Moscow', loading: false })),
  formatInTenantTimezone: vi.fn((value: string, timezone: string) => `formatted:${timezone}:${value}`),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => testState.router,
}));

vi.mock('@/lib/api/schedules', () => ({
  schedulesApi: {
    list: testState.list,
  },
}));

vi.mock('@/lib/hooks', () => ({
  useTenantTimezone: testState.useTenantTimezone,
}));

vi.mock('@/lib/timezone', () => ({
  formatInTenantTimezone: testState.formatInTenantTimezone,
}));

describe('ScheduleListView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.router.push = testState.push;
    testState.useTenantTimezone.mockReturnValue({ timezone: 'Europe/Moscow', loading: false });
    testState.formatInTenantTimezone.mockImplementation((value: string, timezone: string) => `formatted:${timezone}:${value}`);
  });

  afterEach(() => {
    cleanup();
    vi.resetModules();
  });

  const loadComponent = async () => {
    const mod = await import('@/app/schedule/list-view');
    return mod.default;
  };

  it('shows empty state when no schedules are returned', async () => {
    testState.list.mockResolvedValueOnce([]);
    const ScheduleListView = await loadComponent();

    render(<ScheduleListView />);

    expect(await screen.findByText('Запланированных публикаций нет.')).toBeInTheDocument();
    expect(testState.push).not.toHaveBeenCalled();
  });

  it('renders schedule rows and formats date using tenant timezone', async () => {
    testState.list.mockResolvedValueOnce([
      {
        id: 1,
        post_title: 'Пост про запуск',
        platform: 'telegram',
        scheduled_at: '2026-02-26T09:00:00Z',
        status: 'pending',
      },
    ]);

    const ScheduleListView = await loadComponent();
    render(<ScheduleListView />);

    expect(await screen.findByText('Пост про запуск')).toBeInTheDocument();
    expect(screen.getByText('telegram')).toBeInTheDocument();
    expect(screen.getByText('pending')).toBeInTheDocument();
    expect(screen.getByText('formatted:Europe/Moscow:2026-02-26T09:00:00Z')).toBeInTheDocument();

    expect(testState.formatInTenantTimezone).toHaveBeenCalledWith(
      '2026-02-26T09:00:00Z',
      'Europe/Moscow',
      expect.objectContaining({
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    );
  });

  it('redirects to login on 401 ApiError', async () => {
    const { ApiError } = await import('@/lib/api');
    testState.list.mockRejectedValueOnce(new ApiError('unauthorized', 401));
    const ScheduleListView = await loadComponent();

    render(<ScheduleListView />);

    await waitFor(() => {
      expect(testState.push).toHaveBeenCalledWith('/login');
    });
    expect(screen.queryByText('Не удалось загрузить расписание')).not.toBeInTheDocument();
  });

  it('shows generic error for non-auth failures', async () => {
    testState.list.mockRejectedValueOnce(new Error('network'));
    const ScheduleListView = await loadComponent();

    render(<ScheduleListView />);

    expect(await screen.findByText('Не удалось загрузить расписание')).toBeInTheDocument();
    expect(testState.push).not.toHaveBeenCalled();
  });
});
