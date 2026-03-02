import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  push: vi.fn(),
  router: { push: vi.fn() },
  searchQuery: '',
  useTenantTimezone: vi.fn(() => ({ timezone: 'Europe/Moscow', loading: false })),
  formatInTenantTimezone: vi.fn((value: string) => `formatted:${value}`),
  onStart: null as null | ((detail: any) => void),
  onComplete: null as null | ((detail: any) => void),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => testState.router,
  useSearchParams: () => ({
    get: (key: string) => new URLSearchParams(testState.searchQuery).get(key),
    toString: () => testState.searchQuery,
  }),
}));

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    apiFetch: testState.apiFetch,
  };
});

vi.mock('@/lib/hooks', () => ({
  useTenantTimezone: testState.useTenantTimezone,
}));

vi.mock('@/lib/timezone', () => ({
  formatInTenantTimezone: testState.formatInTenantTimezone,
}));

vi.mock('@/lib/post-generation-events', () => ({
  subscribeToPostGenerationStart: (cb: any) => {
    testState.onStart = cb;
    return () => {
      if (testState.onStart === cb) testState.onStart = null;
    };
  },
  subscribeToPostGenerationComplete: (cb: any) => {
    testState.onComplete = cb;
    return () => {
      if (testState.onComplete === cb) testState.onComplete = null;
    };
  },
}));

vi.mock('@/components/ui/select', async () => {
  const ReactModule = await import('react');
  const SelectCtx = ReactModule.createContext<{ value: string; onValueChange?: (value: string) => void } | null>(null);

  const Select = ({ value, onValueChange, children }: any) =>
    ReactModule.createElement(SelectCtx.Provider, { value: { value, onValueChange } }, children);

  const SelectTrigger = ({ children, ...props }: any) => ReactModule.createElement('button', { type: 'button', ...props }, children);
  const SelectValue = ({ placeholder }: any) => {
    const ctx = ReactModule.useContext(SelectCtx);
    return ReactModule.createElement('span', null, ctx?.value || placeholder || '');
  };
  const SelectContent = ({ children, ...props }: any) => ReactModule.createElement('div', props, children);
  const SelectItem = ({ value, children, ...props }: any) => {
    const ctx = ReactModule.useContext(SelectCtx);
    return ReactModule.createElement(
      'button',
      {
        type: 'button',
        onClick: () => ctx?.onValueChange?.(value),
        ...props,
      },
      children
    );
  };

  return { Select, SelectTrigger, SelectValue, SelectContent, SelectItem };
});

describe('PostsTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.router.push = testState.push;
    testState.searchQuery = '';
    testState.onStart = null;
    testState.onComplete = null;
    testState.useTenantTimezone.mockReturnValue({ timezone: 'Europe/Moscow', loading: false });
    testState.formatInTenantTimezone.mockImplementation((value: string) => `formatted:${value}`);
  });

  afterEach(() => {
    cleanup();
  });

  const loadComponent = async () => {
    const mod = await import('@/components/posts/posts-table');
    return mod.PostsTable;
  };

  it('shows empty state when posts list is empty', async () => {
    testState.apiFetch.mockResolvedValueOnce({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    const PostsTable = await loadComponent();

    render(<PostsTable />);

    expect(await screen.findByText('Постов пока нет.')).toBeInTheDocument();
  });

  it('renders post row, formatted schedule and pagination controls', async () => {
    testState.searchQuery = 'page=2';
    testState.apiFetch.mockResolvedValueOnce({
      count: 60,
      next: null,
      previous: null,
      results: [
        {
          id: 42,
          title: 'Новый пост',
          status: 'draft',
          created_at: '2026-02-26T00:00:00Z',
          platforms: ['telegram'],
          template_name: 'Продающий пост',
          has_images: true,
          has_videos: true,
          next_scheduled_at: '2026-02-27T10:15:00Z',
        },
      ],
    });

    const PostsTable = await loadComponent();
    render(<PostsTable />);

    expect(await screen.findByRole('link', { name: 'Новый пост' })).toHaveAttribute('href', '/posts/42');
    expect(screen.getByText('formatted:2026-02-27T10:15:00Z')).toBeInTheDocument();
    expect(screen.getByText('Продающий')).toBeInTheDocument();
    expect(screen.getByText('Есть фото')).toBeInTheDocument();
    expect(screen.getByText('Есть видео')).toBeInTheDocument();
    expect(screen.getByText('Показано 26-50 из 60')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Вперед' }));
    expect(testState.push).toHaveBeenCalledWith('/posts?page=3');

    fireEvent.click(screen.getByRole('button', { name: 'Назад' }));
    expect(testState.push).toHaveBeenCalledWith('/posts');
  });

  it('redirects to login on 401 ApiError', async () => {
    const { ApiError } = await import('@/lib/api');
    testState.apiFetch.mockRejectedValueOnce(new ApiError('unauthorized', 401));
    const PostsTable = await loadComponent();

    render(<PostsTable />);

    await waitFor(() => {
      expect(testState.push).toHaveBeenCalledWith('/login');
    });
  });

  it('updates query when filter option is selected and resets page', async () => {
    testState.searchQuery = 'page=2';
    testState.apiFetch.mockResolvedValueOnce({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    const PostsTable = await loadComponent();

    render(<PostsTable />);
    await screen.findByText('Постов пока нет.');

    fireEvent.click(screen.getByRole('button', { name: 'Все статусы' }));
    fireEvent.click(screen.getByRole('button', { name: 'Черновики' }));

    expect(testState.push).toHaveBeenCalledWith('/posts?status=draft');
  });

  it('shows placeholders on generation start and removes them on completion', async () => {
    testState.apiFetch
      .mockResolvedValueOnce({
        count: 0,
        next: null,
        previous: null,
        results: [],
      })
      .mockResolvedValueOnce({
        count: 0,
        next: null,
        previous: null,
        results: [],
      })
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 50,
            title: 'Сгенерированный пост',
            status: 'draft',
            created_at: '2026-02-26T00:00:00Z',
            platforms: [],
            template_name: null,
            has_images: false,
            has_videos: false,
            next_scheduled_at: null,
          },
        ],
      });

    const PostsTable = await loadComponent();
    render(<PostsTable />);

    await screen.findByText('Постов пока нет.');
    testState.onStart?.({ count: 1, templateName: 'Экспертный' });

    expect(await screen.findByText('Новый пост создается')).toBeInTheDocument();
    expect(screen.getByText('Экспертный')).toBeInTheDocument();

    testState.onComplete?.({ count: 1 });

    await waitFor(() => {
      expect(testState.apiFetch).toHaveBeenCalledTimes(3);
      expect(screen.getByText('Сгенерированный пост')).toBeInTheDocument();
    });
  });
});
