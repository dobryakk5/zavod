import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  clientId: '46',
  getClientCoachingPortal: vi.fn(),
  updateClientCoachingStep: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useParams: () => ({ client_id: testState.clientId }),
}));

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) => ReactModule.createElement('a', { href, ...props }, children),
  };
});

vi.mock('@/lib/api', () => {
  class TestApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
    }
  }

  return {
    ApiError: TestApiError,
  };
});

vi.mock('@/lib/api/coaching', () => ({
  coachingApi: {
    getClientCoachingPortal: (...args: unknown[]) => testState.getClientCoachingPortal(...args),
    updateClientCoachingStep: (...args: unknown[]) => testState.updateClientCoachingStep(...args),
  },
}));

describe('Public coaching portal page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.clientId = '46';
    testState.getClientCoachingPortal.mockResolvedValue({
      client: {
        name: 'Анна Иванова',
        intention: 'Говорить увереннее на встречах',
      },
      goals: [
        {
          id: 'goal-1',
          title: 'Подготовить новый формат общения',
          progress: 55,
          horizon: 'quarter',
          status: 'active',
          competencyLinks: [],
          steps: [
            {
              id: 'step-1',
              text: 'Сделать 3 пробных разговора',
              done: false,
              isMilestone: false,
              milestoneNote: '',
              doneAt: null,
              dueDate: null,
              goalId: 'goal-1',
              goalTitle: 'Подготовить новый формат общения',
            },
          ],
          createdAt: '2026-03-01T10:00:00.000Z',
        },
      ],
      competencies: [],
      milestones: [
        {
          id: 'milestone-1',
          clientId: 46,
          goalId: 'goal-1',
          text: 'Первый уверенный разговор',
          note: 'Отмечено коучем',
          createdAt: '2026-03-20T10:00:00.000Z',
        },
      ],
    });
    testState.updateClientCoachingStep.mockResolvedValue({
      id: 'step-1',
      text: 'Сделать 3 пробных разговора',
      done: true,
      isMilestone: false,
      milestoneNote: '',
      doneAt: '2026-03-21T10:00:00.000Z',
      dueDate: null,
      goalId: 'goal-1',
      goalTitle: 'Подготовить новый формат общения',
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders progress data from the public coaching endpoint', async () => {
    const mod = await import('@/app/c/[client_id]/coaching/page-client');
    const CoachingPortalPage = mod.default;

    render(<CoachingPortalPage />);

    await waitFor(() => {
      expect(testState.getClientCoachingPortal).toHaveBeenCalledWith(46);
    });

    expect(screen.getByText('Моё намерение')).toBeInTheDocument();
    expect(screen.getByText('Говорить увереннее на встречах')).toBeInTheDocument();
    expect(screen.getByText('Подготовить новый формат общения')).toBeInTheDocument();
    expect(screen.getByText('Первый уверенный разговор')).toBeInTheDocument();
  });

  it('toggles a client step via the public step endpoint', async () => {
    const mod = await import('@/app/c/[client_id]/coaching/page-client');
    const CoachingPortalPage = mod.default;

    render(<CoachingPortalPage />);

    const stepButton = await screen.findByRole('button', { name: /Сделать 3 пробных разговора/i });
    fireEvent.click(stepButton);

    await waitFor(() => {
      expect(testState.updateClientCoachingStep).toHaveBeenCalledWith(46, 'step-1', true);
    });
  });
});
