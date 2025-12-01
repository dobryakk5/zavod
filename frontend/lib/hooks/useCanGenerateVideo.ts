'use client';

import { useClient } from './useClient';

/**
 * Hook to check if current user can generate videos
 * Video generation is only available in dev mode or for zavod client
 */
export function useCanGenerateVideo(): {
  canGenerateVideo: boolean;
  loading: boolean;
} {
  const { data, loading } = useClient();

  // Check dev mode from environment
  const isDevMode = process.env.NEXT_PUBLIC_DEV_MODE === 'true';

  // Check if client is zavod
  const isZavodClient = data?.client?.slug === 'zavod';

  const canGenerateVideo = isDevMode || isZavodClient;

  return {
    canGenerateVideo,
    loading,
  };
}
