import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  push: vi.fn(),
  contactsList: vi.fn(),
  categoriesList: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: testState.push }),
}));

vi.mock('next/link', async () => {
  const ReactModule = await import('react');
  return {
    default: ({ href, children, ...props }: any) => ReactModule.createElement('a', { href, ...props }, children),
  };
});

vi.mock('@/lib/api/crm', () => ({
  crmContactsApi: {
    list: (...args: unknown[]) => testState.contactsList(...args),
  },
  crmCategoriesApi: {
    list: (...args: unknown[]) => testState.categoriesList(...args),
  },
}));

vi.mock('@/app/clients/new/new-clients-editor', () => ({
  NewClientForm: ({ onSave }: { onSave: (clients: Array<{ id: number }>) => void }) => (
    <button type="button" onClick={() => onSave([{ id: 123 }])}>
      SubmitMock
    </button>
  ),
}));

describe('NewClientPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.contactsList.mockResolvedValue([]);
    testState.categoriesList.mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
  });

  it('redirects to contact page after creating a client', async () => {
    const mod = await import('@/app/clients/new/page');
    const NewClientPage = mod.default;

    render(<NewClientPage />);

    await waitFor(() => {
      expect(testState.contactsList).toHaveBeenCalled();
      expect(testState.categoriesList).toHaveBeenCalled();
    });

    fireEvent.click(screen.getByRole('button', { name: 'SubmitMock' }));

    expect(testState.push).toHaveBeenCalledWith('/contact/123');
  });
});
