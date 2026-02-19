'use client';

import type { ReactNode } from 'react';
import { useCallback, useEffect, useMemo, useState } from 'react';

const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') ?? '';
const hasApiUrl = Boolean(API_URL);
const buildUrl = (path: string) => `${API_URL}${path}`;

const PROVIDER_META: Record<string, { label: string; icon: ReactNode }> = {
  telegram: {
    label: 'Telegram',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="#0088cc" aria-hidden="true">
        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.894 8.221-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.17 13.967l-2.965-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.983.592z" />
      </svg>
    ),
  },
  vk: {
    label: 'ВКонтакте',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="#0077FF" aria-hidden="true">
        <path d="M15.684 0H8.316C1.592 0 0 1.592 0 8.316v7.368C0 22.408 1.592 24 8.316 24h7.368C22.408 24 24 22.408 24 15.684V8.316C24 1.592 22.408 0 15.684 0zm3.692 17.123h-1.744c-.66 0-.862-.523-2.049-1.727-1.033-1-1.49-1.135-1.744-1.135-.356 0-.458.102-.458.593v1.575c0 .424-.135.678-1.253.678-1.846 0-3.896-1.118-5.335-3.202C5.1 11.366 4.5 9.218 4.5 8.775c0-.254.102-.491.593-.491h1.744c.44 0 .61.203.78.677.863 2.49 2.303 4.675 2.896 4.675.22 0 .322-.102.322-.66V9.633c-.068-1.186-.695-1.287-.695-1.71 0-.204.17-.407.44-.407h2.744c.373 0 .508.203.508.643v3.473c0 .372.17.508.271.508.22 0 .407-.136.813-.542 1.254-1.406 2.151-3.574 2.151-3.574.119-.254.322-.491.763-.491h1.744c.525 0 .644.27.525.643-.22 1.017-2.354 4.031-2.354 4.031-.186.305-.254.44 0 .78.186.254.796.779 1.203 1.253.745.847 1.32 1.558 1.473 2.049.17.491-.085.745-.576.745z" />
      </svg>
    ),
  },
  email: {
    label: 'Email',
    icon: (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" strokeWidth="2" aria-hidden="true">
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
      </svg>
    ),
  },
};

interface Channel {
  provider: string;
  label: string;
  provider_id: string;
  is_preferred: boolean;
}

interface ChannelSelectorProps {
  mode?: 'settings' | 'picker';
  clientId?: number | string;
  onSelect?: (channel: Channel) => void;
}

export function ChannelSelector({ mode = 'settings', clientId, onSelect }: ChannelSelectorProps) {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [preferred, setPreferred] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const endpoint = useMemo(() => {
    const base = buildUrl('/client/channel');
    if (mode === 'picker' && clientId != null && clientId !== '') {
      return `${base}?client_id=${encodeURIComponent(String(clientId))}`;
    }
    return base;
  }, [clientId, mode]);

  const fetchChannels = useCallback(async () => {
    if (!hasApiUrl) {
      setLoading(false);
      setError('NEXT_PUBLIC_API_URL не задан');
      return;
    }

    try {
      const response = await fetch(endpoint, { credentials: 'include' });
      if (!response.ok) {
        setError('Не удалось загрузить каналы');
        return;
      }
      const data = await response.json();
      const list = Array.isArray(data?.channels) ? data.channels : [];
      setChannels(list);
      setPreferred(data?.preferred || list[0]?.provider || null);
    } catch {
      setError('Ошибка соединения');
    } finally {
      setLoading(false);
    }
  }, [endpoint]);

  useEffect(() => {
    void fetchChannels();
  }, [fetchChannels]);

  const handleSelect = async (channel: Channel) => {
    if (mode === 'picker') {
      onSelect?.(channel);
      return;
    }

    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel: channel.provider }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setError(data?.error || 'Не удалось сохранить канал');
        return;
      }
      setPreferred(channel.provider);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch {
      setError('Ошибка соединения');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex gap-2">
        {[1, 2].map((item) => (
          <div key={item} className="h-10 w-32 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    );
  }

  if (channels.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Нет доступных каналов связи.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {mode === 'settings' && (
        <p className="text-sm text-muted-foreground">
          Выберите канал, который будет использоваться по умолчанию для связи.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        {channels.map((channel) => {
          const meta = PROVIDER_META[channel.provider] || { label: channel.label, icon: null };
          const active = channel.provider === preferred;

          return (
            <button
              key={`${channel.provider}:${channel.provider_id}`}
              type="button"
              onClick={() => handleSelect(channel)}
              disabled={saving}
              className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-all ${
                active
                  ? 'border-transparent bg-foreground text-background shadow-sm'
                  : 'border-border bg-background text-foreground hover:bg-muted/50'
              } disabled:opacity-50`}
            >
              {meta.icon}
              <span>{meta.label}</span>
              {active && mode === 'settings' && (
                <span className="ml-1 rounded-full bg-white/20 px-1.5 py-0.5 text-[10px] font-semibold">✓</span>
              )}
            </button>
          );
        })}
      </div>

      {mode === 'settings' && saved && <p className="text-xs text-emerald-600">Сохранено</p>}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}
