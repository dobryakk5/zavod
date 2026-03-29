import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateSettings: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('@/lib/hooks', () => ({
  useRole: () => ({ canEdit: true }),
}));

vi.mock('@/lib/api/client', () => ({
  clientApi: {
    getSettings: (...args: unknown[]) => testState.getSettings(...args),
    updateSettings: (...args: unknown[]) => testState.updateSettings(...args),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: (...args: unknown[]) => testState.toastSuccess(...args),
    error: (...args: unknown[]) => testState.toastError(...args),
  },
}));

vi.mock('@/components/ui/select', async () => {
  const ReactModule = await import('react');
  return {
    Select: ({ value, onValueChange, children }: any) => (
      <div data-select-root="">
        {ReactModule.Children.map(children, (child) =>
          ReactModule.isValidElement(child)
            ? ReactModule.cloneElement(child as React.ReactElement<any>, { value, onValueChange })
            : child
        )}
      </div>
    ),
    SelectTrigger: ({ children, id }: any) => <div id={id}>{children}</div>,
    SelectValue: ({ placeholder, value }: any) => <span>{value || placeholder}</span>,
    SelectContent: ({ children, value, onValueChange }: any) => (
      <select
        aria-label="Часовой пояс клиента"
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
      >
        {children}
      </select>
    ),
    SelectItem: ({ value, children }: any) => <option value={value}>{children}</option>,
  };
});

describe('ClientTimezoneSetting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.getSettings.mockResolvedValue({ timezone: 'Europe/Moscow' });
    testState.updateSettings.mockResolvedValue({ timezone: 'Europe/Moscow' });
  });

  afterEach(() => {
    cleanup();
  });

  it('builds timezone options locally without requesting /api/timezones', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const mod = await import('@/components/settings/client-timezone-setting');
    const ClientTimezoneSetting = mod.ClientTimezoneSetting;

    render(<ClientTimezoneSetting />);

    await waitFor(() => {
      expect(testState.getSettings).toHaveBeenCalledTimes(1);
    });

    expect(fetchSpy).not.toHaveBeenCalled();
    expect(await screen.findByRole('option', { name: /Europe\/Moscow/i })).toBeInTheDocument();
    expect(testState.toastError).not.toHaveBeenCalledWith('Не удалось загрузить список часовых поясов');

    fetchSpy.mockRestore();
  });
});
