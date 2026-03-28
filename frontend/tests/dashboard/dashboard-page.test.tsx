import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  getCoachStats: vi.fn(),
  getCoachClients: vi.fn(),
  getCoachClientCompetencies: vi.fn(),
  contactsList: vi.fn(),
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
}));

vi.mock('@/lib/api/crm', () => ({
  crmContactsApi: {
    list: (...args: unknown[]) => testState.contactsList(...args),
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
    testState.contactsList.mockResolvedValue([]);
    testState.dealsList.mockResolvedValue([]);
    testState.eventsList.mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
  });

  it('shows add client link next to clients heading', async () => {
    const mod = await import('@/app/dashboard/page');
    const DashboardPage = mod.default;

    render(<DashboardPage />);

    await waitFor(() => {
      expect(testState.getCoachClients).toHaveBeenCalled();
    });

    expect(screen.getByRole('link', { name: 'Добавить клиента' })).toHaveAttribute('href', '/clients/new');
  });
});
