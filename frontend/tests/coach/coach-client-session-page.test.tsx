import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  getCoachClient: vi.fn(),
  getCoachClientCompetencies: vi.fn(),
  getCoachClientGoals: vi.fn(),
  getCoachClientMilestones: vi.fn(),
  getCoachClientSessions: vi.fn(),
}));

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) => ReactModule.createElement('a', { href, ...props }, children),
  };
});

vi.mock('@/lib/api/coaching', () => ({
  coachingApi: {
    getCoachClient: (...args: unknown[]) => testState.getCoachClient(...args),
    getCoachClientCompetencies: (...args: unknown[]) => testState.getCoachClientCompetencies(...args),
    getCoachClientGoals: (...args: unknown[]) => testState.getCoachClientGoals(...args),
    getCoachClientMilestones: (...args: unknown[]) => testState.getCoachClientMilestones(...args),
    getCoachClientSessions: (...args: unknown[]) => testState.getCoachClientSessions(...args),
  },
}));

describe('CoachClientSessionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.getCoachClient.mockResolvedValue({
      id: '46',
      name: 'Анна Иванова',
      initials: 'АИ',
      focus: 'Уверенность',
      intention: 'Выстроить спокойную коммуникацию',
      sessionsCount: 3,
      avgProgress: 52,
      nextSession: null,
      clientStatus: null,
      coachId: '7',
      createdAt: '2026-03-01T10:00:00.000Z',
    });
    testState.getCoachClientCompetencies.mockResolvedValue([]);
    testState.getCoachClientGoals.mockResolvedValue([]);
    testState.getCoachClientMilestones.mockResolvedValue([]);
    testState.getCoachClientSessions.mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
  });

  it('shows a link to the public coaching portal in the session header', async () => {
    const mod = await import('@/app/coach/clients/[client_id]/page-client');
    const CoachClientSessionPage = mod.default;

    render(<CoachClientSessionPage clientId={46} />);

    await waitFor(() => {
      expect(testState.getCoachClient).toHaveBeenCalledWith(46);
    });

    expect(
      screen.getByRole('link', { name: 'Открыть кабинет клиента Анна Иванова' }),
    ).toHaveAttribute('href', '/c/46/coaching');
  }, 10000);
});
