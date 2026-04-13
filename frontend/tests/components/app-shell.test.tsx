import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  pathname: '/dashboard',
  push: vi.fn(),
  info: vi.fn(),
  updateName: vi.fn(),
  setActiveClient: vi.fn(),
  reload: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  usePathname: () => testState.pathname,
  useRouter: () => ({ push: testState.push }),
}));

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) => ReactModule.createElement('a', { href, ...props }, children),
  };
});

vi.mock('next/image', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ alt, ...props }: any) => ReactModule.createElement('img', { alt, ...props }),
  };
});

vi.mock('@/lib/api/client', () => ({
  clientApi: {
    info: (...args: unknown[]) => testState.info(...args),
    updateName: (...args: unknown[]) => testState.updateName(...args),
    setActiveClient: (...args: unknown[]) => testState.setActiveClient(...args),
  },
}));

vi.mock('@/components/ui/select', async () => {
  const ReactModule = await import('react');
  const SelectContext = ReactModule.createContext<{
    value?: string;
    onValueChange?: (value: string) => void;
    disabled?: boolean;
  }>({});

  const Select = ({ value, onValueChange, disabled, children }: any) => (
    <SelectContext.Provider value={{ value, onValueChange, disabled }}>{children}</SelectContext.Provider>
  );
  const SelectTrigger = ({ children }: any) => <div>{children}</div>;
  const SelectValue = ({ placeholder }: any) => {
    const context = ReactModule.useContext(SelectContext);
    return <span>{context.value || placeholder}</span>;
  };
  const SelectContent = ({ children }: any) => {
    const context = ReactModule.useContext(SelectContext);
    const options = ReactModule.Children.toArray(children).map((child: any) => ({
      value: child.props.value,
      label: child.props.children,
    }));
    return (
      <select
        data-testid="client-switcher"
        value={context.value}
        disabled={context.disabled}
        onChange={(event) => context.onValueChange?.(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  };
  const SelectItem = ({ value, children }: any) => <option value={value}>{children}</option>;

  return { Select, SelectTrigger, SelectValue, SelectContent, SelectItem };
});

describe('AppShell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.pathname = '/dashboard';
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ accounts: [] }),
    }));
    Object.defineProperty(window, 'location', {
      value: { reload: testState.reload, origin: 'https://frontend.example.com' },
      writable: true,
    });
    testState.info.mockResolvedValue({
      client: { id: 1, name: 'Main', slug: 'main' },
      role: 'owner',
      active_client_id: 1,
      memberships: [
        { client: { id: 1, name: 'Main', slug: 'main' }, role: 'owner' },
        { client: { id: 2, name: 'Second', slug: 'second' }, role: 'editor' },
      ],
    });
    testState.updateName.mockResolvedValue({
      client: { id: 1, name: 'Renamed Project', slug: 'main' },
      role: 'owner',
      active_client_id: 1,
      memberships: [
        { client: { id: 1, name: 'Renamed Project', slug: 'main' }, role: 'owner' },
        { client: { id: 2, name: 'Second', slug: 'second' }, role: 'editor' },
      ],
    });
    testState.setActiveClient.mockResolvedValue({
      client: { id: 2, name: 'Second', slug: 'second' },
      role: 'editor',
      active_client_id: 2,
      memberships: [
        { client: { id: 1, name: 'Main', slug: 'main' }, role: 'owner' },
        { client: { id: 2, name: 'Second', slug: 'second' }, role: 'editor' },
      ],
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('switches active project and reloads the page', async () => {
    const mod = await import('@/components/layout/app-shell');
    const AppShell = mod.AppShell;

    render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );

    await waitFor(() => {
      expect(testState.info).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByTestId('client-switcher'), { target: { value: '2' } });

    await waitFor(() => {
      expect(testState.setActiveClient).toHaveBeenCalledWith(2);
      expect(testState.reload).toHaveBeenCalled();
    });
  });

  it('shows project rename pencil only for owner and saves updated name', async () => {
    const mod = await import('@/components/layout/app-shell');
    const AppShell = mod.AppShell;

    render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );

    await waitFor(() => {
      expect(testState.info).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByLabelText('Редактировать название проекта'));
    fireEvent.change(screen.getByLabelText('Название проекта'), {
      target: { value: 'Renamed Project' },
    });
    fireEvent.click(screen.getByLabelText('Сохранить название проекта'));

    await waitFor(() => {
      expect(testState.updateName).toHaveBeenCalledWith('Renamed Project');
    });

    expect(screen.getAllByText('Renamed Project').length).toBeGreaterThan(0);
  });

  it('does not show project rename pencil for non-owner role', async () => {
    testState.info.mockResolvedValue({
      client: { id: 2, name: 'Second', slug: 'second' },
      role: 'editor',
      active_client_id: 2,
      memberships: [
        { client: { id: 1, name: 'Main', slug: 'main' }, role: 'owner' },
        { client: { id: 2, name: 'Second', slug: 'second' }, role: 'editor' },
      ],
    });

    const mod = await import('@/components/layout/app-shell');
    const AppShell = mod.AppShell;

    render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );

    await waitFor(() => {
      expect(testState.info).toHaveBeenCalled();
    });

    expect(screen.queryByLabelText('Редактировать название проекта')).not.toBeInTheDocument();
  });

  it('renders only marketing top-level navigation for internal routes', async () => {
    const mod = await import('@/components/layout/app-shell');
    const AppShell = mod.AppShell;

    render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );

    await waitFor(() => {
      expect(testState.info).toHaveBeenCalled();
    });

    expect(screen.getAllByRole('link', { name: 'Обзор' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Маркетинг' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Продукты' }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('link', { name: 'Настройки' }).length).toBeGreaterThan(0);
    expect(screen.queryByText('Приветствие')).not.toBeInTheDocument();
    expect(screen.queryByText('Аналитика')).not.toBeInTheDocument();
    expect(screen.queryByText('Посты')).not.toBeInTheDocument();
    expect(screen.queryByText('SEO')).not.toBeInTheDocument();
    expect(screen.queryByText('Статьи')).not.toBeInTheDocument();
  });

  it('bypasses shell for public routes', async () => {
    testState.pathname = '/login';

    const mod = await import('@/components/layout/app-shell');
    const AppShell = mod.AppShell;

    render(
      <AppShell>
        <div>public content</div>
      </AppShell>
    );

    expect(screen.getByText('public content')).toBeInTheDocument();
    expect(screen.queryByText('Маркетинг')).not.toBeInTheDocument();
    expect(testState.info).not.toHaveBeenCalled();
  });

  it('bypasses shell for email verify route', async () => {
    testState.pathname = '/auth/email/verify';

    const mod = await import('@/components/layout/app-shell');
    const AppShell = mod.AppShell;

    render(
      <AppShell>
        <div>verify content</div>
      </AppShell>
    );

    expect(screen.getByText('verify content')).toBeInTheDocument();
    expect(screen.queryByText('Маркетинг')).not.toBeInTheDocument();
    expect(testState.info).not.toHaveBeenCalled();
  });

  it('logs out through the current auth endpoint', async () => {
    testState.pathname = '/dashboard';
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ accounts: [] }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const mod = await import('@/components/layout/app-shell');
    const AppShell = mod.AppShell;

    render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );

    await waitFor(() => {
      expect(testState.info).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Выйти' }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        'http://localhost:4000/auth/logout/',
        expect.objectContaining({
          method: 'POST',
          credentials: 'include',
        }),
      );
      expect(testState.push).toHaveBeenCalledWith('/');
    });
  });

  it('renders readable profile data in the user dialog instead of raw json', async () => {
    testState.pathname = '/dashboard';
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);

      if (url.endsWith('/auth/social/accounts')) {
        return Promise.resolve({
          ok: true,
          json: vi.fn().mockResolvedValue({
            accounts: [
              {
                provider: 'telegram',
                provider_id: '12345',
                created_at: '2026-03-27T10:00:00Z',
                extra_data: {
                  first_name: 'Иван',
                  last_name: 'Петров',
                  username: 'ivan_petrov',
                },
              },
            ],
          }),
        });
      }

      if (url.endsWith('/auth/telegram')) {
        return Promise.resolve({
          ok: true,
          json: vi.fn().mockResolvedValue({
            user: {
              telegramId: '12345',
              firstName: 'Иван',
              lastName: 'Петров',
              username: 'ivan_petrov',
              authDate: '2026-03-27T10:00:00Z',
              contactId: 42,
              tenantId: 1,
            },
          }),
        });
      }

      if (url.endsWith('/auth/vk')) {
        return Promise.resolve({
          ok: true,
          json: vi.fn().mockResolvedValue({
            user: {
              vkId: '777',
              firstName: 'Иван',
              lastName: 'Петров',
              username: 'ivanpetrov',
              authDate: '2026-03-27T11:00:00Z',
              contactId: 51,
              tenantId: 1,
            },
          }),
        });
      }

      return Promise.resolve({
        ok: true,
        json: vi.fn().mockResolvedValue({}),
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const mod = await import('@/components/layout/app-shell');
    const AppShell = mod.AppShell;

    render(
      <AppShell>
        <div>content</div>
      </AppShell>
    );

    await waitFor(() => {
      expect(testState.info).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByText('Профиль и соцаккаунты').closest('button') as HTMLButtonElement);

    await waitFor(() => {
      expect(screen.getByText('Подключённые способы входа')).toBeInTheDocument();
      expect(screen.getByText('Связанные соцаккаунты')).toBeInTheDocument();
      expect(screen.getByText('Telegram ID')).toBeInTheDocument();
      expect(screen.getByText('VK ID')).toBeInTheDocument();
      expect(screen.getAllByText('Иван Петров').length).toBeGreaterThan(0);
    });

    expect(screen.queryByText(/"sources":/)).not.toBeInTheDocument();
    expect(screen.queryByText(/"accounts":/)).not.toBeInTheDocument();
  });
});
