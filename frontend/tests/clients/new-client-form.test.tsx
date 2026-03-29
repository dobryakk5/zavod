import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  createContact: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('@/lib/api/crm', () => ({
  crmCategoriesApi: {
    list: vi.fn(),
  },
  crmContactsApi: {
    create: (...args: unknown[]) => testState.createContact(...args),
    list: vi.fn(),
  },
  crmEventsApi: {
    list: vi.fn(),
  },
  crmPaymentsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
    generateYooKassaLink: vi.fn(),
  },
}));

vi.mock('@/lib/api/client', () => ({
  clientApi: {
    getSettings: vi.fn(),
  },
}));

describe('NewClientForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.createContact.mockResolvedValue({
      id: 123,
      name: 'Анна Иванова',
      email: '',
      phone: '',
      category_id: null,
      status: 'active',
      photo_url: '',
      notes: '',
      parent_id: null,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders with empty parent option without crashing', async () => {
    const mod = await import('@/app/clients/new/new-clients-editor');
    const { NewClientForm } = mod;

    render(<NewClientForm clients={[]} categories={[]} onSave={vi.fn()} />);

    expect(screen.getByLabelText(/Имя/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Добавить клиента' })).toBeInTheDocument();
  });

  it('creates a client and passes it to onSave', async () => {
    const onSave = vi.fn();
    const mod = await import('@/app/clients/new/new-clients-editor');
    const { NewClientForm } = mod;

    render(<NewClientForm clients={[]} categories={[]} onSave={onSave} submitLabel="Создать клиента" />);

    fireEvent.change(screen.getByLabelText(/Имя/), { target: { value: 'Анна Иванова' } });
    fireEvent.click(screen.getByRole('button', { name: 'Создать клиента' }));

    await waitFor(() => {
      expect(testState.createContact).toHaveBeenCalledWith({
        name: 'Анна Иванова',
        email: '',
        phone: '',
        category_id: null,
        status: 'active',
        photo_url: '',
        notes: '',
        parent_id: null,
      });
    });

    expect(onSave).toHaveBeenCalledWith([
      expect.objectContaining({
        id: 123,
        name: 'Анна Иванова',
      }),
    ]);
  });
});
