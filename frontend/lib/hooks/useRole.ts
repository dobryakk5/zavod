'use client';

import { useClient } from './useClient';
import type { UserRole } from '../types';

/**
 * Hook to get current user's role for the client
 */
export function useRole(): {
  role: UserRole | null;
  loading: boolean;
  canEdit: boolean;
  canView: boolean;
} {
  const { data, loading } = useClient();

  const role = data?.role || null;
  const canEdit = role === 'owner' || role === 'editor';
  const canView = role === 'owner' || role === 'editor' || role === 'viewer';

  return {
    role,
    loading,
    canEdit,
    canView,
  };
}
