'use client';

import { useEffect, useState } from 'react';
import { clientApi } from '../api/client';
import type { ClientInfo } from '../types';

/**
 * Hook to get current client info and user role
 */
export function useClient() {
  const [data, setData] = useState<ClientInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const fetchClientInfo = async () => {
      try {
        setLoading(true);
        const info = await clientApi.info();
        setData(info);
        setError(null);
      } catch (err) {
        setError(err as Error);
      } finally {
        setLoading(false);
      }
    };

    fetchClientInfo();
  }, []);

  return { data, loading, error };
}
