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

  it('starts the left panel with horizon tabs instead of a duplicated client header', async () => {
    const mod = await import('@/app/coach/clients/[client_id]/page-client');
    const CoachClientSessionPage = mod.default;

    render(<CoachClientSessionPage clientId={46} />);

    await waitFor(() => {
      expect(testState.getCoachClient).toHaveBeenCalledWith(46);
    });

    expect(screen.queryByRole('link', { name: 'Открыть кабинет клиента Анна Иванова' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Год' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Квартал' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Месяц' })).toBeInTheDocument();
  }, 10000);

  it('shows schedule links when there is no active session', async () => {
    testState.getCoachClientSessions.mockResolvedValue([
      {
        id: 'sess-done-5',
        clientId: 46,
        number: 5,
        date: '2026-03-28T12:00:00.000Z',
        notes: 'Подвели итоги месяца',
        coachNotes: 'Согласовать время следующей встречи',
        status: 'done',
      },
    ]);

    const mod = await import('@/app/coach/clients/[client_id]/page-client');
    const CoachClientSessionPage = mod.default;

    render(<CoachClientSessionPage clientId={46} />);

    await waitFor(() => {
      expect(screen.getByRole('link', { name: 'Запланируйте сессию' })).toHaveAttribute('href', '/contact/46?tab=schedule');
    });

    expect(screen.getByRole('link', { name: 'Обзор календаря' })).toHaveAttribute(
      'href',
      '/clients?tab=schedule&scheduleTab=calendar',
    );
    expect(
      screen.queryByText(/Активной сессии нет\. Нажмите «Начать сессию/i),
    ).not.toBeInTheDocument();
    expect(screen.getByText('Подвели итоги месяца')).toBeInTheDocument();
    expect(screen.getByText('Согласовать время следующей встречи')).toBeInTheDocument();
  });

  it('keeps schedule links hidden while a draft session is active', async () => {
    testState.getCoachClientSessions.mockResolvedValue([
      {
        id: 'sess-draft-6',
        clientId: 46,
        number: 6,
        date: '2026-03-30T12:00:00.000Z',
        notes: 'Черновик заметок',
        coachNotes: 'Черновик задания',
        status: 'draft',
      },
    ]);

    const mod = await import('@/app/coach/clients/[client_id]/page-client');
    const CoachClientSessionPage = mod.default;

    render(<CoachClientSessionPage clientId={46} />);

    await waitFor(() => {
      expect(screen.getByText('Автосохранение включено')).toBeInTheDocument();
    });

    expect(screen.queryByRole('link', { name: 'Запланируйте сессию' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Обзор календаря' })).not.toBeInTheDocument();
  });
});
