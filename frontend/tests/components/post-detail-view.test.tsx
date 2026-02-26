import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/api';

const testState = vi.hoisted(() => ({
  postsGet: vi.fn(),
  postsListAll: vi.fn(),
  postsUpdate: vi.fn(),
  postsGenerateImage: vi.fn(),
  postsGenerateVideo: vi.fn(),
  postsRegenerateText: vi.fn(),
  postsDeleteImage: vi.fn(),
  postsDeleteVideo: vi.fn(),
  schedulesList: vi.fn(),
  schedulesPublishNow: vi.fn(),
  useClient: vi.fn(),
  useTenantTimezone: vi.fn(),
  sanitizeRichText: vi.fn((html: string) => html),
  highlightPhrasesInHtml: vi.fn((html: string) => html),
  formatInTenantTimezone: vi.fn((value: string) => `fmt:${value}`),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  toastWarning: vi.fn(),
}));

vi.mock('@/lib/api/posts', () => ({
  postsApi: {
    get: (...args: any[]) => testState.postsGet(...args),
    listAll: (...args: any[]) => testState.postsListAll(...args),
    update: (...args: any[]) => testState.postsUpdate(...args),
    generateImage: (...args: any[]) => testState.postsGenerateImage(...args),
    generateVideo: (...args: any[]) => testState.postsGenerateVideo(...args),
    regenerateText: (...args: any[]) => testState.postsRegenerateText(...args),
    deleteImage: (...args: any[]) => testState.postsDeleteImage(...args),
    deleteVideo: (...args: any[]) => testState.postsDeleteVideo(...args),
  },
}));

vi.mock('@/lib/api/schedules', () => ({
  schedulesApi: {
    list: (...args: any[]) => testState.schedulesList(...args),
    publishNow: (...args: any[]) => testState.schedulesPublishNow(...args),
  },
}));

vi.mock('@/lib/hooks', () => ({
  useClient: (...args: any[]) => testState.useClient(...args),
  useTenantTimezone: (...args: any[]) => testState.useTenantTimezone(...args),
}));

vi.mock('@/lib/sanitize-html', () => ({
  sanitizeRichText: (...args: any[]) => testState.sanitizeRichText(...args),
}));

vi.mock('@/lib/highlight-html', () => ({
  highlightPhrasesInHtml: (...args: any[]) => testState.highlightPhrasesInHtml(...args),
}));

vi.mock('@/lib/timezone', () => ({
  formatInTenantTimezone: (...args: any[]) => testState.formatInTenantTimezone(...args),
}));

vi.mock('sonner', () => ({
  toast: {
    success: (...args: any[]) => testState.toastSuccess(...args),
    error: (...args: any[]) => testState.toastError(...args),
    warning: (...args: any[]) => testState.toastWarning(...args),
  },
}));

vi.mock('next/image', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ alt, fill: _fill, unoptimized: _unoptimized, ...props }: any) =>
      ReactModule.createElement('img', { alt, ...props }),
  };
});

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) =>
      ReactModule.createElement('a', { href: typeof href === 'string' ? href : String(href), ...props }, children),
  };
});

vi.mock('@/components/ui/dialog', async () => {
  const ReactModule = await import('react');
  const wrap =
    (tag: string) =>
    ({ children, ...props }: any) =>
      ReactModule.createElement(tag, props, children);

  return {
    Dialog: ({ children }: any) => ReactModule.createElement('div', null, children),
    DialogContent: wrap('div'),
    DialogDescription: wrap('p'),
    DialogTitle: wrap('h3'),
  };
});

vi.mock('@/components/ui/visually-hidden', async () => {
  const ReactModule = await import('react');
  return {
    VisuallyHidden: ({ children }: any) => ReactModule.createElement('div', { style: { display: 'none' } }, children),
  };
});

vi.mock('@/components/posts/schedule-post-dialog', async () => {
  const ReactModule = await import('react');
  return {
    SchedulePostDialog: (props: any) =>
      ReactModule.createElement('div', { 'data-testid': 'schedule-post-dialog', 'data-post-id': props.postId }),
  };
});

describe('PostDetailView', () => {
  const basePost = {
    id: 123,
    title: 'Пост про запуск',
    hook_title: 'Старый хук',
    text: '<p>Контент поста</p>',
    status: 'draft',
    created_at: '2026-02-26T10:00:00Z',
    template_type: 'expert_post',
    template_name: 'Экспертный пост',
    platforms: ['telegram'],
    images: [],
    videos: [],
    wordstat_phrases_used: ['автоворонка'],
  } as any;

  beforeEach(() => {
    vi.resetAllMocks();
    testState.useClient.mockReturnValue({
      data: {
        role: 'owner',
        client: {
          slug: 'zavod',
          last_image_generation_at: null,
          last_video_generation_at: null,
        },
      },
      loading: false,
      error: null,
    });
    testState.useTenantTimezone.mockReturnValue({ timezone: 'Europe/Moscow', loading: false });
    testState.formatInTenantTimezone.mockImplementation((value: string) => `fmt:${value}`);
    testState.postsListAll.mockResolvedValue([{ id: 123 }]);
    testState.schedulesList.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
    cleanup();
  });

  const loadComponent = async () => {
    const mod = await import('@/components/posts/post-detail-view');
    return mod.PostDetailView;
  };

  it('shows error state and toast when post cannot be loaded', async () => {
    testState.postsGet.mockRejectedValueOnce(new Error('boom'));
    const PostDetailView = await loadComponent();

    render(<PostDetailView postId={123} />);

    expect(await screen.findByText('Не удалось загрузить пост')).toBeInTheDocument();
    expect(testState.toastError).toHaveBeenCalledWith('Ошибка загрузки поста');
  });

  it('renders post details and saves hook title', async () => {
    testState.postsGet.mockResolvedValueOnce(basePost);
    testState.postsUpdate.mockResolvedValueOnce({ ...basePost, hook_title: 'Новый хук' });
    const PostDetailView = await loadComponent();

    render(<PostDetailView postId={123} />);

    expect(await screen.findByRole('heading', { name: 'Пост про запуск' })).toBeInTheDocument();
    expect(screen.getByText(/fmt:2026-02-26T10:00:00Z/)).toBeInTheDocument();
    expect(screen.getByTestId('schedule-post-dialog')).toHaveAttribute('data-post-id', '123');
    expect(screen.getByText('Запланированных публикаций для этого поста нет.')).toBeInTheDocument();

    const hookInput = screen.getByPlaceholderText('Например: Это работает!') as HTMLInputElement;
    fireEvent.change(hookInput, { target: { value: 'Новый хук' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() => {
      expect(testState.postsUpdate).toHaveBeenCalledWith(123, { hook_title: 'Новый хук' });
      expect(testState.toastSuccess).toHaveBeenCalledWith('Цепляющий заголовок (для фото) обновлен');
    });

    expect(hookInput.value).toBe('Новый хук');
  });

  it('publishes pending schedule and refreshes schedules/post', async () => {
    testState.postsGet
      .mockResolvedValueOnce(basePost) // initial load
      .mockResolvedValueOnce({ ...basePost, status: 'scheduled' }); // refresh after publish
    testState.schedulesList
      .mockResolvedValueOnce([
        {
          id: 11,
          post: 123,
          social_account: 3,
          social_account_name: 'Основной TG',
          platform: 'telegram',
          post_title: 'Пост про запуск',
          scheduled_at: '2026-02-27T12:00:00Z',
          status: 'pending',
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 11,
          post: 123,
          social_account: 3,
          social_account_name: 'Основной TG',
          platform: 'telegram',
          post_title: 'Пост про запуск',
          scheduled_at: '2026-02-27T12:00:00Z',
          status: 'published',
        },
      ]);
    testState.schedulesPublishNow.mockResolvedValueOnce({ status: 'published' });

    const PostDetailView = await loadComponent();
    render(<PostDetailView postId={123} />);

    expect(await screen.findByText('Опубликовать сейчас')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Опубликовать сейчас' }));

    await waitFor(() => {
      expect(testState.schedulesPublishNow).toHaveBeenCalledWith(11);
      expect(testState.toastSuccess).toHaveBeenCalledWith('Опубликовано');
    });

    await waitFor(() => {
      expect(testState.schedulesList).toHaveBeenCalledTimes(2);
      expect(testState.postsGet).toHaveBeenCalledTimes(2);
      expect(screen.getByText('Опубликован')).toBeInTheDocument();
    });
  });

  it('starts image generation and polls until a new image appears', async () => {
    testState.postsGet
      .mockResolvedValueOnce(basePost)
      .mockResolvedValueOnce({
        ...basePost,
        images: [{ id: 501, image: '/media/generated.png', alt_text: 'AI превью', width: 1200, height: 900 }],
      });
    testState.postsGenerateImage.mockResolvedValueOnce(undefined);

    const PostDetailView = await loadComponent();
    render(<PostDetailView postId={123} />);

    expect(await screen.findByRole('heading', { name: 'Пост про запуск' })).toBeInTheDocument();

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: /^Изображение/i }));

    await act(async () => {});

    expect(testState.postsGenerateImage).toHaveBeenCalledWith(123);
    expect(testState.toastSuccess).toHaveBeenCalledWith('Генерация изображения запущена');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(testState.toastSuccess).toHaveBeenCalledWith('Изображение сгенерировано!');

    vi.useRealTimers();
    await waitFor(() => {
      expect(screen.getByAltText('AI превью')).toBeInTheDocument();
    });
  });

  it('shows image cooldown message from ApiError payload', async () => {
    testState.postsGet.mockResolvedValueOnce(basePost);
    testState.postsGenerateImage.mockRejectedValueOnce(
      new ApiError(
        'rate_limited',
        429,
        JSON.stringify({
          error: 'Слишком часто генерируете изображение',
          cooldown_ends_at: '2099-01-01T12:00:00Z',
        })
      )
    );

    const PostDetailView = await loadComponent();
    render(<PostDetailView postId={123} />);

    expect(await screen.findByRole('heading', { name: 'Пост про запуск' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /^Изображение/i }));

    await waitFor(() => {
      expect(testState.toastError).toHaveBeenCalledWith('Слишком часто генерируете изображение');
    });

    expect(
      await screen.findByText(/Повторная генерация изображения будет доступна через/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^Изображение/i })).toBeDisabled();
  });

  it('starts video generation from text and refreshes post after delay', async () => {
    testState.postsGet
      .mockResolvedValueOnce(basePost)
      .mockResolvedValueOnce({
        ...basePost,
        videos: [{ id: 701, video: '/media/generated.mp4' }],
      });
    testState.postsGenerateVideo.mockResolvedValueOnce(undefined);

    const PostDetailView = await loadComponent();
    render(<PostDetailView postId={123} />);

    expect(await screen.findByRole('heading', { name: 'Пост про запуск' })).toBeInTheDocument();

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: /Видео по тексту/i }));

    await act(async () => {});

    expect(testState.postsGenerateVideo).toHaveBeenCalledWith(123, { source: 'text', method: 'veo' });
    expect(testState.toastSuccess).toHaveBeenCalledWith('Генерация видео по тексту запущена');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
    });

    vi.useRealTimers();
    await waitFor(() => {
      expect(testState.postsGet).toHaveBeenCalledTimes(2);
      expect(document.querySelector('video')).toBeTruthy();
    });
  });

  it('shows video cooldown message when video generation API returns cooldown payload', async () => {
    testState.postsGet.mockResolvedValueOnce(basePost);
    testState.postsGenerateVideo.mockRejectedValueOnce(
      new ApiError(
        'rate_limited',
        429,
        JSON.stringify({
          error: 'Видео временно недоступно',
          cooldown_ends_at: '2099-01-01T13:00:00Z',
        })
      )
    );

    const PostDetailView = await loadComponent();
    render(<PostDetailView postId={123} />);

    expect(await screen.findByRole('heading', { name: 'Пост про запуск' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Видео по фото/i }));

    await waitFor(() => {
      expect(testState.toastError).toHaveBeenCalledWith('Видео временно недоступно');
    });

    expect(
      await screen.findByText(/Повторная генерация видео будет доступна через/i)
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Видео по фото/i })).toBeDisabled();
  });

  it('regenerates text and reloads post after delay', async () => {
    testState.postsGet
      .mockResolvedValueOnce(basePost)
      .mockResolvedValueOnce({
        ...basePost,
        text: '<p>Новый текст после перегенерации</p>',
      });
    testState.postsRegenerateText.mockResolvedValueOnce(undefined);

    const PostDetailView = await loadComponent();
    render(<PostDetailView postId={123} />);

    expect(await screen.findByRole('heading', { name: 'Пост про запуск' })).toBeInTheDocument();

    vi.useFakeTimers();
    fireEvent.click(screen.getByRole('button', { name: 'Перегенерировать текст' }));

    await act(async () => {});

    expect(testState.postsRegenerateText).toHaveBeenCalledWith(123);
    expect(testState.toastSuccess).toHaveBeenCalledWith('Перегенерация текста запущена');

    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });

    vi.useRealTimers();
    await waitFor(() => {
      expect(testState.postsGet).toHaveBeenCalledTimes(2);
      expect(screen.getByText('Новый текст после перегенерации')).toBeInTheDocument();
    });
  });

  it('deletes image and video after confirmation and reloads post', async () => {
    const postWithMedia = {
      ...basePost,
      images: [{ id: 21, image: '/media/old.png', alt_text: 'Старое изображение', width: 800, height: 600 }],
      videos: [{ id: 31, video: '/media/old.mp4' }],
    };

    testState.postsGet
      .mockResolvedValueOnce(postWithMedia)
      .mockResolvedValueOnce({ ...postWithMedia, images: [] })
      .mockResolvedValueOnce({ ...postWithMedia, images: [], videos: [] });
    testState.postsDeleteImage.mockResolvedValueOnce(undefined);
    testState.postsDeleteVideo.mockResolvedValueOnce(undefined);

    const PostDetailView = await loadComponent();
    render(<PostDetailView postId={123} />);

    expect(await screen.findByRole('heading', { name: 'Пост про запуск' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTitle('Удалить изображение')).toBeInTheDocument();
      expect(screen.getByTitle('Удалить видео')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle('Удалить изображение'));
    fireEvent.click(screen.getByRole('button', { name: 'Да' }));

    await waitFor(() => {
      expect(testState.postsDeleteImage).toHaveBeenCalledWith(123, 21);
      expect(testState.toastSuccess).toHaveBeenCalledWith('Изображение удалено');
    });

    fireEvent.click(screen.getByTitle('Удалить видео'));
    fireEvent.click(screen.getByRole('button', { name: 'Да' }));

    await waitFor(() => {
      expect(testState.postsDeleteVideo).toHaveBeenCalledWith(123, 31);
      expect(testState.toastSuccess).toHaveBeenCalledWith('Видео удалено');
    });
  });
});
