import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  getCoachStats: vi.fn(),
  getCoachClients: vi.fn(),
  getCoachClientCompetencies: vi.fn(),
  getCoachGroups: vi.fn(),
  getCoachGroupDetail: vi.fn(),
  createCoachGroup: vi.fn(),
  addGroupMember: vi.fn(),
  addGroupMembers: vi.fn(),
  removeGroupMember: vi.fn(),
  createGroupTask: vi.fn(),
  deleteGroupTask: vi.fn(),
  contactsList: vi.fn(),
  contactsCreate: vi.fn(),
  dealsList: vi.fn(),
  eventsList: vi.fn(),
}));

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) => ReactModule.createElement('a', { href, ...props }, children),
  };
});

vi.mock('@/lib/api/coaching', () => ({
  coachingApi: {
    getCoachStats: (...args: unknown[]) => testState.getCoachStats(...args),
    getCoachClients: (...args: unknown[]) => testState.getCoachClients(...args),
    getCoachClientCompetencies: (...args: unknown[]) => testState.getCoachClientCompetencies(...args),
  },
  coachingApiGroups: {
    getCoachGroups: (...args: unknown[]) => testState.getCoachGroups(...args),
    getCoachGroupDetail: (...args: unknown[]) => testState.getCoachGroupDetail(...args),
    createCoachGroup: (...args: unknown[]) => testState.createCoachGroup(...args),
    addGroupMember: (...args: unknown[]) => testState.addGroupMember(...args),
    addGroupMembers: (...args: unknown[]) => testState.addGroupMembers(...args),
    removeGroupMember: (...args: unknown[]) => testState.removeGroupMember(...args),
    createGroupTask: (...args: unknown[]) => testState.createGroupTask(...args),
    deleteGroupTask: (...args: unknown[]) => testState.deleteGroupTask(...args),
  },
}));

vi.mock('@/lib/api/crm', () => ({
  crmContactsApi: {
    list: (...args: unknown[]) => testState.contactsList(...args),
    create: (...args: unknown[]) => testState.contactsCreate(...args),
  },
  crmDealsApi: {
    list: (...args: unknown[]) => testState.dealsList(...args),
  },
  crmEventsApi: {
    list: (...args: unknown[]) => testState.eventsList(...args),
  },
}));

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-03-28T12:00:00.000Z').getTime());
    testState.getCoachStats.mockResolvedValue({
      activeClients: 1,
      completedTasks: 2,
      avgProgress: 30,
      sessionsToday: 0,
    });
    testState.getCoachClients.mockResolvedValue([
      {
        id: '46',
        name: 'Анна Иванова',
        initials: 'АИ',
        focus: 'Уверенность',
        intention: '',
        sessionsCount: 2,
        avgProgress: 30,
        nextSession: null,
        clientStatus: null,
        coachId: '1',
        createdAt: '2026-03-01T10:00:00.000Z',
      },
    ]);
    testState.getCoachClientCompetencies.mockResolvedValue([]);
    testState.getCoachGroups.mockResolvedValue([]);
    testState.getCoachGroupDetail.mockResolvedValue(null);
    testState.createCoachGroup.mockResolvedValue(null);
    testState.addGroupMember.mockResolvedValue(null);
    testState.removeGroupMember.mockResolvedValue(undefined);
    testState.createGroupTask.mockResolvedValue(null);
    testState.deleteGroupTask.mockResolvedValue(undefined);
    testState.addGroupMembers.mockResolvedValue([]);
    testState.contactsList.mockResolvedValue([]);
    testState.contactsCreate.mockResolvedValue({
      id: 77,
      name: 'Мария Петрова',
      email: '',
      phone: '',
      category_id: null,
      status: 'active',
      photo_url: '',
      notes: '',
      parent_id: null,
      created_at: '2026-03-28T12:00:00.000Z',
      updated_at: '2026-03-28T12:00:00.000Z',
    });
    testState.dealsList.mockResolvedValue([]);
    testState.eventsList.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    cleanup();
  });

  it('shows crm link in dashboard tabs', async () => {
    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(testState.getCoachClients).toHaveBeenCalled();
    });

    expect(screen.getByRole('link', { name: /crm/i })).toHaveAttribute('href', '/clients');
    expect(screen.getByRole('button', { name: '+' })).toBeInTheDocument();
  });

  it('shows recent new clients summary for clients created in the last 30 days', async () => {
    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    expect(await screen.findByText('+1 новый клиент за 30 дней')).toBeInTheDocument();
  });

  it('hides new clients summary when there are no recent clients', async () => {
    testState.getCoachClients.mockResolvedValue([
      {
        id: '46',
        name: 'Анна Иванова',
        initials: 'АИ',
        focus: 'Уверенность',
        intention: '',
        sessionsCount: 2,
        avgProgress: 30,
        nextSession: null,
        clientStatus: null,
        coachId: '1',
        createdAt: '2026-02-01T10:00:00.000Z',
      },
    ]);

    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(testState.getCoachClients).toHaveBeenCalled();
    });

    expect(screen.queryByText(/нов(ый|ых) клиент/)).not.toBeInTheDocument();
  });

  it('shows empty-state hint for clients when list is empty', async () => {
    testState.getCoachClients.mockResolvedValue([]);

    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    expect(
      (await screen.findAllByText((_, element) => element?.textContent === 'Для добавления клиентов нажмите кнопку "+"')).length
    ).toBeGreaterThan(0);
  });

  it('opens client quick add row and creates a client from dashboard', async () => {
    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(testState.getCoachClients).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole('button', { name: '+' }));
    fireEvent.change(screen.getByPlaceholderText('Новый клиент...'), {
      target: { value: '  Мария   Петрова ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить' }));

    await waitFor(() => {
      expect(testState.contactsCreate).toHaveBeenCalledWith({ name: 'Мария Петрова' });
    });

    expect(screen.getByText('Мария П.')).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Новый клиент...')).not.toBeInTheDocument();
  });

  it('opens group quick add row and creates a group from dashboard', async () => {
    testState.createCoachGroup.mockResolvedValue({
      id: '9',
      name: 'Новая группа',
      initials: 'НГ',
      memberCount: 0,
    });
    testState.getCoachGroupDetail.mockResolvedValue({
      group: {
        id: '9',
        name: 'Новая группа',
        initials: 'НГ',
        memberCount: 0,
      },
      members: [],
      tasks: [],
    });

    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(testState.getCoachClients).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Группы' }));
    fireEvent.click(screen.getByRole('button', { name: '+' }));
    fireEvent.change(screen.getByPlaceholderText('Новая группа...'), {
      target: { value: 'Новая группа' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить' }));

    await waitFor(() => {
      expect(testState.createCoachGroup).toHaveBeenCalledWith('Новая группа');
    });

    expect((await screen.findAllByText('Новая группа')).length).toBeGreaterThan(0);
    expect(screen.queryByPlaceholderText('Новая группа...')).not.toBeInTheDocument();
  });

  it('resets quick add row when switching tabs', async () => {
    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(testState.getCoachClients).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole('button', { name: '+' }));
    fireEvent.change(screen.getByPlaceholderText('Новый клиент...'), {
      target: { value: 'Черновик клиента' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Группы' }));

    expect(screen.queryByPlaceholderText('Новый клиент...')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '+' }));
    expect(screen.getByPlaceholderText('Новая группа...')).toHaveValue('');
  });

  it('shows empty-state hint for groups when list is empty', async () => {
    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(testState.getCoachClients).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Группы' }));

    expect(
      (await screen.findAllByText((_, element) => element?.textContent === 'Для добавления групп нажмите кнопку "+"')).length
    ).toBeGreaterThan(0);
  });
});
