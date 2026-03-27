import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  pathname: '/dashboard',
  push: vi.fn(),
  info: vi.fn(),
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

    expect(screen.getByRole('link', { name: 'Дашборд' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Клиенты' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Маркетинг' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Продукты' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Настройки' })).toBeInTheDocument();
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
});
