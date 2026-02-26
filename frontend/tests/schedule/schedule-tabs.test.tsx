import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/app/schedule/calendar', async () => {
  const ReactModule = await import('react');
  return {
    default: () => ReactModule.createElement('div', { 'data-testid': 'calendar-view' }, 'Calendar View'),
  };
});

vi.mock('@/app/schedule/list-view', async () => {
  const ReactModule = await import('react');
  return {
    default: () => ReactModule.createElement('div', { 'data-testid': 'list-view' }, 'List View'),
  };
});

vi.mock('@/components/ui/tabs', async () => {
  const ReactModule = await import('react');
  const TabsCtx = ReactModule.createContext<{ value: string; onValueChange?: (value: string) => void } | null>(null);

  const Tabs = ({ value, onValueChange, children, ...props }: any) =>
    ReactModule.createElement(TabsCtx.Provider, { value: { value, onValueChange } }, ReactModule.createElement('div', props, children));

  const TabsList = ({ children, ...props }: any) => ReactModule.createElement('div', props, children);

  const TabsTrigger = ({ value, children, ...props }: any) => {
    const ctx = ReactModule.useContext(TabsCtx);
    const isActive = ctx?.value === value;
    return ReactModule.createElement(
      'button',
      {
        type: 'button',
        'data-state': isActive ? 'active' : 'inactive',
        'aria-pressed': isActive,
        onClick: () => ctx?.onValueChange?.(value),
        ...props,
      },
      children
    );
  };

  const TabsContent = ({ value, children, ...props }: any) => {
    const ctx = ReactModule.useContext(TabsCtx);
    if (ctx?.value !== value) return null;
    return ReactModule.createElement('div', props, children);
  };

  return { Tabs, TabsList, TabsTrigger, TabsContent };
});

describe('ScheduleTabs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
    vi.resetModules();
  });

  const loadComponent = async () => {
    const mod = await import('@/app/schedule/schedule-tabs');
    return mod.default;
  };

  it('shows title and switches from calendar tab to list tab', async () => {
    const ScheduleTabs = await loadComponent();
    render(<ScheduleTabs />);

    expect(screen.getByRole('heading', { name: 'Расписание публикаций' })).toBeInTheDocument();
    expect(screen.getByTestId('calendar-view')).toBeInTheDocument();
    expect(screen.queryByTestId('list-view')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Список' }));

    expect(screen.queryByTestId('calendar-view')).not.toBeInTheDocument();
    expect(screen.getByTestId('list-view')).toBeInTheDocument();
  });

  it('hides title when showTitle is false', async () => {
    const ScheduleTabs = await loadComponent();
    render(<ScheduleTabs showTitle={false} />);

    expect(screen.queryByRole('heading', { name: 'Расписание публикаций' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Календарь' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Список' })).toBeInTheDocument();
  });
});
