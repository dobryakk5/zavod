'use client';

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';
import { getVkConnectUrl } from '@/lib/api/vk';

interface VkConnectButtonProps {
  onConnected?: () => void;
  disabled?: boolean;
  className?: string;
  children?: ReactNode;
}

/**
 * Opens VK OAuth flow in a popup window and triggers onConnected once it closes.
 */
export function VkConnectButton({
  onConnected,
  disabled,
  className,
  children,
}: VkConnectButtonProps) {
  const [connecting, setConnecting] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const cleanupTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      cleanupTimer();
    };
  }, [cleanupTimer]);

  const handleClick = () => {
    if (connecting) {
      return;
    }

    const popup = window.open(
      getVkConnectUrl(),
      'vk-connect',
      'width=600,height=720,resizable=yes,scrollbars=yes,status=yes',
    );

    if (!popup) {
      toast.error('Не удалось открыть окно авторизации VK');
      return;
    }

    setConnecting(true);
    popup.focus();

    cleanupTimer();
    timerRef.current = setInterval(() => {
      if (!popup || popup.closed) {
        cleanupTimer();
        setConnecting(false);
        onConnected?.();
      }
    }, 1000);
  };

  return (
    <Button
      type="button"
      onClick={handleClick}
      disabled={disabled || connecting}
      className={className}
    >
      {children ?? (connecting ? 'Ожидание авторизации...' : 'Подключить группу VK')}
    </Button>
  );
}
