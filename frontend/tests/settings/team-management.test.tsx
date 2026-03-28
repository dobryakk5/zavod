import React from 'react';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const testState = vi.hoisted(() => ({
  getTeam: vi.fn(),
  createTeamInvitation: vi.fn(),
  revokeTeamInvitation: vi.fn(),
  removeTeamMember: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock('@/lib/hooks', () => ({
  useRole: () => ({ role: 'owner' }),
}));

vi.mock('@/lib/api/client', () => ({
  clientApi: {
    getTeam: (...args: unknown[]) => testState.getTeam(...args),
    createTeamInvitation: (...args: unknown[]) => testState.createTeamInvitation(...args),
    revokeTeamInvitation: (...args: unknown[]) => testState.revokeTeamInvitation(...args),
    removeTeamMember: (...args: unknown[]) => testState.removeTeamMember(...args),
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
    SelectTrigger: ({ children }: any) => <>{children}</>,
    SelectValue: ({ placeholder }: any) => <span>{placeholder}</span>,
    SelectContent: ({ children, value, onValueChange }: any) => (
      <select aria-label="Платформа" value={value} onChange={(event) => onValueChange(event.target.value)}>
        {children}
      </select>
    ),
    SelectItem: ({ value, children }: any) => <option value={value}>{children}</option>,
  };
});

describe('TeamManagement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    testState.getTeam.mockResolvedValue({
      members: [],
      pending_invites: [],
      limit: 20,
      used_slots: 1,
    });
    testState.createTeamInvitation.mockResolvedValue({
      status: 'pending_created',
      message: 'Приглашение отправлено на email.',
      invite_id: 7,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('sends email team invitation from settings form', async () => {
    const mod = await import('@/components/settings/team-management');
    const TeamManagement = mod.TeamManagement;

    render(<TeamManagement />);

    await waitFor(() => {
      expect(testState.getTeam).toHaveBeenCalled();
    });

    fireEvent.change(screen.getByRole('combobox', { name: 'Платформа' }), {
      target: { value: 'email' },
    });
    fireEvent.change(screen.getByPlaceholderText('user@example.com'), {
      target: { value: 'invitee@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Пригласить' }));

    await waitFor(() => {
      expect(testState.createTeamInvitation).toHaveBeenCalledWith({
        provider: 'email',
        account_handle: 'invitee@example.com',
      });
    });

    expect(testState.toastSuccess).toHaveBeenCalledWith('Приглашение отправлено на email.');
  });
});
