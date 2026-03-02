import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  push: vi.fn(),
  router: { push: vi.fn() },
  telegramList: vi.fn(),
  operatorList: vi.fn(),
  operatorCreate: vi.fn(),
  operatorAddHistory: vi.fn(),
  useTenantTimezone: vi.fn(() => ({ timezone: 'Europe/Moscow', loading: false })),
  formatInTenantTimezone: vi.fn((value: string) => `formatted:${value}`),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => testState.router,
}));

vi.mock('@/lib/api/telegramTasks', () => ({
  telegramTasksApi: {
    list: testState.telegramList,
  },
}));

vi.mock('@/lib/api/operatorTasks', () => ({
  operatorTasksApi: {
    list: testState.operatorList,
    create: testState.operatorCreate,
    addHistory: testState.operatorAddHistory,
  },
}));

vi.mock('@/lib/hooks', () => ({
  useTenantTimezone: testState.useTenantTimezone,
}));

vi.mock('@/lib/timezone', () => ({
  formatInTenantTimezone: testState.formatInTenantTimezone,
}));

describe('ScheduleTasksView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.router.push = testState.push;
    testState.useTenantTimezone.mockReturnValue({ timezone: 'Europe/Moscow', loading: false });
    testState.formatInTenantTimezone.mockImplementation((value: string) => `formatted:${value}`);
  });

  afterEach(() => {
    cleanup();
  });

  const loadComponent = async () => {
    const mod = await import('@/app/schedule/tasks-view');
    return mod.default;
  };

  const baseItems = [
    {
      id: 1,
      contact_name: null,
      tg_name: 'alice',
      message_text: 'Хочу больше кейсов',
      received_at: '2026-02-26T09:00:00Z',
      rating: 7,
    },
    {
      id: 2,
      contact_name: null,
      tg_name: 'bob',
      message_text: 'Все отлично',
      received_at: '2026-02-27T09:00:00Z',
      rating: 10,
    },
  ];

  it('shows empty state when no feedback exists', async () => {
    testState.telegramList.mockResolvedValueOnce([]);
    testState.operatorList.mockResolvedValueOnce([]);
    const ScheduleTasksView = await loadComponent();

    render(<ScheduleTasksView />);

    expect(await screen.findByText('Обратной связи пока нет.')).toBeInTheDocument();
  });

  it('redirects to login on 401 ApiError while loading feedback', async () => {
    const { ApiError } = await import('@/lib/api');
    testState.telegramList.mockRejectedValueOnce(new ApiError('unauthorized', 401));
    testState.operatorList.mockResolvedValueOnce([]);
    const ScheduleTasksView = await loadComponent();

    render(<ScheduleTasksView />);

    await waitFor(() => {
      expect(testState.push).toHaveBeenCalledWith('/login');
    });
  });

  it('sorts rows by rating when header is clicked', async () => {
    testState.telegramList.mockResolvedValueOnce(baseItems);
    testState.operatorList.mockResolvedValueOnce([]);
    const ScheduleTasksView = await loadComponent();

    render(<ScheduleTasksView />);

    await screen.findByText('@bob');

    // Default sort is by received_at desc, so @bob should appear before @alice.
    let clientCells = screen.getAllByRole('cell').filter((cell) => cell.textContent === '@alice' || cell.textContent === '@bob');
    expect(clientCells.map((c) => c.textContent)).toEqual(['@bob', '@alice']);

    fireEvent.click(screen.getByRole('button', { name: /Оценка/ }));
    clientCells = screen.getAllByRole('cell').filter((cell) => cell.textContent === '@alice' || cell.textContent === '@bob');
    expect(clientCells.map((c) => c.textContent)).toEqual(['@bob', '@alice']); // rating desc first click

    fireEvent.click(screen.getByRole('button', { name: /Оценка/ }));
    clientCells = screen.getAllByRole('cell').filter((cell) => cell.textContent === '@alice' || cell.textContent === '@bob');
    expect(clientCells.map((c) => c.textContent)).toEqual(['@alice', '@bob']); // asc second click
  });

  it('creates operator task from row button and opens modal', async () => {
    testState.telegramList.mockResolvedValueOnce([baseItems[0]]);
    testState.operatorList.mockResolvedValueOnce([]);
    testState.operatorCreate.mockResolvedValueOnce({
      id: 101,
      level_id: 1,
      title: 'Обратная связь от @alice',
      description: 'Хочу больше кейсов',
      status: 'open',
      priority: 1,
      created_by: 1,
      created_at: '2026-02-27T10:00:00Z',
      updated_at: '2026-02-27T10:00:00Z',
      history: [],
    });

    const ScheduleTasksView = await loadComponent();
    render(<ScheduleTasksView />);

    const row = await screen.findByText('Хочу больше кейсов');
    const rowEl = row.closest('tr') as HTMLTableRowElement;
    fireEvent.click(within(rowEl).getByRole('button'));

    expect(await screen.findByText('Задачи по обратной связи')).toBeInTheDocument();

    await waitFor(() => {
      expect(testState.operatorCreate).toHaveBeenCalledWith({
        level_id: 1,
        title: 'Обратная связь от @alice',
        description: 'Хочу больше кейсов',
        priority: 1,
      });
    });

    expect(await screen.findByText('Обратная связь от @alice')).toBeInTheDocument();
  });

  it('adds history step in modal and updates task status to done', async () => {
    testState.telegramList.mockResolvedValueOnce([baseItems[0]]);
    testState.operatorList.mockResolvedValueOnce([
      {
        id: 201,
        level_id: 1,
        title: 'Обратная связь от @alice',
        description: 'Хочу больше кейсов',
        status: 'open',
        priority: 1,
        created_by: 1,
        created_at: '2026-02-27T10:00:00Z',
        updated_at: '2026-02-27T10:00:00Z',
        history: [],
      },
    ]);
    testState.operatorAddHistory.mockResolvedValueOnce({
      id: 301,
      task_id: 201,
      note: 'Подготовили подборку кейсов',
      status: 'done',
      created_by: 1,
      created_by_username: 'manager',
      created_at: '2026-02-27T11:00:00Z',
    });

    const ScheduleTasksView = await loadComponent();
    render(<ScheduleTasksView />);

    const row = await screen.findByText('Хочу больше кейсов');
    const rowEl = row.closest('tr') as HTMLTableRowElement;
    fireEvent.click(within(rowEl).getByRole('button'));

    await screen.findByText('Обратная связь от @alice');

    fireEvent.change(screen.getByPlaceholderText('Добавить шаг решения…'), {
      target: { value: 'Подготовили подборку кейсов' },
    });
    fireEvent.change(screen.getByDisplayValue('Статус без изменений'), {
      target: { value: 'done' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить шаг' }));

    await waitFor(() => {
      expect(testState.operatorAddHistory).toHaveBeenCalledWith(201, {
        note: 'Подготовили подборку кейсов',
        status: 'done',
      });
    });

    expect(await screen.findByText('Подготовили подборку кейсов')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Переоткрыть' })).toBeInTheDocument();
    expect(screen.getAllByText('Выполнена').length).toBeGreaterThanOrEqual(1);
  });
});
