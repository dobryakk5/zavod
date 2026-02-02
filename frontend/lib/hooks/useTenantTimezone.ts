'use client';

import { useEffect, useState } from 'react';
import { clientApi } from '@/lib/api/client';
import { DEFAULT_TENANT_TIMEZONE, normalizeTenantTimezone } from '@/lib/timezone';

export function useTenantTimezone() {
  const [timezone, setTimezone] = useState(DEFAULT_TENANT_TIMEZONE);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    const loadTimezone = async () => {
      try {
        const settings = await clientApi.getSettings();
        if (!isActive) return;
        setTimezone(normalizeTenantTimezone(settings.timezone));
      } catch (error) {
        if (!isActive) return;
        console.warn('Failed to load tenant timezone', error);
        setTimezone(DEFAULT_TENANT_TIMEZONE);
      } finally {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void loadTimezone();

    return () => {
      isActive = false;
    };
  }, []);

  return { timezone, loading };
}
