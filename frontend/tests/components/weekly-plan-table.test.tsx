import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  emitStart: vi.fn(),
  emitComplete: vi.fn(),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    apiFetch: (...args: any[]) => testState.apiFetch(...args),
  };
});

vi.mock('sonner', () => ({
  toast: {
    success: (...args: any[]) => testState.toastSuccess(...args),
    error: (...args: any[]) => testState.toastError(...args),
  },
}));

vi.mock('@/lib/post-generation-events', () => ({
  emitPostGenerationStart: (...args: any[]) => testState.emitStart(...args),
  emitPostGenerationComplete: (...args: any[]) => testState.emitComplete(...args),
}));

describe('WeeklyPlanTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  const loadComponent = async () => {
    const mod = await import('@/components/posts/weekly-plan-table');
    return mod.WeeklyPlanTable;
  };

  const template = {
    id: 1,
    name: 'Продающий пост',
    type: 'post',
    tone: 'neutral',
    length: 'medium',
    language: 'ru',
    seo_prompt_template: '',
    trend_prompt_template: '',
    additional_instructions: '',
    is_default: false,
    include_hashtags: false,
    max_hashtags: 0,
    created_at: '2026-02-26T00:00:00Z',
    updated_at: '2026-02-26T00:00:00Z',
  } as any;

  it('shows empty-state when templates list is empty', async () => {
    testState.apiFetch.mockResolvedValueOnce([]);
    const WeeklyPlanTable = await loadComponent();

    render(<WeeklyPlanTable />);

    expect(await screen.findByText('Сначала создайте хотя бы один шаблон.')).toBeInTheDocument();
  });

  it('validates posts count before starting generation', async () => {
    testState.apiFetch.mockResolvedValueOnce([template]);
    const WeeklyPlanTable = await loadComponent();

    render(<WeeklyPlanTable />);

    await screen.findByText('Продающий');
    fireEvent.change(screen.getByPlaceholderText('Например, 5'), { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Создать' }));

    expect(testState.toastError).toHaveBeenCalledWith('Укажите количество постов от 1 до 21');
    expect(testState.apiFetch).toHaveBeenCalledTimes(1);
  });

  it('starts generation, emits start event and polls status to success', async () => {
    testState.apiFetch
      .mockResolvedValueOnce([template]) // load templates
      .mockResolvedValueOnce({
        success: true,
        message: 'Генерация запущена',
        task_id: 'task-123',
      }) // /posts/plan-weekly/
      .mockResolvedValueOnce({
        task_id: 'task-123',
        status: 'success',
        result: { created_posts: [101, 102] },
      }); // generation status poll

    const WeeklyPlanTable = await loadComponent();
    render(<WeeklyPlanTable />);

    await screen.findByText('Продающий');
    fireEvent.change(screen.getByPlaceholderText('Например, 5'), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Создать' }));

    await waitFor(() => {
      expect(testState.apiFetch).toHaveBeenCalledWith('/posts/plan-weekly/', {
        method: 'POST',
        body: {
          template_id: 1,
          posts_per_week: 2,
        },
      });
      expect(testState.emitStart).toHaveBeenCalledWith({
        count: 2,
        templateName: 'Продающий',
      });
    });

    await waitFor(() => {
      expect(testState.apiFetch).toHaveBeenCalledWith('/posts/generation-status/?task_id=task-123');
      expect(testState.toastSuccess).toHaveBeenCalledWith('Генерация постов завершена');
      expect(testState.emitComplete).toHaveBeenCalledWith({ count: 2 });
    });

    expect(screen.getByText('Готово: создано 2')).toBeInTheDocument();
  });

  it('shows backend error message from ApiError payload on generation start failure', async () => {
    const { ApiError } = await import('@/lib/api');
    testState.apiFetch
      .mockResolvedValueOnce([template])
      .mockRejectedValueOnce(new ApiError('bad request', 400, JSON.stringify({ error: 'Лимит плана превышен' })));

    const WeeklyPlanTable = await loadComponent();
    render(<WeeklyPlanTable />);

    await screen.findByText('Продающий');
    fireEvent.change(screen.getByPlaceholderText('Например, 5'), { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Создать' }));

    await waitFor(() => {
      expect(testState.toastError).toHaveBeenCalledWith('Лимит плана превышен');
    });
  });
});
