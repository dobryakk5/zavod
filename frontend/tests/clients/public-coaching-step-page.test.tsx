import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  contactId: '91',
  from: 'tasks',
  getClientCoachingPortal: vi.fn(),
  getClientStepHistory: vi.fn(),
  editClientCoachingStep: vi.fn(),
  addClientStepComment: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams([
    ['contact_id', testState.contactId],
    ['from', testState.from],
  ]),
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
    getClientStepHistory: (...args: unknown[]) => testState.getClientStepHistory(...args),
    editClientCoachingStep: (...args: unknown[]) => testState.editClientCoachingStep(...args),
    addClientStepComment: (...args: unknown[]) => testState.addClientStepComment(...args),
  },
}));

describe('PublicCoachingStepPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.contactId = '91';
    testState.from = 'tasks';

    testState.getClientCoachingPortal.mockResolvedValue({
      client: { name: 'Анна Иванова' },
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
              dueDate: '2026-04-02',
              goalId: 'goal-1',
              goalTitle: 'Подготовить новый формат общения',
            },
          ],
          createdAt: '2026-03-01T10:00:00.000Z',
        },
      ],
      competencies: [],
      milestones: [],
    });
    testState.getClientStepHistory.mockResolvedValue([]);
    testState.editClientCoachingStep.mockResolvedValue({
      id: 'step-1',
      text: 'Обновлённый шаг',
      done: false,
      isMilestone: true,
      milestoneNote: 'Важно',
      doneAt: null,
      dueDate: '2026-04-03',
      goalId: 'goal-1',
      goalTitle: 'Подготовить новый формат общения',
    });
    testState.addClientStepComment.mockResolvedValue({
      id: 501,
      task_id: 1,
      note: 'Мой комментарий',
      status: 'open',
      created_by: -91,
      created_at: '2026-03-30T10:00:00.000Z',
      created_by_username: null,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders client step editor without delete action', async () => {
    const mod = await import('@/app/c/[client_id]/coaching/steps/[step_id]/page-client');
    const PublicCoachingStepPage = mod.default;

    render(<PublicCoachingStepPage clientId={46} stepId="step-1" />);

    await waitFor(() => {
      expect(testState.getClientCoachingPortal).toHaveBeenCalledWith(46, { contactId: 91 });
    });

    expect(screen.getByRole('link', { name: 'Вернуться назад' })).toHaveAttribute('href', '/c/46/tasks?contact_id=91');
    expect(screen.getByDisplayValue('Сделать 3 пробных разговора')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Удалить/i })).not.toBeInTheDocument();
  });

  it('saves client step edits and allows adding a comment', async () => {
    const mod = await import('@/app/c/[client_id]/coaching/steps/[step_id]/page-client');
    const PublicCoachingStepPage = mod.default;

    render(<PublicCoachingStepPage clientId={46} stepId="step-1" />);

    const titleInput = await screen.findByDisplayValue('Сделать 3 пробных разговора');
    fireEvent.change(titleInput, { target: { value: 'Обновлённый шаг' } });
    fireEvent.change(screen.getByLabelText('Срок'), { target: { value: '2026-04-03' } });
    fireEvent.click(screen.getByLabelText('Отмечать этот шаг как веху'));
    fireEvent.change(screen.getByLabelText('Комментарий к вехе'), { target: { value: 'Важно' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(testState.editClientCoachingStep).toHaveBeenCalledWith(
        46,
        'step-1',
        {
          text: 'Обновлённый шаг',
          dueDate: '2026-04-03',
          isMilestone: true,
          milestoneNote: 'Важно',
        },
        { contactId: 91 },
      );
    });

    fireEvent.change(screen.getByPlaceholderText('Добавьте комментарий к задаче'), { target: { value: 'Мой комментарий' } });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить комментарий' }));

    await waitFor(() => {
      expect(testState.addClientStepComment).toHaveBeenCalledWith(46, 'step-1', 'Мой комментарий', { contactId: 91 });
    });
    expect(screen.getAllByText('Комментарий').length).toBeGreaterThan(0);
    expect(screen.getByText('Мой комментарий')).toBeInTheDocument();
  });
});
