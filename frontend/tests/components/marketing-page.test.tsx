import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) => ReactModule.createElement('a', { href, ...props }, children),
  };
});

vi.mock('@/lib/api/client', () => ({
  clientApi: {
    generationEventsSummary: vi.fn().mockResolvedValue({
      counts: {
        post: 9,
        article_write: 4,
        article_evaluate: 2,
        channel_analysis: 3,
        website_analysis: 2,
        weekly_collection: 1,
        seo_group: 5,
        wordstat_query: 8,
        google_query: 6,
      },
      limits: {},
      is_trial: false,
    }),
    summary: vi.fn().mockResolvedValue({
      total_posts: 24,
      posts_scheduled: 7,
      posts_published: 17,
      by_platform: [],
    }),
  },
}));

vi.mock('@/lib/api/crm', () => ({
  crmContactsApi: {
    list: vi.fn().mockResolvedValue([{ id: 1 }, { id: 2 }, { id: 3 }]),
  },
  crmEventsApi: {
    list: vi.fn().mockResolvedValue([
      { id: 1, status: 'scheduled', start_time: '2099-01-01T10:00:00Z' },
      { id: 2, status: 'completed', start_time: '2024-01-01T10:00:00Z' },
    ]),
  },
  crmDealsApi: {
    list: vi.fn().mockResolvedValue([{ id: 1 }, { id: 2 }]),
  },
}));

describe('MarketingPage', () => {
  it('renders the five marketing sections with links to deep pages', async () => {
    const mod = await import('@/app/welcome/page');
    const MarketingPage = mod.default;

    render(<MarketingPage />);

    expect(screen.getByRole('heading', { name: 'Маркетинг' })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Аналитика' })).toBeInTheDocument();
    });

    expect(screen.getByRole('heading', { name: 'SEO' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Контент / Посты' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Статьи' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Клиенты' })).toBeInTheDocument();

    expect(screen.getByRole('link', { name: 'Website' })).toHaveAttribute('href', '/analytics?tab=website');
    expect(screen.getByRole('link', { name: 'Конкуренты' })).toHaveAttribute('href', '/seo?tab=competitors');
    expect(screen.getByRole('link', { name: 'Новый пост' })).toHaveAttribute('href', '/posts/new');
    expect(screen.getByRole('link', { name: 'Открыть статьи' })).toHaveAttribute('href', '/articles');
    expect(screen.getByRole('link', { name: 'Календарь' })).toHaveAttribute('href', '/clients?tab=schedule&scheduleTab=calendar');
  });
});
