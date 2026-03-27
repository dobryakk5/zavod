import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  tab: 'edit',
  replace: vi.fn(),
  getCoachClient: vi.fn(),
  getCoachClientCompetencies: vi.fn(),
  getCoachClientMilestones: vi.fn(),
  getCoachClientSessions: vi.fn(),
  getCoachClientTasks: vi.fn(),
  saveCoachClientCompetencies: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: testState.replace }),
  useSearchParams: () => new URLSearchParams(`tab=${testState.tab}`),
}));

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) => ReactModule.createElement('a', { href, ...props }, children),
  };
});

vi.mock('@/app/coach/clients/[client_id]/page-client', () => ({
  default: () => <div>SessionPage</div>,
}));

vi.mock('@/lib/api/coaching', () => ({
  coachingApi: {
    getCoachClient: (...args: unknown[]) => testState.getCoachClient(...args),
    getCoachClientCompetencies: (...args: unknown[]) => testState.getCoachClientCompetencies(...args),
    getCoachClientMilestones: (...args: unknown[]) => testState.getCoachClientMilestones(...args),
    getCoachClientSessions: (...args: unknown[]) => testState.getCoachClientSessions(...args),
  },
  coachingApiExt: {
    getCoachClientTasks: (...args: unknown[]) => testState.getCoachClientTasks(...args),
    saveCoachClientCompetencies: (...args: unknown[]) => testState.saveCoachClientCompetencies(...args),
  },
}));

describe('CoachClientWorkspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.tab = 'edit';
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
    testState.getCoachClientCompetencies.mockResolvedValue([
      {
        id: 'confidence',
        name: 'Уверенность',
        score: 60,
        startScore: 45,
        color: '#1D9E75',
      },
    ]);
    testState.getCoachClientMilestones.mockResolvedValue([]);
    testState.getCoachClientSessions.mockResolvedValue([]);
    testState.getCoachClientTasks.mockResolvedValue([]);
    testState.saveCoachClientCompetencies.mockImplementation(async (_clientId: number, competencies: unknown) => competencies);
  });

  afterEach(() => {
    cleanup();
  });

  it('adds a new competency from the plus button and saves it', async () => {
    const mod = await import('@/app/coach/clients/[client_id]/workspace');
    const CoachClientWorkspace = mod.default;

    render(<CoachClientWorkspace clientId={46} />);

    await waitFor(() => {
      expect(testState.getCoachClient).toHaveBeenCalledWith(46);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Добавить компетенцию' }));
    fireEvent.change(await screen.findByPlaceholderText('Например, Эмпатия'), { target: { value: 'Эмпатия' } });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить' }));

    expect(screen.getByText('Эмпатия')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(testState.saveCoachClientCompetencies).toHaveBeenCalledWith(
        46,
        expect.arrayContaining([
          expect.objectContaining({
            name: 'Уверенность',
            score: 60,
            startScore: 45,
          }),
          expect.objectContaining({
            name: 'Эмпатия',
            score: 0,
            startScore: 0,
            color: expect.any(String),
          }),
        ]),
      );
    });
  });

  it('removes a competency and refreshes milestones after save', async () => {
    testState.getCoachClientCompetencies.mockResolvedValue([
      {
        id: 'confidence',
        name: 'Уверенность',
        score: 60,
        startScore: 45,
        color: '#1D9E75',
      },
      {
        id: 'empathy',
        name: 'Эмпатия',
        score: 70,
        startScore: 50,
        color: '#378ADD',
      },
    ]);
    testState.getCoachClientMilestones
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          id: 'milestone-1',
          clientId: 46,
          goalId: '',
          text: 'Рост компетенции Эмпатия на 20%',
          note: '',
          createdAt: '2026-03-28T12:00:00.000Z',
        },
      ]);

    const mod = await import('@/app/coach/clients/[client_id]/workspace');
    const CoachClientWorkspace = mod.default;

    render(<CoachClientWorkspace clientId={46} />);

    await waitFor(() => {
      expect(testState.getCoachClient).toHaveBeenCalledWith(46);
    });

    fireEvent.click(screen.getByRole('button', { name: 'Убрать компетенцию Эмпатия' }));
    await waitFor(() => {
      expect(screen.queryByText('Эмпатия')).not.toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(testState.saveCoachClientCompetencies).toHaveBeenCalledWith(
        46,
        [
          expect.objectContaining({
            id: 'confidence',
            name: 'Уверенность',
          }),
        ],
      );
      expect(testState.getCoachClientMilestones).toHaveBeenCalledTimes(2);
    });
  });
});
